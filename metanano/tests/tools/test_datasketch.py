"""
References / 参考:
    - docs/en/TODO.md: Section 0.6 - datasketch Integration
    - docs/cn/TODO.md: 第0.6节 - datasketch 集成
    - metanano/utils/similarity.py: MinHash implementation
    - metanano/utils/kmer.py: K-mer generation
    - datasketch GitHub: https://github.com/ekzhu/datasketch

File / 文件:
    - metanano/tests/tools/test_datasketch.py

Overview / 概述:
    Pytest tests for datasketch (MinHash similarity) integration.
    datasketch（MinHash 相似度）集成的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. K-mer generation
        2. MinHash creation and comparison
        3. Jaccard similarity computation
        4. Weighted MinHash functionality
        5. Integration with DiversityFilter

    Python API:
    Python API：
        from datasketch import MinHash, MinHashLSH
        mh = MinHash(num_perm=128)
        for kmer in kmers:
            mh.update(kmer.encode('utf8'))

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
from typing import Set

from metanano.utils.kmer import (
    generate_kmers,
    generate_kmers_with_counts,
    build_kmer_index,
    query_kmer_index,
)
from metanano.utils.similarity import (
    compute_kmer_similarity,
    weighted_minhash,
    weighted_jaccard,
)


def is_datasketch_available() -> bool:
    """
    Check if datasketch is available.
    检查 datasketch 是否可用。
    """
    try:
        from datasketch import MinHash
        return True
    except ImportError:
        return False


class TestKmerGeneration:
    """
    Test suite for k-mer generation utilities.
    K-mer 生成工具的测试套件。
    """

    def test_generate_kmers_basic(self) -> None:
        """
        Test basic k-mer generation.
        测试基本 k-mer 生成。
        """
        sequence = "EVQLV"
        k = 3
        
        kmers = generate_kmers(sequence, k)
        
        expected = {"EVQ", "VQL", "QLV"}
        assert kmers == expected, f"Expected {expected}, got {kmers}"

    def test_generate_kmers_with_k5(self, sample_sequence: str) -> None:
        """
        Test k-mer generation with k=5 (default).
        测试 k=5（默认）的 k-mer 生成。
        """
        kmers = generate_kmers(sample_sequence, k=5)
        
        assert len(kmers) > 0, "Should generate k-mers"
        assert all(len(kmer) == 5 for kmer in kmers), "All k-mers should have length 5"

    def test_generate_kmers_short_sequence(self) -> None:
        """
        Test k-mer generation with sequence shorter than k.
        测试序列短于 k 时的 k-mer 生成。
        """
        sequence = "EVQL"  # Length 4
        k = 5
        
        kmers = generate_kmers(sequence, k)
        
        assert kmers == set(), "Short sequence should return empty set"

    def test_generate_kmers_with_counts(self) -> None:
        """
        Test k-mer generation with occurrence counts.
        测试带出现次数的 k-mer 生成。
        """
        sequence = "AAAAAAA"  # Repeating A's
        k = 3
        
        counts = generate_kmers_with_counts(sequence, k)
        
        assert "AAA" in counts, "Should contain 'AAA'"
        assert counts["AAA"] == 5, "AAA should appear 5 times"

    def test_build_kmer_index(self, sample_sequence: str, sample_sequence_2: str) -> None:
        """
        Test k-mer index building.
        测试 k-mer 索引构建。
        """
        sequences = [sample_sequence, sample_sequence_2]
        
        index = build_kmer_index(sequences, k=5)
        
        assert len(index) > 0, "Index should have entries"
        # Each value should be a set of sequence indices
        # 每个值应该是序列索引的集合
        for kmer, seq_indices in index.items():
            assert isinstance(seq_indices, set), "Values should be sets"
            assert all(isinstance(idx, int) for idx in seq_indices), "Indices should be ints"

    def test_query_kmer_index(self, sample_sequence: str, sample_sequence_2: str) -> None:
        """
        Test k-mer index querying.
        测试 k-mer 索引查询。
        """
        sequences = [sample_sequence, sample_sequence_2]
        index = build_kmer_index(sequences, k=5)
        
        # Query with the first sequence
        # 用第一个序列查询
        candidates = query_kmer_index(sample_sequence, index, k=5, min_shared=1)
        
        assert 0 in candidates, "Query sequence should find itself"


class TestJaccardSimilarity:
    """
    Test suite for Jaccard similarity computation.
    Jaccard 相似度计算的测试套件。
    """

    def test_similarity_identical_sequences(self, sample_sequence: str) -> None:
        """
        Test Jaccard similarity for identical sequences.
        测试相同序列的 Jaccard 相似度。
        """
        similarity = compute_kmer_similarity(sample_sequence, sample_sequence, k=5)
        
        assert similarity == 1.0, "Identical sequences should have similarity 1.0"

    def test_similarity_different_sequences(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test Jaccard similarity for different sequences.
        测试不同序列的 Jaccard 相似度。
        """
        similarity = compute_kmer_similarity(sample_sequence, sample_sequence_2, k=5)
        
        assert 0.0 <= similarity <= 1.0, "Similarity should be in [0, 1]"
        assert similarity < 1.0, "Different sequences should have similarity < 1.0"

    def test_similarity_empty_sequence(self, sample_sequence: str) -> None:
        """
        Test Jaccard similarity with empty sequence.
        测试空序列的 Jaccard 相似度。
        """
        similarity = compute_kmer_similarity(sample_sequence, "", k=5)
        
        assert similarity == 0.0, "Empty sequence should have similarity 0.0"


class TestWeightedMinHash:
    """
    Test suite for weighted MinHash similarity.
    加权 MinHash 相似度的测试套件。
    """

    def test_minhash_availability(self) -> None:
        """
        Test that datasketch MinHash is available.
        测试 datasketch MinHash 是否可用。
        """
        if not is_datasketch_available():
            pytest.skip("datasketch not available")
        
        from datasketch import MinHash
        
        mh = MinHash(num_perm=128)
        assert mh is not None, "MinHash should be creatable"

    def test_weighted_minhash_identical(self, sample_sequence: str) -> None:
        """
        Test weighted MinHash for identical sequences.
        测试相同序列的加权 MinHash。
        """
        if not is_datasketch_available():
            pytest.skip("datasketch not available")
        
        similarity = weighted_minhash(sample_sequence, sample_sequence, k=5)
        
        assert similarity == 1.0, "Identical sequences should have MinHash similarity 1.0"

    def test_weighted_minhash_different(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test weighted MinHash for different sequences.
        测试不同序列的加权 MinHash。
        """
        if not is_datasketch_available():
            pytest.skip("datasketch not available")
        
        similarity = weighted_minhash(sample_sequence, sample_sequence_2, k=5)
        
        assert 0.0 <= similarity <= 1.0, "Similarity should be in [0, 1]"

    def test_weighted_minhash_num_perm(self, sample_sequence: str) -> None:
        """
        Test weighted MinHash with different num_perm values.
        测试不同 num_perm 值的加权 MinHash。
        """
        if not is_datasketch_available():
            pytest.skip("datasketch not available")
        
        # More permutations = more accurate estimate
        # 更多排列 = 更准确的估计
        sim_64 = weighted_minhash(sample_sequence, sample_sequence, num_perm=64)
        sim_256 = weighted_minhash(sample_sequence, sample_sequence, num_perm=256)
        
        # Both should be 1.0 for identical sequences
        # 对于相同序列，两者都应该是 1.0
        assert sim_64 == 1.0, "Should be 1.0 for identical"
        assert sim_256 == 1.0, "Should be 1.0 for identical"


class TestWeightedJaccard:
    """
    Test suite for weighted Jaccard similarity.
    加权 Jaccard 相似度的测试套件。
    """

    def test_weighted_jaccard_identical(self, sample_sequence: str) -> None:
        """
        Test weighted Jaccard for identical sequences.
        测试相同序列的加权 Jaccard。
        """
        similarity = weighted_jaccard(sample_sequence, sample_sequence, k=5)
        
        assert similarity == 1.0, "Identical sequences should have weighted Jaccard 1.0"

    def test_weighted_jaccard_different(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test weighted Jaccard for different sequences.
        测试不同序列的加权 Jaccard。
        """
        similarity = weighted_jaccard(sample_sequence, sample_sequence_2, k=5)
        
        assert 0.0 <= similarity <= 1.0, "Similarity should be in [0, 1]"
        assert similarity < 1.0, "Different sequences should have similarity < 1.0"


class TestDiversityFilterSimilarityIntegration:
    """
    Test suite for DiversityFilter similarity integration.
    DiversityFilter 相似度集成的测试套件。
    """

    def test_historical_similarity_distinct(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test historical similarity check with distinct sequences.
        测试不同序列的历史相似度检查。
        """
        from metanano.config import DiversityConfig
        from metanano.filters.diversity import DiversityFilter
        
        config = DiversityConfig()
        diversity_filter = DiversityFilter(config)
        
        passed, max_similarity = diversity_filter.check_historical_similarity(
            sample_sequence,
            [sample_sequence_2]
        )
        
        # Distinct sequences should pass (similarity < 0.9)
        # 不同序列应该通过（相似度 < 0.9）
        assert passed, "Distinct sequences should pass historical similarity check"

    def test_historical_similarity_identical(self, sample_sequence: str) -> None:
        """
        Test historical similarity check with identical sequences.
        测试相同序列的历史相似度检查。
        """
        from metanano.config import DiversityConfig
        from metanano.filters.diversity import DiversityFilter
        
        config = DiversityConfig()
        diversity_filter = DiversityFilter(config)
        
        passed, max_similarity = diversity_filter.check_historical_similarity(
            sample_sequence,
            [sample_sequence]  # Same as query
        )
        
        # Identical sequence should fail (similarity = 1.0 >= 0.9)
        # 相同序列应该失败（相似度 = 1.0 >= 0.9）
        assert not passed, "Identical sequences should fail historical similarity check"
        assert max_similarity == 1.0, "Max similarity should be 1.0 for identical"

    def test_historical_similarity_empty_history(self, sample_sequence: str) -> None:
        """
        Test historical similarity check with no historical sequences.
        测试无历史序列的历史相似度检查。
        """
        from metanano.config import DiversityConfig
        from metanano.filters.diversity import DiversityFilter
        
        config = DiversityConfig()
        diversity_filter = DiversityFilter(config)
        
        passed, max_similarity = diversity_filter.check_historical_similarity(
            sample_sequence,
            []  # Empty history
        )
        
        # Empty history = no similar sequences = should pass
        # 空历史 = 无相似序列 = 应该通过
        assert passed, "Empty history should always pass"
        assert max_similarity is None, "No history = no similarity"




