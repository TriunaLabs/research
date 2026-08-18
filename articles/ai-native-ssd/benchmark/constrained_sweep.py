"""Experiment 1: constrained-device crossover sweep (attacks H1, informs H2).

The article's H1 concedes that the 102 GB benchmark narrowed on the host and
predicts device-side narrowing wins by a growing margin. This sweep maps the
crossover surface in simulation: how little compute can the "device" have
before in-device selection stops beating host-side selection (Method B)?

Per trial (fresh random query each time, so cluster reads stay cold):
  * Method B: host reads the probed clusters and scores them, unconstrained.
  * Method C-sim: device process reads and scores the same clusters under a
    constraint set: N cores (CPU affinity + capped BLAS threads), a policed
    RAM budget, and a compute tax throttling effective FLOP rate.
Trial ordering alternates (B first vs C first) so each method gets cold and
page-cache-warm reads in equal measure; per-read bandwidth is recorded so
warm reads are visible (>3 GB/s on this drive means the page cache served it).

What this ESTABLISHES: bytes across the boundary (protocol-counted), wall
time and CPU seconds as a function of device compute budget, and where the
constrained device loses to the host. What it does NOT establish: absolute
hardware timing or joules. A throttled host core is still not an SSD
controller; this is a map of the terrain H1 lives on, not a verdict on it.

Usage:
    python constrained_sweep.py --dir D:\\aissd-bench
    python constrained_sweep.py --dir D:\\aissd-bench --summarize
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import threading
import time

import numpy as np
import psutil

import metrics
from method_c import (DIMS, VEC_BYTES, NOISE_SCALE, pack_request,
                      unpack_candidates)

TOPK = 20
NPROBES = [4, 8, 16, 32]
TAXES = [0.0, 0.4, 0.2, 0.1]        # GFLOP/s; 0 = natural sim rate (~0.6 on
                                    # this laptop at 2 cores; taxes must sit
                                    # below natural or they never bind)
TRIALS = 6
DEVICE_CORES = 2
DEVICE_RAM_CAP = int(1.5 * 2**30)   # policed + reported, not enforced by OS
RESULTS = "sweep_results.jsonl"


def read_exact(f, n):
    parts, got = [], 0
    while got < n:
        chunk = f.read(n - got)
        if not chunk:
            break
        parts.append(chunk)
        got += len(chunk)
    return b"".join(parts)


def make_query(centroids, rng):
    target = int(rng.integers(0, len(centroids)))
    q = centroids[target] + NOISE_SCALE * rng.standard_normal(DIMS).astype(np.float32)
    q /= np.linalg.norm(q)
    return q.astype(np.float32)


def method_b(corpus_dir, offsets, q32, probe, k=TOPK):
    """Host-side selection, unconstrained: read probed clusters, score, top-k."""
    path = os.path.join(corpus_dir, "corpus.bin")
    best_s = np.empty(0, np.float32)
    best_i = np.empty(0, np.int64)
    bytes_read = 0
    cpu0 = time.process_time()
    t0 = time.time()
    with open(path, "rb", buffering=0) as f:
        for c in probe:
            start, end = int(offsets[c]), int(offsets[c + 1])
            f.seek(start * VEC_BYTES)
            raw = read_exact(f, (end - start) * VEC_BYTES)
            bytes_read += len(raw)
            block = np.frombuffer(raw, np.float16).reshape(-1, DIMS).astype(np.float32)
            s = block @ q32
            ids = np.arange(start, end, dtype=np.int64)
            alls = np.concatenate([best_s, s])
            alli = np.concatenate([best_i, ids])
            part = np.argpartition(alls, -k)[-k:]
            order = part[np.argsort(alls[part])[::-1]]
            best_s, best_i = alls[order], alli[order]
    wall = time.time() - t0
    return {
        "top_ids": sorted(int(i) for i in best_i),
        "bytes_read": bytes_read,
        "wall_s": wall,
        "host_cpu_s": time.process_time() - cpu0,
        "read_GBps": round(bytes_read / 1e9 / wall, 2) if wall > 0 else None,
    }


def method_c_constrained(corpus_dir, q32, probe, tax_gflops, cores, k=TOPK):
    """Spawn the device process under constraints, speak the wire protocol,
    return protocol byte counts + the device's self-reported accounting."""
    here = os.path.dirname(os.path.abspath(__file__))
    env = dict(os.environ)
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS"):
        env[var] = str(cores)
    cmd = [sys.executable, os.path.join(here, "method_c.py"), "--device-process",
           "--dir", corpus_dir, "--tax-gflops", str(tax_gflops)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    ps = psutil.Process(proc.pid)
    try:
        ps.cpu_affinity(list(range(cores)))
    except Exception:
        pass

    request = pack_request(q32.astype(np.float16), probe.astype(np.uint32), k)
    t0 = time.time()
    proc.stdin.write(struct.pack("<I", len(request)) + request)
    proc.stdin.flush()

    peak = [0]

    def _sample_rss():
        while proc.poll() is None:
            try:
                peak[0] = max(peak[0], ps.memory_info().rss)
            except psutil.NoSuchProcess:
                return
            time.sleep(0.02)

    sampler = threading.Thread(target=_sample_rss, daemon=True)
    sampler.start()

    resp_len = struct.unpack("<I", proc.stdout.read(4))[0]
    response = proc.stdout.read(resp_len)
    wall = time.time() - t0
    _, err = proc.communicate(timeout=30)
    acct = {}
    for line in err.decode(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                acct = json.loads(line)
            except json.JSONDecodeError:
                pass

    ids, scores = unpack_candidates(response)
    order = np.argsort(scores)[::-1][:k]
    top_ids = sorted(int(i) for i in ids[order])
    rss = acct.get("device_peak_rss") or peak[0]
    return {
        "top_ids": top_ids,
        "bytes_down": len(request),
        "bytes_up": 4 + resp_len,
        "wall_s": wall,
        "device_peak_rss": rss,
        "ram_cap_exceeded": bool(rss and rss > DEVICE_RAM_CAP),
        "acct": acct,
    }


def sweep(corpus_dir):
    centroids = np.load(os.path.join(corpus_dir, "centroids.npy"))
    offsets = np.load(os.path.join(corpus_dir, "offsets.npy"))
    out_path = os.path.join(corpus_dir, RESULTS)
    useful = TOPK * VEC_BYTES
    total = len(NPROBES) * TRIALS
    n = 0
    for nprobe in NPROBES:
        for trial in range(TRIALS):
            n += 1
            rng = np.random.default_rng(1000 * nprobe + trial)
            q32 = make_query(centroids, rng)
            probe = np.argsort(centroids @ q32)[::-1][:nprobe].astype(np.int64)
            c_first = (trial % 2 == 0)
            print(f"[{n}/{total}] nprobe={nprobe} trial={trial} "
                  f"({'C first' if c_first else 'B first'})", flush=True)

            def run_b(order_pos):
                r = method_b(corpus_dir, offsets, q32, probe)
                metrics.emit(out_path, metrics.make_run(
                    "constrained_sweep/methodB",
                    {"nprobe": nprobe, "trial": trial, "order": order_pos},
                    storage_bytes_read=r["bytes_read"],
                    boundary_down=0, boundary_up=r["bytes_read"],
                    useful_bytes=useful, wall_s=r["wall_s"],
                    host_cpu_s=r["host_cpu_s"],
                    extras={"read_GBps": r["read_GBps"]}))
                return r

            def run_c(order_pos, tax):
                r = method_c_constrained(corpus_dir, q32, probe, tax, DEVICE_CORES)
                a = r["acct"]
                metrics.emit(out_path, metrics.make_run(
                    "constrained_sweep/methodC_sim",
                    {"nprobe": nprobe, "trial": trial, "order": order_pos,
                     "tax_gflops": tax, "cores": DEVICE_CORES},
                    storage_bytes_read=a.get("device_bytes_read", 0),
                    boundary_down=r["bytes_down"], boundary_up=r["bytes_up"],
                    useful_bytes=useful, wall_s=r["wall_s"],
                    device_cpu_s=a.get("device_cpu_s"),
                    extras={"device_read_s": a.get("device_read_s"),
                            "device_score_s": a.get("device_score_s"),
                            "device_sleep_s": a.get("device_sleep_s"),
                            "effective_gflops": a.get("effective_gflops"),
                            "device_peak_rss": r["device_peak_rss"],
                            "ram_cap_exceeded": r["ram_cap_exceeded"]}))
                return r

            if c_first:
                c_cold = run_c("cold", TAXES[0])
                b = run_b("warm")
            else:
                b = run_b("cold")
                c_cold = run_c("warm", TAXES[0])
            if c_cold["top_ids"] != b["top_ids"]:
                raise AssertionError(
                    f"correctness violation at nprobe={nprobe} trial={trial}")
            for tax in TAXES[1:]:
                r = run_c("warm", tax)
                if r["top_ids"] != b["top_ids"]:
                    raise AssertionError(
                        f"correctness violation at tax={tax} nprobe={nprobe}")
    print("sweep complete ->", out_path)


def summarize(corpus_dir):
    runs = metrics.load(os.path.join(corpus_dir, RESULTS))
    if not runs:
        print("no results yet")
        return

    def med(vals):
        vals = sorted(v for v in vals if v is not None)
        return vals[len(vals) // 2] if vals else None

    print(f"{'nprobe':>6} {'method':>22} {'wall_s(cold)':>12} {'wall_s(warm)':>12} "
          f"{'boundary_MB':>11} {'waste:1':>9}")
    for nprobe in NPROBES:
        rows = [r for r in runs if r["config"]["nprobe"] == nprobe]
        bs = [r for r in rows if r["experiment"].endswith("methodB")]
        print(f"{nprobe:>6} {'B host (uncap)':>22} "
              f"{med([r['wall_s'] for r in bs if r['config']['order']=='cold']) or '-':>12} "
              f"{med([r['wall_s'] for r in bs if r['config']['order']=='warm']) or '-':>12} "
              f"{med([r['boundary_bytes'] for r in bs])/1e6:>11.1f} "
              f"{med([r['boundary_waste_ratio'] for r in bs]) or '-':>9}")
        for tax in TAXES:
            cs = [r for r in rows if r["experiment"].endswith("methodC_sim")
                  and r["config"]["tax_gflops"] == tax]
            if not cs:
                continue
            label = f"C sim ({'untaxed' if tax == 0 else f'{tax:g} GFLOP/s'})"
            print(f"{'':>6} {label:>22} "
                  f"{med([r['wall_s'] for r in cs if r['config']['order']=='cold']) or '-':>12} "
                  f"{med([r['wall_s'] for r in cs if r['config']['order']=='warm']) or '-':>12} "
                  f"{med([r['boundary_bytes'] for r in cs])/1e6:>11.3f} "
                  f"{med([r['boundary_waste_ratio'] for r in cs]) or '-':>9}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"D:\aissd-bench")
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()
    if args.summarize:
        summarize(args.dir)
    else:
        sweep(args.dir)
        summarize(args.dir)


if __name__ == "__main__":
    main()
