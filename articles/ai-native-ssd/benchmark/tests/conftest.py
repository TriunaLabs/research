import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gen_corpus  # noqa: E402

TINY_VECTORS = 20_000
TINY_CLUSTERS = 32


@pytest.fixture(scope="session")
def tiny_corpus(tmp_path_factory):
    """A ~40 MB corpus built by the real generator: 20k vectors, 32 clusters,
    full 1024 dims (the wire protocol fixes DIMS, so only counts shrink)."""
    d = tmp_path_factory.mktemp("tiny-corpus")
    gen_corpus.generate(str(d), n_vectors=TINY_VECTORS,
                        n_clusters=TINY_CLUSTERS, log=None)
    return str(d)


@pytest.fixture(scope="session")
def tiny_arrays(tiny_corpus):
    centroids = np.load(os.path.join(tiny_corpus, "centroids.npy"))
    offsets = np.load(os.path.join(tiny_corpus, "offsets.npy"))
    corpus = np.fromfile(os.path.join(tiny_corpus, "corpus.bin"),
                         dtype=np.float16).reshape(-1, 1024)
    return centroids, offsets, corpus
