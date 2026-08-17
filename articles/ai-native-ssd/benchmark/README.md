# Data-Movement Benchmark

The measurement behind the "A Measurement Anyone Can Reproduce" section of
[the article](../README.md): one top-20 similarity query over a 102.4 GB
embedding corpus, answered two ways — naive full scan vs. index-guided reads —
to measure the gap between bytes *moved* and bytes *needed*.

## Results (as measured)

Hardware: consumer laptop, 40 GB RAM, WD_BLACK SN7100 2 TB NVMe
(PCIe Gen4; ~2.1 GB/s measured sequential read on this machine).

| | Naive full scan | Index-guided |
| --- | --- | --- |
| Data moved | 102.4 GB | 0.80 GB |
| Wall time | 355 s | 1.6 s |
| Top-20 answer | baseline | identical (recall@20 = 1.0) |
| Bytes moved per useful byte | ~2,500,000 : 1 | ~19,500 : 1 |

Raw numbers: [results.json](results.json).

## Reproduce it

Requirements: Python 3.11+, NumPy, and **~103 GB of free disk** on a drive
you want to measure. The corpus is deliberately generated larger than RAM so
the OS page cache cannot serve the scans from memory — on a machine with more
than ~50 GB RAM, scale `N_VECTORS` up accordingly.

```bash
# 1. Edit OUT_DIR in both scripts to a path on the target drive, then:
python gen_corpus.py     # ~15-20 min (RNG-bound), writes 102.4 GB
python benchmark.py      # ~6 min, prints both runs + summary JSON
python rawread.py        # optional: raw sequential-read bandwidth baseline
```

The corpus is deterministic (seeded RNG); delete `corpus.bin` afterwards to
reclaim the disk space.

## Method notes

- 50M synthetic embeddings, 1024-dim fp16, generated as 1,024 clusters
  (noise norm ~0.7 vs. unit centroids) and stored cluster-contiguous
  (IVF-style layout).
- The index-guided query runs **first**, against clusters in the low half of
  the file — the page cache holds only the just-written file tail, so those
  reads are cold. The full scan is cold by construction (file is 2.5x RAM).
- The naive scan's effective throughput (~0.29 GB/s) is well below the
  drive's raw read speed because the host must receive *and* score every
  byte — that gap is part of the point.
- This is a software index on a host CPU, not computational storage. It
  measures the size of the prize (the movement-waste ratio), not an
  in-storage compute implementation.

## Honest limitations

One query shape, synthetic clustered data, a single consumer drive, no
energy instrumentation (the article's energy figures use published
pJ/bit-class constants, clearly hedged). The orders of magnitude, not the
exact digits, are the finding.
