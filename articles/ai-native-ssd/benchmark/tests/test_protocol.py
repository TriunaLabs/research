"""Wire-protocol invariants: the byte counts in the article are these formulas."""
import numpy as np
import pytest

from method_c import (CAND_BYTES, DIMS, VEC_BYTES, pack_candidates,
                      pack_request, unpack_candidates, unpack_request)


@pytest.mark.parametrize("nprobe", [1, 4, 8, 32])
def test_request_round_trip(nprobe):
    rng = np.random.default_rng(0)
    q16 = rng.standard_normal(DIMS).astype(np.float16)
    probe = rng.choice(1024, size=nprobe, replace=False).astype(np.uint32)
    buf = pack_request(q16, probe, k=20)

    # the article's bytes-down figure is this exact formula
    assert len(buf) == 12 + 4 * nprobe + VEC_BYTES

    q32, probe_out, k = unpack_request(buf)
    assert k == 20
    assert probe_out.tolist() == probe.tolist()
    np.testing.assert_array_equal(q32, q16.astype(np.float32))


def test_published_nprobe8_request_size():
    """The article states 2,092 bytes down: 12 header + 32 probe + 2048 query."""
    rng = np.random.default_rng(1)
    buf = pack_request(rng.standard_normal(DIMS).astype(np.float16),
                       np.arange(8, dtype=np.uint32), k=20)
    assert len(buf) == 2092


def test_candidates_round_trip():
    rng = np.random.default_rng(2)
    n = 160                                   # nprobe=8 x k=20
    ids = rng.integers(0, 50_000_000, size=n).astype(np.int64)
    scores = rng.standard_normal(n).astype(np.float32)
    vecs = rng.standard_normal((n, DIMS)).astype(np.float16)
    buf = pack_candidates(ids, scores, vecs)

    # the article's ~322 KB bytes-up figure is this exact formula
    assert len(buf) == n * CAND_BYTES == 160 * 2060

    ids_out, scores_out = unpack_candidates(buf)
    np.testing.assert_array_equal(ids_out, ids)
    np.testing.assert_array_equal(scores_out, scores)
