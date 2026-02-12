"""
File / 文件:
    - metanano/tests/search/test_search_engine.py

Overview / 概述:
    Tests for SearchEngine MapReduce orchestration pipeline.
    SearchEngine MapReduce 编排流水线测试。

Consumers / 调用方:
    - pytest
"""

from typing import Any, Dict

import pytest

from metanano.config import SearchConfig
from metanano.search.index_manager import IndexManager
from metanano.utils.alignment import AlignmentEngine
from metanano.utils.kmer import generate_kmers


def _load_search_symbols() -> tuple[type[Any], type[Any], type[Any]]:
    """
    Import SearchEngine symbols lazily so RED phase fails as test failures.
    延迟导入 SearchEngine 符号，使 RED 阶段以测试失败形式体现。
    """
    try:
        from metanano.search.search_engine import SearchEngine, SearchMatch, SearchResult

        return SearchEngine, SearchMatch, SearchResult
    except ModuleNotFoundError as exc:
        pytest.fail(f"SearchEngine module missing: {exc}")


@pytest.fixture
def search_config() -> SearchConfig:
    """
    Provide default search config.
    提供默认搜索配置。
    """
    return SearchConfig()


def _build_engine(
    search_config: SearchConfig,
    query_sequence: str,
    near_identical_sequence: str,
    similar_sequence: str,
    dissimilar_sequence: str,
    known_cdrs: Dict[str, Dict[str, str]],
    with_missing_cdr: bool,
) -> Any:
    """
    Build a SearchEngine with a deterministic in-memory index.
    构建带确定性内存索引的 SearchEngine。
    """
    SearchEngine, _, _ = _load_search_symbols()

    index_manager = IndexManager(search_config)
    k = getattr(search_config, "k", 5)

    index_manager.add_sequence(
        "query_self",
        query_sequence,
        known_cdrs["query_vhh"],
        generate_kmers(query_sequence, k=k),
    )
    index_manager.add_sequence(
        "near_identical",
        near_identical_sequence,
        None if with_missing_cdr else known_cdrs["near_identical_vhh"],
        generate_kmers(near_identical_sequence, k=k),
    )
    index_manager.add_sequence(
        "similar",
        similar_sequence,
        known_cdrs["similar_vhh"],
        generate_kmers(similar_sequence, k=k),
    )
    index_manager.add_sequence(
        "dissimilar",
        dissimilar_sequence,
        known_cdrs["dissimilar_vhh"],
        generate_kmers(dissimilar_sequence, k=k),
    )

    alignment_engine = AlignmentEngine(search_config.fine_alignment)
    return SearchEngine(search_config, index_manager, alignment_engine)


@pytest.fixture
def search_engine_with_cdrs(
    search_config: SearchConfig,
    query_sequence: str,
    near_identical_sequence: str,
    similar_sequence: str,
    dissimilar_sequence: str,
    known_cdrs: Dict[str, Dict[str, str]],
) -> Any:
    """
    SearchEngine fixture where all indexed matches have CDR annotations.
    所有索引匹配均带 CDR 注释的 SearchEngine fixture。
    """
    return _build_engine(
        search_config=search_config,
        query_sequence=query_sequence,
        near_identical_sequence=near_identical_sequence,
        similar_sequence=similar_sequence,
        dissimilar_sequence=dissimilar_sequence,
        known_cdrs=known_cdrs,
        with_missing_cdr=False,
    )


@pytest.fixture
def search_engine_with_missing_cdr(
    search_config: SearchConfig,
    query_sequence: str,
    near_identical_sequence: str,
    similar_sequence: str,
    dissimilar_sequence: str,
    known_cdrs: Dict[str, Dict[str, str]],
) -> Any:
    """
    SearchEngine fixture where one indexed match has cdrs=None.
    一个索引匹配的 cdrs=None 的 SearchEngine fixture。
    """
    return _build_engine(
        search_config=search_config,
        query_sequence=query_sequence,
        near_identical_sequence=near_identical_sequence,
        similar_sequence=similar_sequence,
        dissimilar_sequence=dissimilar_sequence,
        known_cdrs=known_cdrs,
        with_missing_cdr=True,
    )


def test_search_single_query_returns_results(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    Search known similar sequence and get non-empty matches.
    搜索已知相似序列并获得非空匹配。
    """
    result = search_engine_with_cdrs.search(query_sequence)
    assert len(result.matches) > 0


def test_search_returns_multi_tier_results(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    Search results carry valid tier labels.
    搜索结果包含有效分层标签。
    """
    result = search_engine_with_cdrs.search(query_sequence)
    tiers = {match.tier for match in result.matches}

    assert tiers
    assert tiers.issubset({"exact", "high", "moderate", "low"})


def test_search_excludes_self_match(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    Query sequence already in index should be excluded from results.
    当查询序列已在索引中时，应从结果中排除自身。
    """
    result = search_engine_with_cdrs.search(query_sequence)
    assert all(match.target_id != "query_self" for match in result.matches)


def test_search_empty_index_returns_empty(search_config: SearchConfig, query_sequence: str) -> None:
    """
    Empty index returns empty search result.
    空索引返回空搜索结果。
    """
    SearchEngine, _, _ = _load_search_symbols()
    index_manager = IndexManager(search_config)
    engine = SearchEngine(search_config, index_manager, AlignmentEngine(search_config.fine_alignment))

    result = engine.search(query_sequence)

    assert result.matches == []
    assert result.total_candidates == 0
    assert result.total_indexed == 0


def test_search_dissimilar_query_returns_empty_or_low(search_engine_with_cdrs: Any) -> None:
    """
    Very dissimilar query should not produce exact/high matches.
    高度不相似查询不应产生 exact/high 匹配。
    """
    result = search_engine_with_cdrs.search("A" * 120)
    assert all(match.tier not in {"exact", "high"} for match in result.matches)


def test_search_includes_alignment_when_requested(
    search_engine_with_cdrs: Any, query_sequence: str
) -> None:
    """
    include_alignment=True should include aligned sequences.
    include_alignment=True 时应包含对齐序列。
    """
    result = search_engine_with_cdrs.search(query_sequence, include_alignment=True)

    assert result.matches
    assert all(match.aligned_query is not None for match in result.matches)
    assert all(match.aligned_target is not None for match in result.matches)


def test_search_excludes_alignment_by_default(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    Default search should not include aligned sequences.
    默认搜索不应包含对齐序列。
    """
    result = search_engine_with_cdrs.search(query_sequence)

    assert result.matches
    assert all(match.aligned_query is None for match in result.matches)
    assert all(match.aligned_target is None for match in result.matches)


def test_search_includes_cdr_comparison(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    Search results should include CDR similarity metrics when available.
    当可用时，搜索结果应包含 CDR 相似度指标。
    """
    result = search_engine_with_cdrs.search(query_sequence)

    assert result.matches
    assert result.matches[0].cdr_similarity is not None
    assert set(result.matches[0].cdr_similarity.keys()) == {"CDR1", "CDR2", "CDR3"}
    assert all(0.0 <= value <= 1.0 for value in result.matches[0].cdr_similarity.values())


def test_search_cdr_comparison_skipped_when_cdrs_none(
    search_engine_with_missing_cdr: Any,
    query_sequence: str,
) -> None:
    """
    Match with missing CDR annotation should have cdr_similarity=None.
    当匹配缺少 CDR 注释时，cdr_similarity 应为 None。
    """
    result = search_engine_with_missing_cdr.search(query_sequence)

    missing_cdr_match = [match for match in result.matches if match.target_id == "near_identical"]
    assert missing_cdr_match
    assert missing_cdr_match[0].cdr_similarity is None


def test_search_respects_configurable_thresholds(
    search_engine_with_cdrs: Any,
    query_sequence: str,
) -> None:
    """
    Stricter coarse thresholds should reduce result count.
    更严格的粗过滤阈值应减少结果数量。
    """
    baseline = search_engine_with_cdrs.search(query_sequence)
    strict = search_engine_with_cdrs.search(
        query_sequence,
        coarse_min_shared=999,
        coarse_jaccard=0.99,
    )

    assert len(baseline.matches) > 0
    assert len(strict.matches) < len(baseline.matches)


def test_search_uses_parallel_execution(monkeypatch: Any, search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    Search alignment stage should submit tasks through ThreadPoolExecutor.
    搜索对齐阶段应通过 ThreadPoolExecutor 提交任务。
    """
    import metanano.search.search_engine as search_engine_module

    submit_calls = {"count": 0}

    class _FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class _FakeExecutor:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def submit(self, func, *args, **kwargs):
            submit_calls["count"] += 1
            return _FakeFuture(func(*args, **kwargs))

    monkeypatch.setattr(search_engine_module, "ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(
        search_engine_with_cdrs._index_manager,
        "coarse_filter",
        lambda **_: [0, 1],
    )
    monkeypatch.setattr(type(search_engine_with_cdrs), "_BATCH_SIZE", 2, raising=False)

    result = search_engine_with_cdrs.search(query_sequence)

    assert submit_calls["count"] > 0
    assert result.total_candidates == 2
    assert submit_calls["count"] == 1


def test_align_batch_returns_list_of_matches(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    result = search_engine_with_cdrs.search(query_sequence)
    candidate_count = result.total_candidates
    assert candidate_count > 0

    query_cdrs = search_engine_with_cdrs._resolve_query_cdrs(query_sequence)
    batch = [
        search_engine_with_cdrs._index_manager.get_record_by_id(match.target_id)
        for match in result.matches
    ]
    batch_indices = [
        search_engine_with_cdrs._index_manager._id_to_idx[record.id]
        for record in batch
        if record is not None
    ]

    matches = search_engine_with_cdrs._align_batch(
        query_sequence,
        batch_indices,
        False,
        query_cdrs,
    )

    assert len(matches) == len(batch_indices)


def test_search_tied_identity_orders_by_target_id(
    monkeypatch: Any,
    search_config: SearchConfig,
    query_sequence: str,
    similar_sequence: str,
    near_identical_sequence: str,
) -> None:
    SearchEngine, SearchMatch, _ = _load_search_symbols()

    index_manager = IndexManager(search_config)
    k = getattr(search_config, "k", 5)
    index_manager.add_sequence(
        "z_target",
        similar_sequence,
        None,
        generate_kmers(similar_sequence, k=k),
    )
    index_manager.add_sequence(
        "a_target",
        near_identical_sequence,
        None,
        generate_kmers(near_identical_sequence, k=k),
    )

    monkeypatch.setattr(index_manager, "coarse_filter", lambda **_: [0, 1])

    engine = SearchEngine(
        search_config,
        index_manager,
        AlignmentEngine(search_config.fine_alignment),
    )

    def _fake_align_candidate(
        query: str,
        candidate_index: int,
        include_alignment: bool,
        query_cdrs: Dict[str, str] | None,
    ) -> Any:
        del query, include_alignment, query_cdrs
        record = index_manager.get_record(candidate_index)
        return SearchMatch(
            target_id=record.id,
            target_sequence=record.sequence,
            score=100,
            identity=0.8,
            tier="high",
            cigar=None,
            aligned_query=None,
            aligned_target=None,
            cdr_similarity=None,
        )

    monkeypatch.setattr(engine, "_align_candidate", _fake_align_candidate)

    result = engine.search(query_sequence)

    assert [match.target_id for match in result.matches] == ["a_target", "z_target"]


def test_search_uses_lsh_strategy_when_configured(
    monkeypatch: Any,
    search_engine_with_cdrs: Any,
    query_sequence: str,
) -> None:
    search_engine_with_cdrs._config.coarse_filter.retrieval_strategy = "lsh"
    calls = {"coarse": 0, "lsh": 0}

    def _fake_coarse_filter(**_: Any) -> list[int]:
        calls["coarse"] += 1
        return []

    def _fake_lsh_query(**_: Any) -> list[int]:
        calls["lsh"] += 1
        return []

    monkeypatch.setattr(search_engine_with_cdrs._index_manager, "coarse_filter", _fake_coarse_filter)
    monkeypatch.setattr(search_engine_with_cdrs._index_manager, "lsh_query", _fake_lsh_query)

    result = search_engine_with_cdrs.search(query_sequence)

    assert calls["lsh"] == 1
    assert calls["coarse"] == 0
    assert result.total_candidates == 0


def test_search_uses_kmer_strategy_by_default(
    monkeypatch: Any,
    search_engine_with_cdrs: Any,
    query_sequence: str,
) -> None:
    calls = {"coarse": 0, "lsh": 0}

    def _fake_coarse_filter(**_: Any) -> list[int]:
        calls["coarse"] += 1
        return []

    def _fake_lsh_query(**_: Any) -> list[int]:
        calls["lsh"] += 1
        return []

    monkeypatch.setattr(search_engine_with_cdrs._index_manager, "coarse_filter", _fake_coarse_filter)
    monkeypatch.setattr(search_engine_with_cdrs._index_manager, "lsh_query", _fake_lsh_query)

    result = search_engine_with_cdrs.search(query_sequence)

    assert calls["coarse"] == 1
    assert calls["lsh"] == 0
    assert result.total_candidates == 0


def test_search_result_dataclass(search_engine_with_cdrs: Any, query_sequence: str) -> None:
    """
    SearchResult exposes expected fields and basic value types.
    SearchResult 暴露预期字段和基础类型。
    """
    _, SearchMatch, SearchResult = _load_search_symbols()

    result = search_engine_with_cdrs.search(query_sequence)

    assert isinstance(result, SearchResult)
    assert hasattr(result, "query_sequence")
    assert hasattr(result, "matches")
    assert hasattr(result, "total_candidates")
    assert hasattr(result, "total_indexed")
    assert hasattr(result, "elapsed_ms")
    assert isinstance(result.query_sequence, str)
    assert isinstance(result.matches, list)
    assert isinstance(result.total_candidates, int)
    assert isinstance(result.total_indexed, int)
    assert isinstance(result.elapsed_ms, float)
    assert all(isinstance(match, SearchMatch) for match in result.matches)
