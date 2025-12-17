"""
References / 参考:
    - docs/en/TODO.md: Section 0.1 - TNP Integration
    - docs/cn/TODO.md: 第0.1节 - TNP 集成
    - metanano/utils/tnp_wrapper.py: TNPWrapper implementation
    - TNP GitHub: https://github.com/oxpig/TNP

File / 文件:
    - metanano/tests/tools/test_tnp.py

Overview / 概述:
    Pytest tests for TNP (Therapeutic Nanobody Profiler) integration.
    TNP（治疗性纳米抗体分析器）集成的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. TNP CLI availability check
        2. TNP profiling with valid sequences
        3. TNP result parsing and validation
        4. Red Region criteria evaluation
        5. Integration with DevelopabilityFilter

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
from typing import Optional

from metanano.utils.tnp_wrapper import TNPWrapper, TNPResult
from metanano.config import DevelopabilityConfig
from metanano.filters.developability import DevelopabilityFilter, DevelopabilityResult


class TestTNPWrapper:
    """
    Test suite for TNPWrapper class.
    TNPWrapper 类的测试套件。
    """

    def test_tnp_availability(self) -> None:
        """
        Test that TNP CLI is available in the environment.
        测试 TNP CLI 在环境中是否可用。
        
        This test verifies that the TNP executable can be found.
        此测试验证是否可以找到 TNP 可执行文件。
        """
        tnp = TNPWrapper()
        is_available = tnp._check_tnp_available()
        
        # Skip subsequent tests if TNP is not available
        # 如果 TNP 不可用，跳过后续测试
        if not is_available:
            pytest.skip("TNP CLI not available in environment")
        
        assert is_available, "TNP should be available in metanano conda environment"

    def test_profile_valid_sequence(self, sample_sequence: str) -> None:
        """
        Test TNP profiling with a valid VHH sequence.
        使用有效的 VHH 序列测试 TNP 分析。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
                来自 fixture 的有效 VHH 序列。
        
        Expected behavior / 预期行为:
            - TNP should return a valid TNPResult
            - All required fields should be populated
            - CDR lengths should be within expected ranges
        """
        tnp = TNPWrapper()
        
        if not tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = tnp.profile(sample_sequence, name="test_valid")
        
        assert result is not None, "TNP should return a result for valid sequence"
        assert isinstance(result, TNPResult), "Result should be TNPResult instance"
        assert result.name == "test_valid", "Name should match input"
        assert result.total_cdr_length > 0, "Total CDR length should be positive"
        assert result.cdr3_length > 0, "CDR3 length should be positive"
        assert result.cdr3_compactness > 0, "CDR3 compactness should be positive"

    def test_profile_result_fields(self, sample_sequence: str) -> None:
        """
        Test that all TNP result fields are properly populated.
        测试所有 TNP 结果字段是否正确填充。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
                来自 fixture 的有效 VHH 序列。
        """
        tnp = TNPWrapper()
        
        if not tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = tnp.profile(sample_sequence, name="test_fields")
        
        assert result is not None
        
        # Check all required fields exist and have valid values
        # 检查所有必需字段是否存在并有有效值
        assert hasattr(result, 'total_cdr_length'), "Should have total_cdr_length"
        assert hasattr(result, 'cdr3_length'), "Should have cdr3_length"
        assert hasattr(result, 'cdr3_compactness'), "Should have cdr3_compactness"
        assert hasattr(result, 'psh'), "Should have psh (surface hydrophobic patches)"
        assert hasattr(result, 'ppc'), "Should have ppc (positive charge patches)"
        assert hasattr(result, 'pnc'), "Should have pnc (negative charge patches)"
        assert hasattr(result, 'flags'), "Should have flags dict"
        
        # Check flags structure
        # 检查标志结构
        assert isinstance(result.flags, dict), "Flags should be a dictionary"

    def test_profile_to_dict_conversion(self, sample_sequence: str) -> None:
        """
        Test TNPResult.to_profile_dict() conversion for filter integration.
        测试 TNPResult.to_profile_dict() 转换以用于过滤器集成。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
                来自 fixture 的有效 VHH 序列。
        """
        tnp = TNPWrapper()
        
        if not tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = tnp.profile(sample_sequence)
        assert result is not None
        
        profile_dict = result.to_profile_dict()
        
        # Verify dict has keys expected by DevelopabilityFilter
        # 验证字典具有 DevelopabilityFilter 期望的键
        expected_keys = [
            'total_cdr_length',
            'cdr3_length', 
            'cdr3_compactness',
            'surface_hydrophobic_patches',
            'positive_charge_patches',
            'negative_charge_patches',
        ]
        
        for key in expected_keys:
            assert key in profile_dict, f"Profile dict should have '{key}'"

    def test_profile_with_auto_name(self, sample_sequence: str) -> None:
        """
        Test TNP profiling with auto-generated name.
        测试使用自动生成名称的 TNP 分析。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
                来自 fixture 的有效 VHH 序列。
        """
        tnp = TNPWrapper()
        
        if not tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        # Call without explicit name
        # 不使用显式名称调用
        result = tnp.profile(sample_sequence)
        
        assert result is not None, "Should work with auto-generated name"
        assert result.name.startswith("seq_"), "Auto name should start with 'seq_'"


class TestTNPRedRegionCriteria:
    """
    Test suite for TNP Red Region criteria validation.
    TNP 红区标准验证的测试套件。
    
    Red Region criteria (REJECT if any triggered):
    红区标准（如果触发任何一个则拒绝）：
        - Total CDR Length: L < 20 OR L > 39
        - CDR3 Length: L3 < 5 OR L3 > 23
        - CDR3 Compactness: C < 0.56 OR C > 1.61
        - Surface Hydrophobic Patches: PSH < 73.4 OR PSH > 155.47
        - Positive Charge Patches: PPC > 1.18
        - Negative Charge Patches: PNC > 1.88
    """

    def test_valid_sequence_passes_red_region(self, sample_sequence: str) -> None:
        """
        Test that a valid VHH sequence passes all Red Region criteria.
        测试有效的 VHH 序列通过所有红区标准。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
                来自 fixture 的有效 VHH 序列。
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        # Skip if TNP not available
        # 如果 TNP 不可用则跳过
        if not dev_filter._tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = dev_filter.analyze(sample_sequence)
        
        assert result.passed, f"Valid sequence should pass. Red flags: {result.red_flags}"
        assert result.red_flags is None or len(result.red_flags) == 0

    def test_cdr_length_within_range(self, sample_sequence: str) -> None:
        """
        Test that CDR lengths are within acceptable ranges.
        测试 CDR 长度在可接受范围内。
        
        Valid ranges:
        有效范围：
            - Total CDR Length: 20 ≤ L ≤ 39
            - CDR3 Length: 5 ≤ L3 ≤ 23
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        if not dev_filter._tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = dev_filter.analyze(sample_sequence)
        
        # Check Total CDR Length
        # 检查总 CDR 长度
        if result.total_cdr_length is not None:
            assert 20 <= result.total_cdr_length <= 39, \
                f"Total CDR length {result.total_cdr_length} should be in [20, 39]"
        
        # Check CDR3 Length
        # 检查 CDR3 长度
        if result.cdr3_length is not None:
            assert 5 <= result.cdr3_length <= 23, \
                f"CDR3 length {result.cdr3_length} should be in [5, 23]"

    def test_compactness_within_range(self, sample_sequence: str) -> None:
        """
        Test that CDR3 compactness is within acceptable range.
        测试 CDR3 紧凑度在可接受范围内。
        
        Valid range: 0.56 ≤ C ≤ 1.61
        有效范围：0.56 ≤ C ≤ 1.61
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        if not dev_filter._tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = dev_filter.analyze(sample_sequence)
        
        if result.cdr3_compactness is not None:
            assert 0.56 <= result.cdr3_compactness <= 1.61, \
                f"CDR3 compactness {result.cdr3_compactness} should be in [0.56, 1.61]"

    def test_charge_patches_within_threshold(self, sample_sequence: str) -> None:
        """
        Test that charge patch scores are within acceptable thresholds.
        测试电荷斑块分数在可接受阈值内。
        
        Thresholds (REJECT if exceeded):
        阈值（超过则拒绝）：
            - PPC ≤ 1.18
            - PNC ≤ 1.88
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        if not dev_filter._tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = dev_filter.analyze(sample_sequence)
        
        if result.positive_charge_patches is not None:
            assert result.positive_charge_patches <= 1.18, \
                f"PPC {result.positive_charge_patches} should be ≤ 1.18"
        
        if result.negative_charge_patches is not None:
            assert result.negative_charge_patches <= 1.88, \
                f"PNC {result.negative_charge_patches} should be ≤ 1.88"


class TestDevelopabilityFilterIntegration:
    """
    Test suite for DevelopabilityFilter integration with TNP.
    DevelopabilityFilter 与 TNP 集成的测试套件。
    """

    def test_filter_returns_developability_result(self, sample_sequence: str) -> None:
        """
        Test that DevelopabilityFilter returns proper result type.
        测试 DevelopabilityFilter 返回正确的结果类型。
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        if not dev_filter._tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = dev_filter.analyze(sample_sequence)
        
        assert isinstance(result, DevelopabilityResult), \
            "Should return DevelopabilityResult"

    def test_filter_to_dict_conversion(self, sample_sequence: str) -> None:
        """
        Test DevelopabilityResult.to_dict() for API response serialization.
        测试 DevelopabilityResult.to_dict() 用于 API 响应序列化。
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        if not dev_filter._tnp._check_tnp_available():
            pytest.skip("TNP CLI not available")
        
        result = dev_filter.analyze(sample_sequence)
        result_dict = result.to_dict()
        
        assert 'passed' in result_dict, "Dict should have 'passed' key"
        assert isinstance(result_dict['passed'], bool), "'passed' should be boolean"

    def test_filter_handles_tnp_unavailable(self) -> None:
        """
        Test graceful handling when TNP is not available.
        测试 TNP 不可用时的优雅处理。
        """
        config = DevelopabilityConfig()
        dev_filter = DevelopabilityFilter(config)
        
        # Mock TNP as unavailable
        # 模拟 TNP 不可用
        original_check = dev_filter._tnp._check_tnp_available
        dev_filter._tnp._check_tnp_available = lambda: False
        
        try:
            result = dev_filter.analyze("EVQLVESGGGLVQPGG")
            
            assert not result.passed, "Should fail when TNP unavailable"
            assert result.reason is not None, "Should have failure reason"
        finally:
            dev_filter._tnp._check_tnp_available = original_check




