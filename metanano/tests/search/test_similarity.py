"""
File / 文件:
    - metanano/tests/search/test_similarity.py

Overview / 概述:
    Tests for compute_kmer_similarity_precomputed function.
    compute_kmer_similarity_precomputed 函数的测试。

Consumers / 调用方:
    - pytest
"""

import pytest

from metanano.utils.kmer import generate_kmers
from metanano.utils.similarity import (
    compute_kmer_similarity,
    compute_kmer_similarity_precomputed,
)


class TestComputeKmerSimilarityPrecomputed:
    """
    Tests for precomputed k-mer Jaccard similarity.
    预计算 k-mer Jaccard 相似度的测试。
    """

    def test_precomputed_jaccard_matches_standard(
        self,
        query_sequence: str,
        near_identical_sequence: str,
    ) -> None:
        """
        Precomputed variant returns same value as standard compute_kmer_similarity.
        预计算变体返回与标准 compute_kmer_similarity 相同的值。
        """
        k = 5
        kmers_a = generate_kmers(query_sequence, k)
        kmers_b = generate_kmers(near_identical_sequence, k)

        precomputed = compute_kmer_similarity_precomputed(kmers_a, kmers_b)
        standard = compute_kmer_similarity(query_sequence, near_identical_sequence, k)

        assert precomputed == pytest.approx(standard)

    def test_precomputed_empty_sets(self) -> None:
        """
        Both empty sets returns 0.0.
        两个空集返回 0.0。
        """
        result = compute_kmer_similarity_precomputed(set(), set())
        assert result == 0.0

    def test_precomputed_identical_sets(self, query_sequence: str) -> None:
        """
        Identical k-mer sets return 1.0.
        相同的 k-mer 集返回 1.0。
        """
        kmers = generate_kmers(query_sequence, 5)
        result = compute_kmer_similarity_precomputed(kmers, kmers)
        assert result == 1.0
