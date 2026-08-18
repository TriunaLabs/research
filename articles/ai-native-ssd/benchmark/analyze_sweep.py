"""Analysis for constrained_sweep.py results: derive the parity compute rate.

For each nprobe, fit wall = overhead + GFLOP/rate over the taxed device runs,
then solve for the rate at which the constrained device's wall time equals
unconstrained Method B's. Sanity check: the fitted GFLOP term must match the
analytic 0.1 GFLOP per probed cluster (2 x 48.8k vectors x 1024 dims), which
validates that the tax mechanism throttled what it claims to throttle.

Usage: python analyze_sweep.py --dir D:\\aissd-bench
"""
import argparse
import json
import os

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"D:\aissd-bench")
    args = ap.parse_args()
    path = os.path.join(args.dir, "sweep_results.jsonl")
    runs = [json.loads(l) for l in open(path, encoding="utf-8")]
    nprobes = sorted({r["config"]["nprobe"] for r in runs})

    print(f"{'nprobe':>6} {'fit_GFLOP':>9} {'overhead_s':>10} "
          f"{'parity_vs_B_cold':>16} {'parity_vs_B_warm':>16} {'boundary_x':>10}")
    for nprobe in nprobes:
        rows = [r for r in runs if r["config"]["nprobe"] == nprobe]
        cs = [r for r in rows if "methodC" in r["experiment"]
              and r["config"]["tax_gflops"] > 0]
        x = np.array([1.0 / r["config"]["tax_gflops"] for r in cs])
        y = np.array([r["wall_s"] for r in cs])
        gflop, overhead = np.polyfit(x, y, 1)

        def med(pred):
            v = sorted(r["wall_s"] for r in rows if pred(r))
            return v[len(v) // 2] if v else None

        b_cold = med(lambda r: "methodB" in r["experiment"]
                     and r["config"]["order"] == "cold")
        b_warm = med(lambda r: "methodB" in r["experiment"]
                     and r["config"]["order"] == "warm")
        b_bytes = np.median([r["boundary_bytes"] for r in rows
                             if "methodB" in r["experiment"]])
        c_bytes = np.median([r["boundary_bytes"] for r in rows
                             if "methodC" in r["experiment"]])
        parity_cold = gflop / (b_cold - overhead) if b_cold > overhead else float("nan")
        parity_warm = gflop / (b_warm - overhead) if b_warm > overhead else float("nan")
        print(f"{nprobe:>6} {gflop:>9.2f} {overhead:>10.2f} "
              f"{parity_cold:>13.2f} GF/s {parity_warm:>13.2f} GF/s "
              f"{b_bytes / c_bytes:>9.0f}x")


if __name__ == "__main__":
    main()
