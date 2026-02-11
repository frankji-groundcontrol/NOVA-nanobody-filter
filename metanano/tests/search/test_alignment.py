"""
References / 参考:
    - docs/en/README.md: Section 1.1.3 - Fine Alignment
    - docs/cn/README.md: 第1.1.3节 - 精细对齐

File / 文件:
    - metanano/tests/search/test_alignment.py

Overview / 概述:
    Tests for AlignmentEngine pairwise sequence alignment.
    AlignmentEngine 成对序列对齐的测试。

    Covers parasail-based local/global alignment, BioPython fallback,
    result dataclass, and optional visualization.
    覆盖基于 parasail 的局部/全局对齐、BioPython 回退、
    结果数据类和可选可视化。

Consumers / 调用方:
    - pytest (test runner)
"""

import sys
from unittest.mock import patch

import pytest

from metanano.config import FineAlignmentConfig
from metanano.tests.search.conftest import SEARCH_FIXTURES
from metanano.utils.alignment import AlignmentEngine, AlignmentResult


@pytest.fixture
def config() -> FineAlignmentConfig:
    """
    Provide default fine alignment configuration.
    提供默认的精细对齐配置。
    """
    return FineAlignmentConfig()


@pytest.fixture
def engine(config: FineAlignmentConfig) -> AlignmentEngine:
    """
    Provide an AlignmentEngine instance.
    提供一个 AlignmentEngine 实例。
    """
    return AlignmentEngine(config)


class TestAlignmentEngine:
    """
    Tests for AlignmentEngine pairwise alignment.
    AlignmentEngine 成对对齐的测试。
    """

    def test_parasail_smith_waterman_score(self, engine: AlignmentEngine) -> None:
        """
        Smith-Waterman (local) alignment returns a positive score.
        Smith-Waterman（局部）对齐返回正分数。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target, method="local")

        assert result.score > 0

    def test_parasail_needleman_wunsch_score(self, engine: AlignmentEngine) -> None:
        """
        Needleman-Wunsch (global) alignment returns a positive score.
        Needleman-Wunsch（全局）对齐返回正分数。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target, method="global")

        assert result.score > 0

    def test_alignment_returns_identity_percent(self, engine: AlignmentEngine) -> None:
        """
        Alignment identity is between 0.0 and 1.0.
        对齐相似度在 0.0 到 1.0 之间。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target)

        assert 0.0 <= result.identity <= 1.0

    def test_alignment_returns_cigar(self, engine: AlignmentEngine) -> None:
        """
        Alignment returns a non-empty CIGAR string.
        对齐返回非空的 CIGAR 字符串。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target)

        assert isinstance(result.cigar, str)
        assert len(result.cigar) > 0

    def test_alignment_returns_aligned_sequences(
        self, engine: AlignmentEngine
    ) -> None:
        """
        Aligned query and target are strings of equal length.
        对齐后的查询和目标是等长的字符串。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target)

        assert isinstance(result.aligned_query, str)
        assert isinstance(result.aligned_target, str)
        assert len(result.aligned_query) == len(result.aligned_target)

    def test_biopython_fallback_when_parasail_unavailable(
        self, config: FineAlignmentConfig
    ) -> None:
        """
        Falls back to BioPython when parasail import fails, returning valid result.
        当 parasail 导入失败时回退到 BioPython，返回有效结果。
        """
        with patch.dict(sys.modules, {"parasail": None}):
            fallback_engine = AlignmentEngine(config)

        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = fallback_engine.align(query, target)

        assert result.score > 0
        assert 0.0 <= result.identity <= 1.0

    def test_alignment_with_identical_sequences(
        self, engine: AlignmentEngine
    ) -> None:
        """
        Identical sequences produce identity ≈ 1.0 (>0.99).
        相同序列产生相似度 ≈ 1.0（>0.99）。
        """
        query = SEARCH_FIXTURES["query_vhh"]

        result = engine.align(query, query)

        assert result.identity > 0.99

    def test_alignment_with_dissimilar_sequences(
        self, engine: AlignmentEngine
    ) -> None:
        """
        Dissimilar sequences produce identity < 0.5.
        不相似的序列产生相似度 < 0.5。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["dissimilar_vhh"]

        result = engine.align(query, target, method="global")

        assert result.identity < 0.5

    def test_alignment_optional_visualization(
        self, engine: AlignmentEngine
    ) -> None:
        """
        include_alignment=False returns None for aligned sequences.
        include_alignment=False 时对齐序列返回 None。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target, include_alignment=False)

        assert result.aligned_query is None
        assert result.aligned_target is None
        assert result.score > 0

    def test_alignment_result_dataclass(self, engine: AlignmentEngine) -> None:
        """
        AlignmentResult has all required fields.
        AlignmentResult 包含所有必需字段。
        """
        query = SEARCH_FIXTURES["query_vhh"]
        target = SEARCH_FIXTURES["similar_vhh"]

        result = engine.align(query, target)

        assert hasattr(result, "score")
        assert hasattr(result, "identity")
        assert hasattr(result, "cigar")
        assert hasattr(result, "aligned_query")
        assert hasattr(result, "aligned_target")
        assert hasattr(result, "length")
        assert hasattr(result, "matches")
        assert isinstance(result.score, int)
        assert isinstance(result.identity, float)
        assert isinstance(result.length, int)
        assert isinstance(result.matches, int)
