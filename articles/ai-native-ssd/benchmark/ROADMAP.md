# Benchmark roadmap

The article states five falsifiable hypotheses (H1-H5). This is the experimental
program for attacking the ones attackable without computational-storage hardware,
in priority order. The invariant across all of it: **the process-isolated device
+ narrow wire protocol pattern from `method_c.py` is what makes the byte counts
honest. Every experiment reuses it.** Every run emits the `metrics.py` triple
(bytes touched on storage / bytes crossed the boundary / bytes actually useful)
so results stay comparable.

Platform note: this runs on Windows 11. Linux-flavored advice translates as:
cgroup CPU caps -> `psutil` CPU affinity + capped BLAS thread env; cgroup memory
caps -> policed RSS (reported, violations flagged) or a Job Object; RAPL ->
not available; use CPU package power via LibreHardwareMonitor or a wall-power
meter when energy runs start. Until then runs record wall time and per-process
CPU seconds, and energy claims stay out of the results.

## 1. Constrained-device crossover sweep - `constrained_sweep.py` (DONE, first pass: see [sweep-results.md](sweep-results.md))

Attacks **H1**, informs **H2**. Method B (host, unconstrained) vs the Method C
simulation under device-like constraints: 2 cores, policed 1.5 GB RAM budget,
compute tax throttling effective FLOP rate. Sweeps nprobe x tax, alternating
run order so cold and page-cache-warm reads are distinguishable.

Measured finding from first runs: the 2-core NumPy sim's natural scoring rate is
~0.6 GFLOP/s, far below drive bandwidth (scoring 2 flop/byte at the drive's
2.1 GB/s requires ~4.2 GFLOP/s to be I/O-bound). So the sim cannot reach the
crossover from below; instead, fit wall = overhead + FLOP/rate to the taxed
points and derive the parity rate against Method B. The deliverable is that
curve: the minimum device compute rate at which in-device selection matches
host-side selection, per nprobe.

## 2. Multi-query temporal locality (NEXT)

Tests the transferability of SolidAttention's observation (~81% block-selection
overlap between consecutive iterations) to the retrieval plane. Extend the
device process to serve a *sequence* of 50-200 queries with drifting topics and
overlapping probe sets; give the device a small, explicitly-budgeted hot-cluster
cache (a few hundred MB, counted against the RAM cap) and a trivial predictor.
Measure cumulative boundary bytes and device-cache hit rate vs the no-cache
baseline. Requires a multi-request framing on the wire protocol (length-prefixed
request loop; protocol bytes still counted per request).

Honesty note: the OS page cache already acts as an implicit device cache for
repeated reads. The device must therefore report bytes *requested from media*
and the run must report read bandwidth per cluster so cache-served reads are
identifiable. Reads over ~3 GB/s on this drive came from RAM, not NAND.

## 3. MoE expert streaming - `moe_bench/` (AFTER 2; tests H4 directly)

Small synthetic MoE: 8-16 experts per layer, packed 4-bit weights on disk,
device process owns the weight file. Host sends the router's expert IDs per
token (the routing metadata whose size H4 claims stays small); device returns
packed expert tensors, optionally with hotness filtering / speculative
prefetch. Measure: bytes of routing metadata down, bytes of experts up, vs
total parameter bytes; expert-cache hit rate under realistic activation skew
(Zipf-ish, matching kimi-k3-in-c's observed hot/cold split). No model quality
needed; weights can be random. Reuses the process pattern nearly unchanged.

## 4. KV-block hierarchy - `kv_bench/` (LARGEST; likely its own article)

Simulates the HillInfer/SolidAttention division of labor. Device process owns
on-disk KV blocks; protocol: `lookup_prefix`, `score_and_select`,
`fetch_blocks`, `evict`. Two modes: host scores importance vs device scores
locally and returns winners. Needs a workload generator (synthetic long-context
traces with high prefix reuse; real vLLM/llama.cpp traces if available). This
is a second article's worth of scope; do not fold it into revisions of the
first.

## Non-goals

* **No five-plane simulation.** The planes are the article's speculative layer;
  simulating our own speculation produces numbers that look like evidence and
  are not. Experiments target the load-bearing claims only.
* **No energy numbers until there is a meter.** Wall time and CPU seconds are
  recorded now; joules wait for package-power sampling or a wall meter, clearly
  labeled either way.
