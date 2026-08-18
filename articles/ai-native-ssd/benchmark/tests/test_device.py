"""Device-side computation: the functional spec an FPGA kernel must match."""
import numpy as np

from method_c import DIMS, device_score_cluster


def test_matches_brute_force_reference():
    rng = np.random.default_rng(3)
    block = rng.standard_normal((500, DIMS)).astype(np.float16)
    q32 = rng.standard_normal(DIMS).astype(np.float32)
    start, k = 10_000, 20

    ids, scores, vecs = device_score_cluster(block.tobytes(), q32, start, k)

    ref = block.astype(np.float32) @ q32
    ref_order = np.argsort(ref)[::-1][:k]
    np.testing.assert_array_equal(ids, start + ref_order.astype(np.int64))
    np.testing.assert_array_equal(scores, ref[ref_order])
    np.testing.assert_array_equal(vecs, block[ref_order])
    assert all(scores[i] >= scores[i + 1] for i in range(k - 1))


def test_fp16_query_quantization_is_a_correctness_boundary():
    """Regression for the bug the first sweep caught: the wire carries the
    query as fp16, so a host scoring the fp32 original computes a different
    function than the device, and rank-k near-ties can legitimately flip.
    Pin both facts: quantization changes scores, and scoring the round-tripped
    query reproduces the device's arithmetic bitwise."""
    rng = np.random.default_rng(4)
    q32 = rng.standard_normal(DIMS).astype(np.float32)
    q16_32 = q32.astype(np.float16).astype(np.float32)
    assert not np.array_equal(q32, q16_32), "fp16 round-trip must quantize"

    block = rng.standard_normal((100, DIMS)).astype(np.float16)
    scores_fp32_query = block.astype(np.float32) @ q32
    scores_fp16_query = block.astype(np.float32) @ q16_32
    assert not np.array_equal(scores_fp32_query, scores_fp16_query)

    _, device_scores, _ = device_score_cluster(block.tobytes(), q16_32, 0, 100)
    np.testing.assert_array_equal(np.sort(device_scores),
                                  np.sort(scores_fp16_query))
