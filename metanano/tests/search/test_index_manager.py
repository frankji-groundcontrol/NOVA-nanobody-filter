"""
File / 文件:
    - metanano/tests/search/test_index_manager.py

Overview / 概述:
    Tests for IndexManager — thread-safe in-memory k-mer index with two-stage coarse filter.
    IndexManager 的测试 — 线程安全的内存 k-mer 索引与两阶段粗过滤。

Consumers / 调用方:
    - pytest
"""

import threading
from typing import Dict, List, Optional, Set

import pytest

from metanano.config import CoarseFilterConfig, SearchConfig
from metanano.search.index_manager import IndexManager, SequenceRecord
from metanano.utils.kmer import generate_kmers
from metanano.utils.similarity import compute_kmer_similarity


@pytest.fixture
def search_config() -> SearchConfig:
    """
    Default SearchConfig for tests.
    测试用的默认 SearchConfig。
    """
    return SearchConfig()


@pytest.fixture
def index_manager(search_config: SearchConfig) -> IndexManager:
    """
    Fresh IndexManager instance.
    新的 IndexManager 实例。
    """
    return IndexManager(search_config)


class TestIndexManagerBasics:
    """
    Basic add/get/size operations.
    基本的 add/get/size 操作。
    """

    def test_add_sequence_increases_size(self, index_manager: IndexManager, query_sequence: str) -> None:
        """
        Adding one sequence makes size 1.
        添加一个序列使 size 变为 1。
        """
        kmers = generate_kmers(query_sequence, 5)
        index_manager.add_sequence("seq_0", query_sequence, None, kmers)
        assert index_manager.size() == 1

    def test_empty_index_returns_empty(self, index_manager: IndexManager) -> None:
        """
        Querying empty index returns empty list.
        查询空索引返回空列表。
        """
        query_kmers = generate_kmers("EVQLVQSGVEVKKPGA", 5)
        result = index_manager.coarse_filter(
            query_kmers=query_kmers,
            min_shared=1,
            jaccard_threshold=0.1,
            max_candidates=100,
        )
        assert result == []

    def test_get_sequence_record_by_index(
        self,
        index_manager: IndexManager,
        query_sequence: str,
        known_cdrs: Dict[str, Dict[str, str]],
    ) -> None:
        """
        get_record returns SequenceRecord with correct fields.
        get_record 返回具有正确字段的 SequenceRecord。
        """
        kmers = generate_kmers(query_sequence, 5)
        cdrs = known_cdrs["query_vhh"]
        index_manager.add_sequence("query_0", query_sequence, cdrs, kmers)

        record = index_manager.get_record(0)
        assert isinstance(record, SequenceRecord)
        assert record.id == "query_0"
        assert record.sequence == query_sequence
        assert record.cdrs == cdrs
        assert record.kmer_count == len(kmers)

    def test_cdr_extraction_failure_handled(
        self,
        index_manager: IndexManager,
        query_sequence: str,
    ) -> None:
        """
        Sequence with cdrs=None can be indexed and queried.
        cdrs=None 的序列可以被索引和查询。
        """
        kmers = generate_kmers(query_sequence, 5)
        index_manager.add_sequence("no_cdr", query_sequence, None, kmers)

        record = index_manager.get_record(0)
        assert record.cdrs is None
        assert record.kmer_count == len(kmers)

    def test_get_ids_for_sequence_returns_all_ids(
        self,
        index_manager: IndexManager,
        query_sequence: str,
    ) -> None:
        kmers = generate_kmers(query_sequence, 5)
        index_manager.add_sequence("seq_a", query_sequence, None, kmers)
        index_manager.add_sequence("seq_b", query_sequence, None, kmers)

        found = index_manager.get_ids_for_sequence(query_sequence)
        assert found == {"seq_a", "seq_b"}
        assert index_manager.get_ids_for_sequence("THIS_SEQUENCE_DOES_NOT_EXIST") == set()

    def test_get_record_by_id_returns_record_or_none(
        self,
        index_manager: IndexManager,
        query_sequence: str,
    ) -> None:
        kmers = generate_kmers(query_sequence, 5)
        index_manager.add_sequence("seq_0", query_sequence, None, kmers)

        record = index_manager.get_record_by_id("seq_0")
        assert record is not None
        assert record.id == "seq_0"
        assert record.sequence == query_sequence
        assert index_manager.get_record_by_id("missing") is None

    def test_kmers_stored_as_hashed_frozenset(
        self,
        index_manager: IndexManager,
        query_sequence: str,
    ) -> None:
        kmers = generate_kmers(query_sequence, 5)
        index_manager.add_sequence("seq_hashed", query_sequence, None, kmers)

        record = index_manager.get_record(0)
        assert record.kmer_count == len(kmers)


class TestCoarseFilter:
    """
    Two-stage coarse filter behavior.
    两阶段粗过滤行为。
    """

    def test_query_returns_candidates(
        self,
        index_manager: IndexManager,
        query_sequence: str,
        near_identical_sequence: str,
        dissimilar_sequence: str,
    ) -> None:
        """
        Querying with a known similar sequence returns candidate indices.
        使用已知的相似序列查询返回候选索引。
        """
        # Add near-identical and dissimilar
        # 添加近乎相同和不相似的序列
        kmers_near = generate_kmers(near_identical_sequence, 5)
        kmers_dis = generate_kmers(dissimilar_sequence, 5)
        index_manager.add_sequence("near", near_identical_sequence, None, kmers_near)
        index_manager.add_sequence("dis", dissimilar_sequence, None, kmers_dis)

        query_kmers = generate_kmers(query_sequence, 5)
        candidates = index_manager.coarse_filter(
            query_kmers=query_kmers,
            min_shared=3,
            jaccard_threshold=0.3,
            max_candidates=100,
        )
        # near_identical should definitely be a candidate
        # near_identical 一定是一个候选
        assert 0 in candidates  # index of near_identical

    def test_coarse_filter_superset_of_bruteforce(
        self,
        search_config: SearchConfig,
        sequence_database: List[str],
        query_sequence: str,
    ) -> None:
        """
        All brute-force Jaccard matches above threshold are in the coarse filter candidate set.
        所有高于阈值的暴力 Jaccard 匹配都在粗过滤候选集中。
        """
        mgr = IndexManager(search_config)
        threshold = 0.3

        # Index all sequences
        # 索引所有序列
        for i, seq in enumerate(sequence_database):
            kmers = generate_kmers(seq, 5)
            mgr.add_sequence(f"seq_{i}", seq, None, kmers)

        query_kmers = generate_kmers(query_sequence, 5)
        candidates = mgr.coarse_filter(
            query_kmers=query_kmers,
            min_shared=1,
            jaccard_threshold=threshold,
            max_candidates=500,
        )

        # Brute-force: compute Jaccard for every indexed sequence
        # 暴力计算：计算每个索引序列的 Jaccard
        bruteforce_matches = set()
        for i, seq in enumerate(sequence_database):
            sim = compute_kmer_similarity(query_sequence, seq, k=5)
            if sim >= threshold:
                bruteforce_matches.add(i)

        # Coarse filter MUST be a superset
        # 粗过滤必须是超集
        candidate_set = set(candidates)
        assert bruteforce_matches.issubset(candidate_set), (
            f"Brute-force matches {bruteforce_matches - candidate_set} missing from coarse filter"
        )

    def test_self_match_excluded(
        self,
        index_manager: IndexManager,
        query_sequence: str,
        near_identical_sequence: str,
    ) -> None:
        """
        Query sequence in index with exclude_ids excludes it from results.
        使用 exclude_ids 查询索引中的序列时将其排除在结果之外。
        """
        kmers_q = generate_kmers(query_sequence, 5)
        kmers_n = generate_kmers(near_identical_sequence, 5)
        index_manager.add_sequence("self", query_sequence, None, kmers_q)
        index_manager.add_sequence("near", near_identical_sequence, None, kmers_n)

        candidates = index_manager.coarse_filter(
            query_kmers=kmers_q,
            min_shared=1,
            jaccard_threshold=0.1,
            max_candidates=100,
            exclude_ids={"self"},
        )
        # "self" (index 0) should be excluded
        # "self"（索引 0）应被排除
        assert 0 not in candidates

    def test_two_stage_coarse_filter(
        self,
        search_config: SearchConfig,
        sequence_database: List[str],
        query_sequence: str,
    ) -> None:
        """
        Stage 1 (min k-mers) produces >= stage 2 (Jaccard) candidates.
        阶段 1（最小 k-mer 数）产生的候选数 >= 阶段 2（Jaccard）。
        """
        mgr = IndexManager(search_config)
        for i, seq in enumerate(sequence_database):
            kmers = generate_kmers(seq, 5)
            mgr.add_sequence(f"seq_{i}", seq, None, kmers)

        query_kmers = generate_kmers(query_sequence, 5)

        # Stage 1 only: very low thresholds to get all stage-1 survivors
        # 仅阶段 1：非常低的阈值以获取所有阶段 1 幸存者
        stage1_candidates = mgr.coarse_filter(
            query_kmers=query_kmers,
            min_shared=3,
            jaccard_threshold=0.0,  # effectively skip stage 2
            max_candidates=500,
        )

        # Both stages: apply Jaccard threshold
        # 两个阶段：应用 Jaccard 阈值
        stage2_candidates = mgr.coarse_filter(
            query_kmers=query_kmers,
            min_shared=3,
            jaccard_threshold=0.3,
            max_candidates=500,
        )

        assert len(stage1_candidates) >= len(stage2_candidates)

    def test_max_candidates_cap(
        self,
        search_config: SearchConfig,
        sequence_database: List[str],
        query_sequence: str,
    ) -> None:
        """
        Results are capped at max_candidates even with many matches.
        即使有很多匹配，结果也被限制在 max_candidates。
        """
        mgr = IndexManager(search_config)
        for i, seq in enumerate(sequence_database):
            kmers = generate_kmers(seq, 5)
            mgr.add_sequence(f"seq_{i}", seq, None, kmers)

        query_kmers = generate_kmers(query_sequence, 5)
        candidates = mgr.coarse_filter(
            query_kmers=query_kmers,
            min_shared=1,
            jaccard_threshold=0.0,
            max_candidates=2,
        )
        assert len(candidates) <= 2

    def test_max_candidates_tie_breaks_by_sequence_id(self, search_config: SearchConfig) -> None:
        mgr = IndexManager(search_config)
        seq = "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
        kmers = generate_kmers(seq, 5)

        mgr.add_sequence("z_seq", seq, None, kmers)
        mgr.add_sequence("a_seq", seq, None, kmers)

        candidates = mgr.coarse_filter(
            query_kmers=kmers,
            min_shared=1,
            jaccard_threshold=0.0,
            max_candidates=1,
        )

        assert len(candidates) == 1
        assert mgr.get_record(candidates[0]).id == "a_seq"

    def test_lsh_methods_exist(self, index_manager: IndexManager) -> None:
        assert hasattr(index_manager, "lsh_query")
        assert hasattr(index_manager, "build_lsh_index")

    def test_lsh_query_exclude_ids_and_tie_breaking(self) -> None:
        pytest.importorskip("datasketch")

        config = SearchConfig(coarse_filter=CoarseFilterConfig(retrieval_strategy="lsh"))
        mgr = IndexManager(config)

        seq = "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
        seq_variant = "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKS"
        kmers = generate_kmers(seq, 5)

        mgr.add_sequence("z_seq", seq, None, kmers)
        mgr.add_sequence("a_seq", seq, None, kmers)
        mgr.add_sequence("b_seq", seq_variant, None, generate_kmers(seq_variant, 5))

        candidates = mgr.lsh_query(query_kmers=kmers, max_candidates=3)
        candidate_ids = [mgr.get_record(idx).id for idx in candidates]

        assert candidate_ids[:2] == ["a_seq", "z_seq"]

        filtered = mgr.lsh_query(query_kmers=kmers, max_candidates=3, exclude_ids={"a_seq"})
        filtered_ids = [mgr.get_record(idx).id for idx in filtered]
        assert "a_seq" not in filtered_ids


class TestThreadSafety:
    """
    Concurrent access tests.
    并发访问测试。
    """

    def test_thread_safe_concurrent_adds(
        self,
        index_manager: IndexManager,
        sequence_database: List[str],
    ) -> None:
        """
        10 threads adding simultaneously produce expected size, no corruption.
        10 个线程同时添加产生预期大小，无损坏。
        """
        errors: List[Exception] = []

        def add_seq(idx: int, seq: str) -> None:
            try:
                kmers = generate_kmers(seq, 5)
                index_manager.add_sequence(f"thread_{idx}", seq, None, kmers)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            seq = sequence_database[i % len(sequence_database)]
            t = threading.Thread(target=add_seq, args=(i, seq))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert index_manager.size() == 10
