"""Generate a clustered embedding corpus for the data-movement benchmark.

50M vectors x 1024 dims, fp16, grouped by cluster (IVF layout).
Outputs:
  corpus.bin      - vectors, cluster-contiguous, fp16          (~102.4 GB)
  centroids.npy   - 1024 x 1024 fp32 cluster centroids
  offsets.npy     - int64 start index of each cluster in corpus.bin
"""
import numpy as np
import time
import os

OUT_DIR = r"D:\aissd-bench"
N_VECTORS = 50_000_000
DIMS = 1024
N_CLUSTERS = 1024
NOISE_SCALE = 0.7 / 32      # noise NORM ~0.7 vs centroid norm 1.0 (0.7/sqrt(1024) per-dim)
CHUNK = 500_000             # vectors per write chunk

rng = np.random.default_rng(42)

# Cluster centroids on the unit sphere-ish
centroids = rng.standard_normal((N_CLUSTERS, DIMS), dtype=np.float32)
centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
np.save(os.path.join(OUT_DIR, "centroids.npy"), centroids)

# Cluster sizes: roughly equal with mild variation
base = N_VECTORS // N_CLUSTERS
sizes = np.full(N_CLUSTERS, base, dtype=np.int64)
sizes[: N_VECTORS - base * N_CLUSTERS] += 1
offsets = np.zeros(N_CLUSTERS + 1, dtype=np.int64)
offsets[1:] = np.cumsum(sizes)
np.save(os.path.join(OUT_DIR, "offsets.npy"), offsets)

t0 = time.time()
written = 0
path = os.path.join(OUT_DIR, "corpus.bin")
with open(path, "wb", buffering=1024 * 1024 * 8) as f:
    for c in range(N_CLUSTERS):
        n = int(sizes[c])
        done = 0
        while done < n:
            m = min(CHUNK, n - done)
            block = centroids[c] + NOISE_SCALE * rng.standard_normal((m, DIMS), dtype=np.float32)
            f.write(block.astype(np.float16).tobytes())
            done += m
            written += m
        if c % 64 == 0:
            el = time.time() - t0
            gb = written * DIMS * 2 / 1e9
            print(f"cluster {c}/{N_CLUSTERS}  {gb:.1f} GB  {el:.0f}s  {gb/max(el,1e-9):.2f} GB/s", flush=True)

el = time.time() - t0
print(f"DONE: {written} vectors, {written*DIMS*2/1e9:.1f} GB in {el:.0f}s", flush=True)
