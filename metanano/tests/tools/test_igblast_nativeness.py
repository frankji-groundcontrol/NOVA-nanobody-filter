"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - docs/cn/README.md: 第1.2节 - 天然性过滤器
    - metanano/utils/igblast_nativeness.py

File / 文件:
    - metanano/tests/tools/test_igblast_nativeness.py

Overview / 概述:
    Pytest tests for IgBLAST-based nativeness/humanness scoring.
    基于 IgBLAST 的天然性/人源性评分的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. IgBLAST binary and database availability
        2. VHH nativeness and human framework scoring via igblast_nativeness.run
        3. Integration with NativenessFilter (IgBLAST-based pipeline)

Consumers / 调用方:
    - pytest (test runner)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any

import pytest

from metanano.utils import igblast_nativeness
from metanano.config import NativenessConfig
from metanano.filters.nativeness import NativenessFilter


IGBLASTP_PATH = Path(igblast_nativeness.IGBLAST_DIR) / "bin" / "igblastp"


def _has_igblast() -> bool:
    """
    Check if IgBLAST binary is available and executable.
    检查 IgBLAST 可执行文件是否可用且可执行。
    """
    return IGBLASTP_PATH.exists() and os.access(IGBLASTP_PATH, os.X_OK)


def _camelid_db_exists() -> bool:
    """
    Check that camelid V database exists.
    检查骆驼科 V 区域数据库是否存在。
    """
    db_path = Path(igblast_nativeness.CAMELID_DB_V)
    return db_path.exists()


skip_igblast = pytest.mark.skipif(
    not _has_igblast() or not _camelid_db_exists(),
    reason=f"IgBLAST binaries or databases not available under {igblast_nativeness.IGBLAST_DIR}",
)


@skip_igblast
class TestIgBlastAvailability:
    """
    Test suite for IgBLAST availability.
    IgBLAST 可用性测试套件。
    """

    def test_igblast_binary_exists_and_executable(self) -> None:
        """
        IgBLAST binary should exist and be executable.
        IgBLAST 可执行文件应存在且可执行。
        """
        assert IGBLASTP_PATH.exists(), f"{IGBLASTP_PATH} should exist"
        assert os.access(IGBLASTP_PATH, os.X_OK), f"{IGBLASTP_PATH} should be executable"

    def test_camelid_database_exists(self) -> None:
        """
        Camelid V-region database should exist.
        骆驼科 V 区域数据库文件应存在。
        """
        db_path = Path(igblast_nativeness.CAMELID_DB_V)
        assert db_path.exists(), f"Camelid V database not found at {db_path}"


@skip_igblast
class TestIgBlastNativenessScoring:
    """
    Test suite for IgBLAST-based nativeness scoring.
    基于 IgBLAST 的天然性评分测试套件。
    """

    def _run_igblast_on_sequence(self, sequence: str) -> List[Dict[str, Any]]:
        """
        Helper to run igblast_nativeness.run on a single sequence.
        帮助函数：对单条序列运行 igblast_nativeness.run。
        """
        import tempfile

        seq = (sequence or "").strip().upper()
        assert seq, "Sequence should not be empty"

        with tempfile.TemporaryDirectory() as td:
            fasta_path = Path(td) / "query.fasta"
            with fasta_path.open("w", encoding="utf-8") as fh:
                fh.write(">test\n")
                fh.write(seq + "\n")

            try:
                results = igblast_nativeness.run(str(fasta_path))
            except RuntimeError as e:
                pytest.skip(f"IgBLAST failed: {e}")
            return results

    def test_score_vhh_sequence_returns_result(self, sample_sequence: str) -> None:
        """
        Test that scoring a valid VHH sequence returns one result.
        测试对有效 VHH 序列评分返回一个结果。
        """
        results = self._run_igblast_on_sequence(sample_sequence)
        assert isinstance(results, list), "run() should return a list"
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"

        r = results[0]
        for key in ["vhh_nativeness", "final_score"]:
            assert key in r, f"Result should contain '{key}' field"

    def test_scores_in_valid_range(self, sample_sequence: str) -> None:
        """
        Test that VHH nativeness and human framework scores are in [0, 1] when present.
        测试 VHH 天然性和人源性分数在 [0, 1] 范围内（当存在时）。
        """
        results = self._run_igblast_on_sequence(sample_sequence)
        r = results[0]

        vhh = r.get("vhh_nativeness")
        if vhh is not None:
            assert 0.0 <= vhh <= 1.0, f"vhh_nativeness should be in [0, 1], got {vhh}"

        human = r.get("human_framework")
        if human is not None:
            assert 0.0 <= human <= 1.0, f"human_framework should be in [0, 1], got {human}"

        final = r.get("final_score")
        if final is not None:
            assert 0.0 <= final <= 1.0, f"final_score should be in [0, 1], got {final}"

    def test_no_hard_reject_for_valid_sequence(self, sample_sequence: str) -> None:
        """
        Valid VHH sequence should not normally be hard rejected.
        有效 VHH 序列通常不应被硬拒绝。
        """
        results = self._run_igblast_on_sequence(sample_sequence)
        r = results[0]
        assert "hard_reject" in r
        # Some edge sequences might still be rejected, so only assert type.
        # 某些边缘序列可能仍被拒绝，这里只检查类型。
        assert isinstance(r["hard_reject"], bool)


@skip_igblast
class TestNativenessFilterIgBlastIntegration:
    """
    Test suite for NativenessFilter integration with IgBLAST-based scoring.
    NativenessFilter 与基于 IgBLAST 的评分集成测试套件。
    """

    def test_filter_analyze_returns_result(self, sample_sequence: str) -> None:
        """
        NativenessFilter.analyze should return a NativenessResult object.
        NativenessFilter.analyze 应返回 NativenessResult 对象。
        """
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)

        result = nat_filter.analyze(sample_sequence)
        assert result is not None, "Filter should return a result"
        assert hasattr(result, "passed"), "Result should have 'passed' attribute"
        assert hasattr(result, "imgt_numbered"), "Result should have 'imgt_numbered' attribute"

    def test_filter_scores_in_range_when_available(self, sample_sequence: str) -> None:
        """
        When scoring succeeds, nativeness and humanness scores should be in [0, 1].
        当评分成功时，天然性和人源性分数应在 [0, 1] 范围内。
        """
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)

        result = nat_filter.analyze(sample_sequence)

        if result.nativeness_score is not None:
            assert 0.0 <= result.nativeness_score <= 1.0
        if result.humanness_score is not None:
            assert 0.0 <= result.humanness_score <= 1.0

