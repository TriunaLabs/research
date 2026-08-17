"""Method C: in-storage candidate scoring — device contract + harness.

The article proposes Method C for computational-storage hardware (SmartSSD-
class NVMe + FPGA): the host sends the query and a probe list DOWN, the
device scores candidates next to the NAND and sends only top-k per cluster
UP. This file ships everything except the hardware:

  * the wire protocol (the exact bytes that would cross PCIe),
  * a NumPy reference implementation of the device-side computation
    (the functional spec an FPGA kernel must match),
  * a simulated device in a separate process that exclusively owns the
    corpus file — the host harness never touches the data, so protocol
    bytes are counted across a real process boundary,
  * a stub class where real device I/O plugs in.

What the simulation DOES establish: protocol correctness (Method C's top-20
must equal Method B/A's) and the true bus-byte count (~KBs down, ~300 KB up
vs 0.8 GB for Method B).

What it does NOT establish: timing or energy. A host CPU simulating an FPGA
proves nothing about either — those columns stay empty until someone runs
this against real hardware. Implement HardwareDevice and send results.

Usage:
    python method_c.py --dir D:\\aissd-bench [--backend sim]
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time

import numpy as np

DIMS = 1024
NPROBE = 8
TOPK = 20
VEC_BYTES = DIMS * 2
NOISE_SCALE = 0.7 / 32          # must match gen_corpus.py

# ---------------------------------------------------------------------------
# Wire protocol: the bytes that would cross PCIe.
#
# REQUEST  (host -> device):
#   magic  u32 = 0x43534431 ("CSD1")
#   k      u32
#   nprobe u32
#   probe cluster ids: u32 * nprobe
#   query vector: fp16 * DIMS
# RESPONSE (device -> host), per candidate, nprobe*k candidates:
#   global id u64 | score fp32 | vector fp16*DIMS
# Returning the winning vectors (not just ids) mirrors real retrieval, and
# is what the article's ~300 KB figure assumes: 160 * 2060 B ~= 322 KB.
# ---------------------------------------------------------------------------
MAGIC = 0x43534431
REQ_FMT = f"<III{NPROBE}I"
CAND_BYTES = 8 + 4 + VEC_BYTES


def pack_request(query_fp16: np.ndarray, probe_ids: np.ndarray, k: int) -> bytes:
    head = struct.pack(REQ_FMT, MAGIC, k, len(probe_ids), *probe_ids.tolist())
    return head + query_fp16.tobytes()


def unpack_request(buf: bytes):
    head_sz = struct.calcsize(REQ_FMT)
    magic, k, nprobe, *probe = struct.unpack(REQ_FMT, buf[:head_sz])
    assert magic == MAGIC, "bad request magic"
    q = np.frombuffer(buf[head_sz:], dtype=np.float16).astype(np.float32)
    return q, np.array(probe[:nprobe], dtype=np.int64), k


def pack_candidates(ids, scores, vectors) -> bytes:
    out = bytearray()
    for i, s, v in zip(ids, scores, vectors):
        out += struct.pack("<qf", int(i), float(s)) + v.tobytes()
    return bytes(out)


def unpack_candidates(buf: bytes):
    n = len(buf) // CAND_BYTES
    ids, scores = np.empty(n, np.int64), np.empty(n, np.float32)
    for j in range(n):
        off = j * CAND_BYTES
        ids[j], scores[j] = struct.unpack_from("<qf", buf, off)
    return ids, scores


# ---------------------------------------------------------------------------
# Device-side computation: the functional spec an FPGA kernel must match.
# Given the raw fp16 bytes of ONE cluster, return its top-k by dot product.
# ---------------------------------------------------------------------------
def device_score_cluster(raw: bytes, q32: np.ndarray, global_start: int, k: int):
    block = np.frombuffer(raw, dtype=np.float16).reshape(-1, DIMS)
    scores = block.astype(np.float32) @ q32
    part = np.argpartition(scores, -k)[-k:]
    order = part[np.argsort(scores[part])[::-1]]
    ids = global_start + order.astype(np.int64)
    return ids, scores[order], block[order]


def run_device_process(corpus_dir: str):
    """Entry point for the simulated device subprocess. Owns the corpus file;
    speaks only the wire protocol on stdin/stdout."""
    offsets = np.load(os.path.join(corpus_dir, "offsets.npy"))
    path = os.path.join(corpus_dir, "corpus.bin")
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    req_len = struct.unpack("<I", stdin.read(4))[0]
    q32, probe, k = unpack_request(stdin.read(req_len))
    out = bytearray()
    with open(path, "rb", buffering=0) as f:
        for c in probe:
            start, end = int(offsets[c]), int(offsets[c + 1])
            f.seek(start * VEC_BYTES)
            need = (end - start) * VEC_BYTES
            raw = b""
            while len(raw) < need:
                chunk = f.read(need - len(raw))
                if not chunk:
                    break
                raw += chunk
            ids, scores, vecs = device_score_cluster(raw, q32, start, k)
            out += pack_candidates(ids, scores, vecs)
    stdout.write(struct.pack("<I", len(out)) + bytes(out))
    stdout.flush()


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class SimulatedDevice:
    """Reference backend: correct answers and true protocol byte counts.
    Timing through this backend is NOT a hardware claim."""

    def __init__(self, corpus_dir):
        self.proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--device-process",
             "--dir", corpus_dir],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def query(self, request: bytes) -> bytes:
        self.proc.stdin.write(struct.pack("<I", len(request)) + request)
        self.proc.stdin.flush()
        resp_len = struct.unpack("<I", self.proc.stdout.read(4))[0]
        return self.proc.stdout.read(resp_len)


class HardwareDevice:
    """Plug real computational storage in here.

    For a Xilinx SmartSSD: implement device_score_cluster as a Vitis HLS
    kernel (fp16 dot products + top-k, streamed across NAND channels), move
    pack/unpack to XRT buffer I/O, and keep the wire format above so the
    harness's byte accounting and verification still apply.
    """

    def __init__(self, corpus_dir):
        raise NotImplementedError(
            "No computational-storage hardware attached. "
            "Implement query(request)->response against your device SDK.")


# ---------------------------------------------------------------------------
# Host harness
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"D:\aissd-bench")
    ap.add_argument("--backend", choices=["sim", "hardware"], default="sim")
    ap.add_argument("--device-process", action="store_true",
                    help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.device_process:
        run_device_process(args.dir)
        return

    centroids = np.load(os.path.join(args.dir, "centroids.npy"))
    rng = np.random.default_rng(7)                      # same query as A/B
    target = int(rng.integers(0, len(centroids) // 4))
    query = (centroids[target]
             + NOISE_SCALE * rng.standard_normal(DIMS).astype(np.float32))
    query /= np.linalg.norm(query)
    q32 = query.astype(np.float32)

    probe = np.argsort(centroids @ q32)[::-1][:NPROBE].astype(np.uint32)
    request = pack_request(query.astype(np.float16), probe, TOPK)

    backend = (SimulatedDevice if args.backend == "sim" else HardwareDevice)(args.dir)
    t0 = time.time()
    response = backend.query(request)
    elapsed = time.time() - t0

    ids, scores = unpack_candidates(response)
    order = np.argsort(scores)[::-1][:TOPK]
    top_ids = sorted(int(i) for i in ids[order])

    result = {
        "backend": args.backend,
        "bytes_down": len(request),
        "bytes_up": len(response),
        "bus_bytes_total": len(request) + len(response),
        "useful_answer_bytes": TOPK * VEC_BYTES,
        "waste_ratio": round((len(request) + len(response)) / (TOPK * VEC_BYTES), 1),
        "top20_ids": top_ids,
    }
    if args.backend == "sim":
        result["timing_note"] = ("simulation on host CPU — validates protocol "
                                 "and correctness only, NOT a hardware timing claim")
    else:
        result["seconds"] = round(elapsed, 3)

    prior = os.path.join(args.dir, "results.json")
    if os.path.exists(prior):
        with open(prior) as f:
            baseline = json.load(f)
        expect = sorted(baseline["runs"]["naive"]["top20_ids"])
        result["matches_method_a_top20"] = (top_ids == expect)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
