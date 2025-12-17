"""
References / 参考:
    - docs/en/README.md: Section 6 - Examples
    - pytest documentation: fixtures

File / 文件:
    - metanano/tests/tools/conftest.py

Overview / 概述:
    Pytest fixtures for tool integration tests.
    工具集成测试的 Pytest fixtures。

    Provides sample sequences and configuration objects for testing.
    提供用于测试的示例序列和配置对象。

Consumers / 调用方:
    - metanano/tests/tools/test_*.py
"""

import pytest
from typing import Dict, List


# Sample nanobody sequences for testing
# 用于测试的示例纳米抗体序列
SAMPLE_SEQUENCES: Dict[str, str] = {
    # Valid VHH sequence (should pass all filters)
    # 有效的 VHH 序列（应通过所有过滤器）
    "valid_vhh": (
        "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
        "RVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
    ),
    
    # Another valid VHH for diversity testing
    # 另一个用于多样性测试的有效 VHH
    "valid_vhh_2": (
        "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKG"
        "RFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDLGWSFDYWGQGTLVTVSS"
    ),
    
    # Short/invalid sequence (should fail nativeness)
    # 短序列/无效序列（应该无法通过天然性）
    "invalid_short": "EVQLVESGGGLVQPGG",
    
    # Near-duplicate of valid_vhh (for diversity testing)
    # valid_vhh 的近似重复（用于多样性测试）
    "near_duplicate": (
        "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
        "RVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"  # Same as valid_vhh
    ),
}


@pytest.fixture
def sample_sequence() -> str:
    """
    Provide a valid VHH sequence for testing.
    提供用于测试的有效 VHH 序列。
    
    Returns / 返回:
        str: A valid nanobody sequence.
            有效的纳米抗体序列。
    """
    return SAMPLE_SEQUENCES["valid_vhh"]


@pytest.fixture
def sample_sequence_2() -> str:
    """
    Provide a second valid VHH sequence for diversity testing.
    提供第二个用于多样性测试的有效 VHH 序列。
    
    Returns / 返回:
        str: A valid nanobody sequence different from sample_sequence.
            与 sample_sequence 不同的有效纳米抗体序列。
    """
    return SAMPLE_SEQUENCES["valid_vhh_2"]


@pytest.fixture
def invalid_sequence() -> str:
    """
    Provide an invalid/short sequence for testing error handling.
    提供用于测试错误处理的无效/短序列。
    
    Returns / 返回:
        str: An invalid nanobody sequence.
            无效的纳米抗体序列。
    """
    return SAMPLE_SEQUENCES["invalid_short"]


@pytest.fixture
def sequence_batch() -> List[str]:
    """
    Provide a batch of sequences for diversity testing.
    提供用于多样性测试的序列批次。
    
    Returns / 返回:
        List[str]: List of nanobody sequences.
            纳米抗体序列列表。
    """
    return [
        SAMPLE_SEQUENCES["valid_vhh"],
        SAMPLE_SEQUENCES["valid_vhh_2"],
    ]


@pytest.fixture
def duplicate_batch() -> List[str]:
    """
    Provide a batch with near-duplicate sequences for testing diversity rejection.
    提供包含近似重复序列的批次用于测试多样性拒绝。
    
    Returns / 返回:
        List[str]: List with duplicate sequences.
            包含重复序列的列表。
    """
    return [
        SAMPLE_SEQUENCES["valid_vhh"],
        SAMPLE_SEQUENCES["near_duplicate"],
    ]




