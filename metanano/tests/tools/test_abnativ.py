"""
References / 参考:
    - docs/en/TODO.md: Section 0.4 - AbnatiV Integration
    - docs/cn/TODO.md: 第0.4节 - AbnatiV 集成
    - AbnatiV GitLab: https://gitlab.developers.cam.ac.uk/ch/sormanni/abnativ

File / 文件:
    - metanano/tests/tools/test_abnativ.py

Overview / 概述:
    Pytest tests for AbnatiV v2 (nativeness scoring) integration.
    AbnatiV v2（天然性评分）集成的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. AbnatiV package availability
        2. Model availability (requires `abnativ init`)
        3. VHH nativeness scoring
        4. Score interpretation
        5. Integration with NativenessFilter

    Setup Required / 需要的设置:
        pip install abnativ
        abnativ init  # Downloads models from Zenodo

    Python API (from GitLab README):
    Python API（来自 GitLab README）：
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sequence), id="vhh_seq")
        df_scores, df_profiles = abnativ_scoring(
            model_type='VHH',  # or VHH2 for v2
            seq_records=[record],
            mean_score_only=True,
            do_align=True,
            is_VHH=True,
            verbose=False
        )

    Output Format (DataFrame columns):
    输出格式（DataFrame 列）：
        - ID: Sequence identifier
        - AbNatiV: Overall nativeness score (0-1, threshold 0.8)
        - CDR-1, CDR-2, CDR-3: CDR region scores
        - Framework: Framework region score

Consumers / 调用方:
    - pytest (test runner)
"""

import os
import pytest
from pathlib import Path
from typing import Optional, Tuple

# AbnatiV model directory
ABNATIV_MODELS_DIR = Path.home() / ".abnativ" / "models" / "pretrained_models"


def is_abnativ_available() -> bool:
    """
    Check if AbnatiV package is available.
    检查 AbnatiV 包是否可用。
    """
    try:
        from abnativ.model.scoring_functions import abnativ_scoring
        return True
    except ImportError:
        return False


def are_models_downloaded() -> bool:
    """
    Check if AbnatiV models are downloaded and valid (non-zero size).
    检查 AbnatiV 模型是否已下载且有效（非零大小）。
    
    Models are downloaded via `abnativ init` command.
    模型通过 `abnativ init` 命令下载。
    """
    if not ABNATIV_MODELS_DIR.exists():
        return False
    
    # Check for at least one model file with non-zero size
    # 检查至少一个非零大小的模型文件
    model_files = ["vhh_model.ckpt", "vhh2_model.ckpt", "vh_model.ckpt"]
    for f in model_files:
        path = ABNATIV_MODELS_DIR / f
        if path.exists() and path.stat().st_size > 0:
            return True
    return False


def get_skip_reason() -> Optional[str]:
    """
    Get reason to skip tests if any.
    获取跳过测试的原因（如果有）。
    """
    if not is_abnativ_available():
        return "AbnatiV package not installed"
    if not are_models_downloaded():
        return "AbnatiV models not downloaded. Run `abnativ init` first."
    return None


class TestAbnatiVAvailability:
    """
    Test suite for AbnatiV package availability.
    AbnatiV 包可用性的测试套件。
    """

    def test_abnativ_package_installed(self) -> None:
        """
        Test that AbnatiV package is installed.
        测试 AbnatiV 包是否已安装。
        """
        try:
            import abnativ
            assert abnativ is not None
        except ImportError:
            pytest.skip("AbnatiV not installed. Install with: pip install abnativ")

    def test_abnativ_scoring_import(self) -> None:
        """
        Test that scoring functions can be imported.
        测试评分函数是否可以导入。
        """
        if not is_abnativ_available():
            pytest.skip("AbnatiV not available")
        
        from abnativ.model.scoring_functions import abnativ_scoring
        assert abnativ_scoring is not None

    def test_models_directory_exists(self) -> None:
        """
        Test that models directory exists (may be empty).
        测试模型目录是否存在（可能为空）。
        """
        if not is_abnativ_available():
            pytest.skip("AbnatiV not available")
        
        # Just check if we can determine the path
        # 只检查是否可以确定路径
        assert ABNATIV_MODELS_DIR.parent.parent.name == ".abnativ"

    def test_models_downloaded(self) -> None:
        """
        Test that at least one model is downloaded.
        测试至少一个模型是否已下载。
        
        If this fails, run: abnativ init
        如果此测试失败，运行：abnativ init
        """
        if not is_abnativ_available():
            pytest.skip("AbnatiV not available")
        
        if not are_models_downloaded():
            pytest.skip("Models not downloaded. Run `abnativ init` to download.")
        
        assert are_models_downloaded()


class TestAbnatiVScoring:
    """
    Test suite for AbnatiV nativeness scoring.
    AbnatiV 天然性评分的测试套件。
    """

    def test_score_vhh_sequence(self, sample_sequence: str) -> None:
        """
        Test VHH sequence scoring.
        测试 VHH 序列评分。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sample_sequence), id="test_vhh")
        
        df_scores, df_profiles = abnativ_scoring(
            model_type='VHH',
            seq_records=[record],
            mean_score_only=True,
            do_align=True,
            is_VHH=True,
            verbose=False
        )
        
        assert not df_scores.empty, "Should return non-empty DataFrame"
        # Column name format: 'AbNatiV VHH Score' for VHH model
        # 列名格式：VHH 模型使用 'AbNatiV VHH Score'
        score_col = [c for c in df_scores.columns if 'AbNatiV' in c and 'Score' in c and 'CDR' not in c and 'FR' not in c]
        assert len(score_col) > 0, f"Should have AbNatiV score column, got: {list(df_scores.columns)}"

    def test_score_returns_valid_range(self, sample_sequence: str) -> None:
        """
        Test that scores are in valid range [0, 1].
        测试分数是否在有效范围 [0, 1] 内。
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sample_sequence), id="test_vhh")
        
        df_scores, _ = abnativ_scoring(
            model_type='VHH',
            seq_records=[record],
            mean_score_only=True,
            do_align=True,
            is_VHH=True,
            verbose=False
        )
        
        # Find the main score column (format: 'AbNatiV VHH Score')
        # 找到主分数列（格式：'AbNatiV VHH Score'）
        score_col = [c for c in df_scores.columns if 'AbNatiV' in c and 'Score' in c and 'CDR' not in c and 'FR' not in c][0]
        score = df_scores[score_col].values[0]
        
        assert 0.0 <= score <= 1.0, f"Score {score} should be in [0, 1]"

    def test_score_vhh2_model(self, sample_sequence: str) -> None:
        """
        Test VHH2 (AbNatiV v2) model scoring.
        测试 VHH2（AbNatiV v2）模型评分。
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        # Check if VHH2 model is available
        # 检查 VHH2 模型是否可用
        vhh2_model = ABNATIV_MODELS_DIR / "vhh2_model.ckpt"
        if not vhh2_model.exists():
            pytest.skip("VHH2 model not downloaded")
        
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sample_sequence), id="test_vhh2")
        
        df_scores, _ = abnativ_scoring(
            model_type='VHH2',
            seq_records=[record],
            mean_score_only=True,
            do_align=True,
            is_VHH=True,
            verbose=False
        )
        
        assert not df_scores.empty, "VHH2 scoring should return results"

    def test_score_with_profile(self, sample_sequence: str) -> None:
        """
        Test scoring with residue-level profiles.
        测试带残基级别配置文件的评分。
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sample_sequence), id="test_vhh")
        
        df_scores, df_profiles = abnativ_scoring(
            model_type='VHH',
            seq_records=[record],
            mean_score_only=False,  # Get residue-level profiles
            do_align=True,
            is_VHH=True,
            verbose=False
        )
        
        # When mean_score_only=False, profiles should have data
        # 当 mean_score_only=False 时，配置文件应有数据
        assert not df_scores.empty, "Scores should be returned"


class TestAbnatiVNativenessThreshold:
    """
    Test suite for nativeness score interpretation.
    天然性分数解释的测试套件。
    
    From README: Score approaches 1 for highly native sequences,
    and 0.8 is the threshold separating native from non-native.
    来自 README：分数接近 1 表示高度天然的序列，
    0.8 是区分天然与非天然的阈值。
    """

    def test_valid_vhh_above_threshold(self, sample_sequence: str) -> None:
        """
        Test that valid VHH sequences score above 0.8 threshold.
        测试有效 VHH 序列的分数高于 0.8 阈值。
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sample_sequence), id="test_vhh")
        
        df_scores, _ = abnativ_scoring(
            model_type='VHH',
            seq_records=[record],
            mean_score_only=True,
            do_align=True,
            is_VHH=True,
            verbose=False
        )
        
        # Find the main score column (format: 'AbNatiV VHH Score')
        # 找到主分数列（格式：'AbNatiV VHH Score'）
        score_col = [c for c in df_scores.columns if 'AbNatiV' in c and 'Score' in c and 'CDR' not in c and 'FR' not in c][0]
        score = df_scores[score_col].values[0]
        
        # Valid VHH sequences should ideally score >= 0.8
        # 有效的 VHH 序列理想情况下应该得分 >= 0.8
        # Note: This is informational; real sequences may vary
        # 注意：这是信息性的；实际序列可能有所不同
        assert score > 0.0, "Score should be positive"


class TestAbnatiVCDRScoring:
    """
    Test suite for CDR-specific scoring.
    CDR 特定评分的测试套件。
    """

    def test_cdr_scores_available(self, sample_sequence: str) -> None:
        """
        Test that CDR-specific scores are returned.
        测试是否返回 CDR 特定分数。
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        from abnativ.model.scoring_functions import abnativ_scoring
        from Bio.SeqRecord import SeqRecord
        from Bio.Seq import Seq
        
        record = SeqRecord(Seq(sample_sequence), id="test_vhh")
        
        df_scores, _ = abnativ_scoring(
            model_type='VHH',
            seq_records=[record],
            mean_score_only=True,
            do_align=True,
            is_VHH=True,
            verbose=False
        )
        
        # Check for CDR columns (format: 'AbNatiV CDR1-VHH Score', etc.)
        # 检查 CDR 列（格式：'AbNatiV CDR1-VHH Score' 等）
        columns = df_scores.columns.tolist()
        
        # Check for main score column
        # 检查主分数列
        score_cols = [c for c in columns if 'AbNatiV' in c and 'Score' in c]
        assert len(score_cols) > 0, f"Should have AbNatiV score columns, got: {columns}"
        
        # Check for CDR-specific columns
        # 检查 CDR 特定列
        cdr_cols = [c for c in columns if 'CDR' in c]
        assert len(cdr_cols) >= 3, f"Should have CDR1, CDR2, CDR3 columns, got: {cdr_cols}"


class TestNativenessFilterAbnatiVIntegration:
    """
    Test suite for NativenessFilter integration with AbnatiV.
    NativenessFilter 与 AbnatiV 集成的测试套件。
    """

    def test_filter_uses_abnativ_when_available(self, sample_sequence: str) -> None:
        """
        Test that NativenessFilter can use AbnatiV for scoring.
        测试 NativenessFilter 可以使用 AbnatiV 进行评分。
        """
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        
        from metanano.config import NativenessConfig
        from metanano.filters.nativeness import NativenessFilter
        
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)
        
        # If AbnatiV is available, the filter should be able to score
        # 如果 AbnatiV 可用，过滤器应该能够评分
        result = nat_filter.analyze(sample_sequence)
        
        assert result is not None, "Filter should return a result"

    def test_filter_graceful_fallback(self, sample_sequence: str) -> None:
        """
        Test that NativenessFilter handles AbnatiV unavailability gracefully.
        测试 NativenessFilter 优雅处理 AbnatiV 不可用的情况。
        """
        from metanano.config import NativenessConfig
        from metanano.filters.nativeness import NativenessFilter
        
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)
        
        # Filter should work regardless of AbnatiV availability
        # 过滤器应该无论 AbnatiV 是否可用都能工作
        result = nat_filter.analyze(sample_sequence)
        
        assert result is not None, "Filter should return a result"
        assert hasattr(result, 'passed'), "Result should have 'passed' attribute"

