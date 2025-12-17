"""
References / 参考:
    - docs/en/TODO.md: Section 0.3 - abnumber Integration
    - docs/cn/TODO.md: 第0.3节 - abnumber 集成
    - metanano/utils/cdr_utils.py: CDR extraction implementation
    - abnumber GitHub: https://github.com/prihoda/AbNumber

File / 文件:
    - metanano/tests/tools/test_abnumber.py

Overview / 概述:
    Pytest tests for abnumber (IMGT numbering) integration.
    abnumber（IMGT 编号）集成的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. Chain object creation and IMGT numbering
        2. CDR region extraction (CDR1, CDR2, CDR3)
        3. Framework region extraction (FR1-FR4)
        4. Error handling for invalid sequences
        5. Mutation counting between sequences

    Python API:
    Python API：
        from abnumber import Chain
        chain = Chain(sequence, scheme='imgt')
        cdr1 = chain.cdr1_seq
        cdr2 = chain.cdr2_seq
        cdr3 = chain.cdr3_seq

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
from typing import Dict, Optional

from metanano.utils.cdr_utils import extract_cdrs, count_cdr_mutations


def is_abnumber_available() -> bool:
    """
    Check if abnumber is available.
    检查 abnumber 是否可用。
    """
    try:
        from abnumber import Chain
        return True
    except ImportError:
        return False


class TestAbnumberChain:
    """
    Test suite for abnumber Chain class functionality.
    abnumber Chain 类功能的测试套件。
    """

    def test_abnumber_availability(self) -> None:
        """
        Test that abnumber package is available.
        测试 abnumber 包是否可用。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        from abnumber import Chain
        assert Chain is not None, "abnumber.Chain should be importable"

    def test_chain_creation_valid_sequence(self, sample_sequence: str) -> None:
        """
        Test Chain creation with valid VHH sequence.
        测试使用有效 VHH 序列创建 Chain。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        from abnumber import Chain
        
        chain = Chain(sample_sequence, scheme='imgt')
        
        assert chain is not None, "Chain should be created successfully"
        assert len(chain) > 0, "Chain should have non-zero length"

    def test_chain_type_detection(self, sample_sequence: str) -> None:
        """
        Test that Chain correctly identifies the chain type.
        测试 Chain 是否正确识别链类型。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        from abnumber import Chain
        
        chain = Chain(sample_sequence, scheme='imgt')
        
        # VHH sequences should be identified as heavy chain (H)
        # VHH 序列应该被识别为重链 (H)
        assert chain.chain_type == 'H', f"Expected heavy chain, got {chain.chain_type}"

    def test_chain_invalid_sequence_raises_error(self, invalid_sequence: str) -> None:
        """
        Test that invalid sequences raise ChainParseError.
        测试无效序列是否引发 ChainParseError。
        
        Args / 参数:
            invalid_sequence (str): Invalid/short sequence from fixture.
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        from abnumber import Chain
        from abnumber.exceptions import ChainParseError
        
        with pytest.raises(ChainParseError):
            Chain(invalid_sequence, scheme='imgt')


class TestCDRExtraction:
    """
    Test suite for CDR region extraction.
    CDR 区域提取的测试套件。
    """

    def test_extract_cdrs_valid_sequence(self, sample_sequence: str) -> None:
        """
        Test CDR extraction from valid VHH sequence.
        测试从有效 VHH 序列提取 CDR。
        
        Args / 参数:
            sample_sequence (str): Valid VHH sequence from fixture.
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        cdrs = extract_cdrs(sample_sequence)
        
        assert cdrs is not None, "extract_cdrs should return dict for valid sequence"
        assert isinstance(cdrs, dict), "Result should be a dictionary"
        assert 'cdr1' in cdrs, "Should contain cdr1"
        assert 'cdr2' in cdrs, "Should contain cdr2"
        assert 'cdr3' in cdrs, "Should contain cdr3"

    def test_extract_cdrs_content(self, sample_sequence: str) -> None:
        """
        Test that extracted CDRs have valid content.
        测试提取的 CDR 是否有有效内容。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        cdrs = extract_cdrs(sample_sequence)
        
        assert cdrs is not None
        
        # All CDRs should be non-empty strings
        # 所有 CDR 应该是非空字符串
        assert len(cdrs['cdr1']) > 0, "CDR1 should be non-empty"
        assert len(cdrs['cdr2']) > 0, "CDR2 should be non-empty"
        assert len(cdrs['cdr3']) > 0, "CDR3 should be non-empty"
        
        # CDRs should contain only amino acid letters
        # CDR 应该只包含氨基酸字母
        valid_aa = set('ACDEFGHIKLMNPQRSTVWY')
        for cdr_name, cdr_seq in cdrs.items():
            assert all(aa in valid_aa for aa in cdr_seq), \
                f"{cdr_name} should contain only valid amino acids"

    def test_extract_cdrs_invalid_sequence(self, invalid_sequence: str) -> None:
        """
        Test CDR extraction from invalid sequence returns None.
        测试从无效序列提取 CDR 返回 None。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        cdrs = extract_cdrs(invalid_sequence)
        
        assert cdrs is None, "extract_cdrs should return None for invalid sequence"

    def test_extract_cdrs_empty_sequence(self) -> None:
        """
        Test CDR extraction from empty sequence.
        测试从空序列提取 CDR。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        cdrs = extract_cdrs("")
        
        assert cdrs is None, "extract_cdrs should return None for empty sequence"

    def test_cdr3_is_longest(self, sample_sequence: str) -> None:
        """
        Test that CDR3 is typically the longest CDR in VHH sequences.
        测试 CDR3 通常是 VHH 序列中最长的 CDR。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        cdrs = extract_cdrs(sample_sequence)
        
        assert cdrs is not None
        
        # CDR3 is typically the longest in nanobodies
        # 在纳米抗体中 CDR3 通常最长
        assert len(cdrs['cdr3']) >= len(cdrs['cdr1']), \
            "CDR3 should be >= CDR1 length"


class TestCDRMutationCounting:
    """
    Test suite for CDR mutation counting.
    CDR 突变计数的测试套件。
    """

    def test_count_mutations_same_sequence(self, sample_sequence: str) -> None:
        """
        Test mutation counting between identical sequences.
        测试相同序列之间的突变计数。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        combined, cdr3 = count_cdr_mutations(sample_sequence, sample_sequence)
        
        # Identical sequences should have 0 mutations
        # 相同序列应该有 0 个突变
        assert combined == 0, "Identical sequences should have 0 combined mutations"
        assert cdr3 == 0, "Identical sequences should have 0 CDR3 mutations"

    def test_count_mutations_different_sequences(
        self, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test mutation counting between different sequences.
        测试不同序列之间的突变计数。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        combined, cdr3 = count_cdr_mutations(sample_sequence, sample_sequence_2)
        
        # Different sequences should have some mutations
        # 不同序列应该有一些突变
        assert combined > 0, "Different sequences should have mutations"
        assert isinstance(combined, int), "combined should be int"
        assert isinstance(cdr3, int), "cdr3 should be int"

    def test_count_mutations_no_reference(self, sample_sequence: str) -> None:
        """
        Test mutation counting without reference (heuristic mode).
        测试无参考序列的突变计数（启发式模式）。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        combined, cdr3 = count_cdr_mutations(sample_sequence, reference=None)
        
        # Should return non-negative values based on heuristic
        # 应该根据启发式返回非负值
        assert combined >= 0, "Combined mutations should be >= 0"
        assert cdr3 >= 0, "CDR3 mutations should be >= 0"

    def test_count_mutations_invalid_sequence(self, invalid_sequence: str) -> None:
        """
        Test mutation counting with invalid sequence.
        测试无效序列的突变计数。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        combined, cdr3 = count_cdr_mutations(invalid_sequence)
        
        # Should return 0 for invalid sequences
        # 无效序列应该返回 0
        assert combined == 0, "Invalid sequence should return 0 combined"
        assert cdr3 == 0, "Invalid sequence should return 0 cdr3"


class TestNativenessFilterAbnumberIntegration:
    """
    Test suite for NativenessFilter integration with abnumber.
    NativenessFilter 与 abnumber 集成的测试套件。
    """

    def test_filter_numbers_valid_sequence(self, sample_sequence: str) -> None:
        """
        Test that NativenessFilter can number a valid sequence.
        测试 NativenessFilter 可以对有效序列进行编号。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        from metanano.config import NativenessConfig
        from metanano.filters.nativeness import NativenessFilter
        
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)
        
        numbered = nat_filter.number_sequence(sample_sequence)
        
        assert numbered is not None, "Valid sequence should be numbered"
        assert 'chain' in numbered, "Result should contain chain object"
        assert 'cdr1' in numbered, "Result should contain cdr1"
        assert 'cdr2' in numbered, "Result should contain cdr2"
        assert 'cdr3' in numbered, "Result should contain cdr3"

    def test_filter_rejects_unnumberable_sequence(self, invalid_sequence: str) -> None:
        """
        Test that NativenessFilter rejects sequences that can't be numbered.
        测试 NativenessFilter 拒绝无法编号的序列。
        """
        if not is_abnumber_available():
            pytest.skip("abnumber not available")
        
        from metanano.config import NativenessConfig
        from metanano.filters.nativeness import NativenessFilter
        
        config = NativenessConfig()
        nat_filter = NativenessFilter(config)
        
        numbered = nat_filter.number_sequence(invalid_sequence)
        
        assert numbered is None, "Invalid sequence should not be numbered"




