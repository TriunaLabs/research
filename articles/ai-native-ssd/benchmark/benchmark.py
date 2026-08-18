"""Data-movement benchmark: naive full-scan retrieval vs index-guided retrieval.

Same query, same top-20 answer, two data-movement strategies:
  A) Naive: stream the entire corpus from SSD to CPU, score everything.
  B) Index-guided: score 1024 centroids (a few KB), read only the nprobe
     nearest clusters from SSD, score those.

Ordering note: B runs FIRST on clusters chosen from the LOW half of the file.
The corpus (102 GB) is 2.5x RAM, and generation ended by writing the file's
tail, so the standby cache holds recent (high-offset) pages; low-offset
clusters are cold. A then streams the whole file (all cold reads dominate).

Reports bytes moved, wall time, effective bandwidth, recall@20, and the
bytes-moved : useful-answer ratio.
"""
import numpy as np
import time
import os
import json

DIR = r"D:\aissd-bench"
DIMS = 1024
TOPK = 20
NPROBE = 8
READ_CHUNK_VECS = 2_000_000          # ~4 GB per chunk for the full scan
NOISE_SCALE = 0.7 / 32      # must match gen_corpus.py

centroids = np.load(os.path.join(DIR, "centroids.npy"))          # fp32 (1024,1024)
offsets = np.load(os.path.join(DIR, "offsets.npy"))              # int64 (1025,)
path = os.path.join(DIR, "corpus.bin")
n_total = int(offsets[-1])
vec_bytes = DIMS * 2
file_bytes = n_total * vec_bytes
assert os.path.getsize(path) == file_bytes, "corpus size mismatch"

# ---- Query: a perturbed member of a cluster from the LOW half of the file ----
rng = np.random.default_rng(7)
target_cluster = int(rng.integers(0, len(centroids) // 4))       # low file offset => cold
query = (centroids[target_cluster]
         + NOISE_SCALE * rng.standard_normal(DIMS).astype(np.float32))
query /= np.linalg.norm(query)
q32 = query.astype(np.float32)

def read_exact(f, n):
    """Read exactly n bytes (or fewer only at EOF); unbuffered reads may return short."""
    parts = []
    got = 0
    while got < n:
        chunk = f.read(n - got)
        if not chunk:
            break
        parts.append(chunk)
        got += len(chunk)
    return b"".join(parts)

def topk_merge(scores, ids, k=TOPK):
    part = np.argpartition(scores, -k)[-k:]
    order = part[np.argsort(scores[part])[::-1]]
    return scores[order], ids[order]

results = {}

# =====================  B) INDEX-GUIDED (runs first: cold)  =====================
t0 = time.time()
cscores = centroids @ q32                                        # 1024 dots
probe = np.argsort(cscores)[::-1][:NPROBE]
t_index = time.time() - t0

bytes_read_b = 0
best_s = np.empty(0, dtype=np.float32)
best_i = np.empty(0, dtype=np.int64)
t0 = time.time()
with open(path, "rb", buffering=0) as f:
    for c in probe:
        start, end = int(offsets[c]), int(offsets[c + 1])
        f.seek(start * vec_bytes)
        raw = read_exact(f, (end - start) * vec_bytes)
        bytes_read_b += len(raw)
        block = np.frombuffer(raw, dtype=np.float16).reshape(-1, DIMS).astype(np.float32)
        s = block @ q32
        ids = np.arange(start, end, dtype=np.int64)
        alls = np.concatenate([best_s, s]); alli = np.concatenate([best_i, ids])
        best_s, best_i = topk_merge(alls, alli)
t_b = time.time() - t0
results["indexed"] = {
    "seconds": round(t_b + t_index, 3),
    "bytes_moved": bytes_read_b + centroids.nbytes,
    "gb_moved": round((bytes_read_b + centroids.nbytes) / 1e9, 3),
    "effective_GBps": round(bytes_read_b / 1e9 / t_b, 2),
    "clusters_read": NPROBE,
    "top20_ids": best_i.tolist(),
}
print("B) index-guided:", json.dumps(results["indexed"], indent=2), flush=True)

# =====================  A) NAIVE FULL SCAN  =====================
bytes_read_a = 0
best_s2 = np.empty(0, dtype=np.float32)
best_i2 = np.empty(0, dtype=np.int64)
t0 = time.time()
with open(path, "rb", buffering=0) as f:
    idx = 0
    while True:
        raw = read_exact(f, READ_CHUNK_VECS * vec_bytes)
        if not raw:
            break
        bytes_read_a += len(raw)
        block = np.frombuffer(raw, dtype=np.float16).reshape(-1, DIMS).astype(np.float32)
        s = block @ q32
        ids = np.arange(idx, idx + block.shape[0], dtype=np.int64)
        idx += block.shape[0]
        alls = np.concatenate([best_s2, s]); alli = np.concatenate([best_i2, ids])
        best_s2, best_i2 = topk_merge(alls, alli)
t_a = time.time() - t0
results["naive"] = {
    "seconds": round(t_a, 3),
    "bytes_moved": bytes_read_a,
    "gb_moved": round(bytes_read_a / 1e9, 3),
    "effective_GBps": round(bytes_read_a / 1e9 / t_a, 2),
    "top20_ids": best_i2.tolist(),
}
print("A) naive full scan:", json.dumps(results["naive"], indent=2), flush=True)

# =====================  COMPARISON  =====================
recall = len(set(results["indexed"]["top20_ids"]) & set(results["naive"]["top20_ids"])) / TOPK
useful_bytes = TOPK * vec_bytes
summary = {
    "corpus_vectors": n_total,
    "corpus_gb": round(file_bytes / 1e9, 1),
    "recall_at_20_vs_naive": recall,
    "useful_answer_bytes": useful_bytes,
    "naive_waste_ratio": round(bytes_read_a / useful_bytes),
    "indexed_waste_ratio": round(bytes_read_b / useful_bytes),
    "movement_reduction_x": round(bytes_read_a / bytes_read_b, 1),
    "speedup_x": round(t_a / (t_b + t_index), 1),
}
print("SUMMARY:", json.dumps(summary, indent=2), flush=True)
with open(os.path.join(DIR, "results.json"), "w") as f:
    json.dump({"summary": summary, "runs": results}, f, indent=2)
