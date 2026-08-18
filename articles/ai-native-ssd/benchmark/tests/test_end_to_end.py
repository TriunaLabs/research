"""End-to-end smoke test on a tiny corpus: the article's reproduction path,
executable in seconds without the 102 GB corpus. Brute force over the whole
corpus is the independent oracle; Method B and the process-isolated Method C
simulation must both agree with it, and the protocol byte counts must match
their analytic formulas."""
import numpy as np

import constrained_sweep as cs
import metrics
from method_c import DIMS, VEC_BYTES

TOPK = 20
NPROBE = 4


def _query_and_probe(centroids, seed=7):
    rng = np.random.default_rng(seed)
    q32 = cs.make_query(centroids, rng)
    probe = np.argsort(centroids @ q32)[::-1][:NPROBE].astype(np.int64)
    return q32, probe


def test_method_b_matches_brute_force_on_probed_clusters(tiny_corpus, tiny_arrays):
    centroids, offsets, corpus = tiny_arrays
    q32, probe = _query_and_probe(centroids)

    b = cs.method_b(tiny_corpus, offsets, q32, probe, k=TOPK)

    # oracle: brute force over the probed clusters via the in-memory copy
    mask_ids = np.concatenate([np.arange(int(offsets[c]), int(offsets[c + 1]))
                               for c in probe])
    scores = corpus[mask_ids].astype(np.float32) @ q32
    expect = sorted(int(i) for i in mask_ids[np.argsort(scores)[::-1][:TOPK]])
    assert b["top_ids"] == expect
    assert b["bytes_read"] == sum(int(offsets[c + 1] - offsets[c]) * VEC_BYTES
                                  for c in probe)


def test_index_guided_recall_against_full_corpus(tiny_arrays):
    """The tiny corpus preserves the property the article's benchmark relies
    on: probing a handful of clusters recovers the global top-20 exactly."""
    centroids, offsets, corpus = tiny_arrays
    q32, probe = _query_and_probe(centroids)

    full = corpus.astype(np.float32) @ q32
    global_top = set(int(i) for i in np.argsort(full)[::-1][:TOPK])

    mask_ids = np.concatenate([np.arange(int(offsets[c]), int(offsets[c + 1]))
                               for c in probe])
    scores = corpus[mask_ids].astype(np.float32) @ q32
    probed_top = set(int(i) for i in mask_ids[np.argsort(scores)[::-1][:TOPK]])
    assert probed_top == global_top, "recall@20 must be 1.0 on the tiny corpus"


def test_method_c_process_boundary(tiny_corpus, tiny_arrays):
    """Spawn the real device subprocess against the tiny corpus and verify
    correctness plus every byte-count the article's figures are built from."""
    centroids, offsets, _ = tiny_arrays
    q32, probe = _query_and_probe(centroids)

    b = cs.method_b(tiny_corpus, offsets, q32, probe, k=TOPK)
    c = cs.method_c_constrained(tiny_corpus, q32, probe, tax_gflops=0.0,
                                cores=1, k=TOPK)

    assert c["top_ids"] == b["top_ids"]
    assert c["bytes_down"] == 12 + 4 * NPROBE + DIMS * 2
    assert c["bytes_up"] == 4 + NPROBE * TOPK * (8 + 4 + DIMS * 2)
    acct = c["acct"]
    assert acct["device_bytes_read"] == b["bytes_read"]
    assert acct["device_macs"] == b["bytes_read"] // VEC_BYTES * DIMS


def test_compute_tax_binds(tiny_corpus, tiny_arrays):
    """A tax far below natural rate must stretch wall time via device sleep."""
    centroids, _, _ = tiny_arrays
    q32, probe = _query_and_probe(centroids)
    taxed = cs.method_c_constrained(tiny_corpus, q32, probe,
                                    tax_gflops=0.05, cores=1, k=TOPK)
    acct = taxed["acct"]
    required = 2 * acct["device_macs"] / (0.05 * 1e9)
    assert acct["device_sleep_s"] > 0
    assert acct["device_score_s"] + acct["device_sleep_s"] >= required * 0.9


def test_metrics_triple():
    run = metrics.make_run("t", {"x": 1}, storage_bytes_read=1000,
                           boundary_down=10, boundary_up=90,
                           useful_bytes=10, wall_s=0.5)
    assert run["boundary_bytes"] == 100
    assert run["boundary_waste_ratio"] == 10.0
    assert run["storage_waste_ratio"] == 100.0
