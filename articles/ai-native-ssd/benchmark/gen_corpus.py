"""Generate a clustered embedding corpus for the data-movement benchmark.

Default: 50M vectors x 1024 dims, fp16, grouped by cluster (IVF layout).
Outputs:
  corpus.bin      - vectors, cluster-contiguous, fp16          (~102.4 GB)
  centroids.npy   - n_clusters x dims fp32 cluster centroids
  offsets.npy     - int64 start index of each cluster in corpus.bin

The test suite calls generate() with a tiny configuration (~40 MB) so the
whole pipeline is verifiable without the full corpus.
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


def generate(out_dir, n_vectors=N_VECTORS, dims=DIMS, n_clusters=N_CLUSTERS,
             noise_scale=NOISE_SCALE, seed=42, chunk=CHUNK, log=print):
    rng = np.random.default_rng(seed)

    # Cluster centroids on the unit sphere-ish
    centroids = rng.standard_normal((n_clusters, dims), dtype=np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    np.save(os.path.join(out_dir, "centroids.npy"), centroids)

    # Cluster sizes: roughly equal with mild variation
    base = n_vectors // n_clusters
    sizes = np.full(n_clusters, base, dtype=np.int64)
    sizes[: n_vectors - base * n_clusters] += 1
    offsets = np.zeros(n_clusters + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(sizes)
    np.save(os.path.join(out_dir, "offsets.npy"), offsets)

    t0 = time.time()
    written = 0
    path = os.path.join(out_dir, "corpus.bin")
    with open(path, "wb", buffering=1024 * 1024 * 8) as f:
        for c in range(n_clusters):
            n = int(sizes[c])
            done = 0
            while done < n:
                m = min(chunk, n - done)
                block = centroids[c] + noise_scale * rng.standard_normal((m, dims), dtype=np.float32)
                f.write(block.astype(np.float16).tobytes())
                done += m
                written += m
            if c % 64 == 0 and log:
                el = time.time() - t0
                gb = written * dims * 2 / 1e9
                log(f"cluster {c}/{n_clusters}  {gb:.1f} GB  {el:.0f}s  {gb/max(el,1e-9):.2f} GB/s", flush=True)

    el = time.time() - t0
    if log:
        log(f"DONE: {written} vectors, {written*dims*2/1e9:.1f} GB in {el:.0f}s", flush=True)
    return path


if __name__ == "__main__":
    generate(OUT_DIR)
