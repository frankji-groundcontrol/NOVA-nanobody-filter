"""
References / 参考:
    - metanano/tests/tools/conftest.py
    - FastAPI TestClient documentation
    - pytest fixtures

File / 文件:
    - metanano/tests/routes/conftest.py

Overview / 概述:
    Pytest fixtures for route integration tests.
    路由集成测试的 Pytest fixtures。

    Provides:
    提供：
        - TestClient for FastAPI app
        - Sample sequences and payloads
        - Server availability checks

Consumers / 调用方:
    - metanano/tests/routes/test_*.py
"""

import os
import pytest
import requests
from typing import Dict, List, Any, Optional


# Default test server URL
# 默认测试服务器 URL
DEFAULT_BASE_URL = "http://localhost:5000"


def get_base_url() -> str:
    """
    Get the base URL for testing.
    获取测试用的基础 URL。

    Returns / 返回:
        str: Base URL from environment or default.
            来自环境变量或默认的基础 URL。
    """
    return os.environ.get("METANANO_TEST_URL", DEFAULT_BASE_URL)


def is_server_running() -> bool:
    """
    Check if the test server is running.
    检查测试服务器是否正在运行。

    Returns / 返回:
        bool: True if server responds to health check.
            如果服务器响应健康检查则返回 True。
    """
    try:
        resp = requests.get(f"{get_base_url()}/health", timeout=2)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


# Skip reason if server is not running
# 服务器未运行时的跳过原因
skip_if_no_server = pytest.mark.skipif(
    not is_server_running(),
    reason="Test server not running. Start with: python -m uvicorn metanano.app:app --host 0.0.0.0 --port 5000"
)


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
    
    # Third valid VHH
    # 第三个有效的 VHH
    "valid_vhh_3": (
        "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYMSWVRQAPGKGLEWVSSIRSGGGRTYYSESVKG"
        "RFTISRDNSKNTLYLQMNSLRAEDTAVYYCARDLILGNFDYWGQGTLVTVSS"
    ),
    
    # Short/invalid sequence (should fail nativeness)
    # 短序列/无效序列（应该无法通过天然性）
    "invalid_short": "EVQLVESGGGLVQPGG",
    
    # Non-antibody sequence (random protein)
    # 非抗体序列（随机蛋白质）
    "non_antibody": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQQIAAA",
}


@pytest.fixture(scope="session")
def base_url() -> str:
    """
    Provide the base URL for API requests.
    提供 API 请求的基础 URL。

    Returns / 返回:
        str: The server base URL.
            服务器基础 URL。
    """
    return get_base_url()


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
    Provide a second valid VHH sequence.
    提供第二个有效 VHH 序列。

    Returns / 返回:
        str: A different valid nanobody sequence.
            不同的有效纳米抗体序列。
    """
    return SAMPLE_SEQUENCES["valid_vhh_2"]


@pytest.fixture
def sample_sequence_3() -> str:
    """
    Provide a third valid VHH sequence.
    提供第三个有效 VHH 序列。

    Returns / 返回:
        str: Another valid nanobody sequence.
            另一个有效的纳米抗体序列。
    """
    return SAMPLE_SEQUENCES["valid_vhh_3"]


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
    Provide a batch of valid sequences for testing.
    提供用于测试的有效序列批次。

    Returns / 返回:
        List[str]: List of nanobody sequences.
            纳米抗体序列列表。
    """
    return [
        SAMPLE_SEQUENCES["valid_vhh"],
        SAMPLE_SEQUENCES["valid_vhh_2"],
        SAMPLE_SEQUENCES["valid_vhh_3"],
    ]


@pytest.fixture
def validation_request_payload(sample_sequence: str) -> Dict[str, Any]:
    """
    Provide a validation request payload.
    提供验证请求的有效载荷。

    Args / 参数:
        sample_sequence (str): The sequence to validate.
            要验证的序列。

    Returns / 返回:
        Dict[str, Any]: Request payload for /validate endpoint.
            /validate 端点的请求有效载荷。
    """
    return {"sequence": sample_sequence}


@pytest.fixture
def batch_validation_payload(sequence_batch: List[str]) -> Dict[str, Any]:
    """
    Provide a batch validation request payload.
    提供批量验证请求的有效载荷。

    Args / 参数:
        sequence_batch (List[str]): Sequences to validate.
            要验证的序列列表。

    Returns / 返回:
        Dict[str, Any]: Request payload for /validate/batch endpoint.
            /validate/batch 端点的请求有效载荷。
    """
    return {"sequences": sequence_batch}

