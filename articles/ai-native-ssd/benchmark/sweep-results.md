# Constrained-device crossover sweep: first results

*Run 2026-08-18 on the same hardware as the article's benchmark (laptop, 40 GB
RAM, WD_BLACK SN7100, same 102.4 GB / 50M-vector corpus). Raw per-run data:
[`sweep_results.jsonl`](sweep_results.jsonl); harness:
[`constrained_sweep.py`](constrained_sweep.py); analysis:
[`analyze_sweep.py`](analyze_sweep.py).*

## Setup

Method B (host-side selection, unconstrained) vs the Method C simulated device
under device-like constraints: 2-core CPU affinity with BLAS threads capped, a
policed 1.5 GB RAM budget (peak observed ~333 MB; never violated), and a
compute tax throttling effective scoring rate. 6 fresh random queries per
nprobe in {4, 8, 16, 32}, taxes in {natural ~0.6, 0.4, 0.2, 0.1} GFLOP/s,
alternating run order so both methods see cold and page-cache-warm reads.
Every device run's top-20 was verified identical to Method B's on the same
query (0 mismatches, 0 rank ties in 120 device runs).

## Results

Median wall seconds; boundary = bytes crossing the host/device boundary.

| nprobe | B host (cold) | C sim natural (cold) | boundary B | boundary C | reduction |
|-------:|--------------:|---------------------:|-----------:|-----------:|----------:|
|      4 |          0.90 |                 1.40 |     400 MB |     167 KB |    2,397x |
|      8 |          1.93 |                 2.03 |     800 MB |     332 KB |    2,412x |
|     16 |          3.56 |                 3.65 |    1.60 GB |     661 KB |    2,419x |
|     32 |          8.14 |                 7.35 |    3.20 GB |    1.32 MB |    2,423x |

Fitting wall = overhead + GFLOP/rate over the taxed runs (the fitted GFLOP
term reproduces the analytic 0.1 GFLOP per probed cluster exactly, validating
the throttle) and solving for parity with Method B:

| nprobe | fitted GFLOP | overhead s | parity rate vs B cold | vs B warm |
|-------:|-------------:|-----------:|----------------------:|----------:|
|      4 |         0.39 |       0.74 |             2.45 GF/s | 2.49 GF/s |
|      8 |         0.80 |       0.89 |             0.77 GF/s | 0.98 GF/s |
|     16 |         1.60 |       1.31 |             0.71 GF/s | 0.80 GF/s |
|     32 |         3.20 |       2.21 |             0.54 GF/s | 0.76 GF/s |

## What this says about H1

1. **The boundary-bytes reduction is a constant ~2,400x at every scale.** That
   part is protocol arithmetic and transfers to real hardware unchanged.
2. **The parity compute rate falls as the probed set grows**: a device matching
   an unconstrained host needs ~2.5 GFLOP/s at nprobe=4 but only ~0.5-0.8
   GFLOP/s at nprobe=32. This is the direction H1 predicts: the margin moves
   toward the device as the workload grows relative to the interconnect.
3. **Even this deliberately weak device reaches wall-time parity** at nprobe
   8-16 and wins outright at nprobe=32 (7.35 s vs 8.14 s cold) while moving
   2,400x fewer bytes.

## What this does NOT say

* **Method B here is NumPy, not a tuned host.** A FAISS/AVX-512 host scores
  this workload far faster, raising the parity bar by possibly one to two
  orders of magnitude. SmartSSD-class FPGAs stream fp16 dot products in the
  tens-to-hundreds of GFLOP/s, so the bar likely stays reachable, but that
  comparison has not been run. This is the next refinement worth making.
* **The simulated device reads through the same OS and NAND path as the
  host.** Real device-internal bandwidth (across NAND channels, no PCIe) would
  differ in the device's favor; nothing here measures that.
* **Process-spawn overhead (~0.3 s) is a simulation artifact** included in the
  overhead term; a real device does not fork per query.
* **No energy numbers.** Wall time and CPU seconds only, per the roadmap.

## Protocol finding worth keeping

The sweep's correctness gate caught a real protocol subtlety on its first run:
the wire format carries the query as fp16, so a device scores slightly
different bits than a host holding the fp32 original, and two candidates
1e-6 apart at rank 20 swapped because of it. Fix in the harness: quantize the
query once so both sides score identical bits. Implication for real systems:
**query quantization on the wire is a correctness boundary the host must
account for when validating device-side selection.**
