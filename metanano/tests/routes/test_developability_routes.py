"""
References / 参考:
    - metanano/routes/developability_routes.py
    - docs/en/README.md: Section 3.6 - Developability Routes

File / 文件:
    - metanano/tests/routes/test_developability_routes.py

Overview / 概述:
    Pytest tests for developability service routes.
    可开发性服务路由的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. POST /developability/analyze - Single sequence analysis
        2. POST /developability/tnp-profile - TNP profile computation
        3. POST /developability/analyze-batch - Batch analysis

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
import requests
from typing import List
from .conftest import skip_if_no_server


@skip_if_no_server
class TestDevelopabilityAnalyzeRoutes:
    """
    Test suite for developability analysis endpoint.
    可开发性分析端点的测试套件。
    """

    def test_developability_analyze_returns_200(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that POST /developability/analyze returns 200.
        测试 POST /developability/analyze 返回 200。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze",
            json={"sequence": sample_sequence},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_developability_analyze_response_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test developability analyze response structure.
        测试可开发性分析响应结构。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        assert "passed" in data, "Response should contain 'passed' field"
        assert isinstance(data["passed"], bool), "'passed' should be boolean"

    def test_developability_analyze_tnp_fields(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that developability response contains TNP information.
        测试可开发性响应包含 TNP 信息。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # TNP-related fields should be present
        # TNP 相关字段应该存在
        tnp_fields = ["cdr3_length", "flags"]
        for field in tnp_fields:
            assert field in data, f"Response should contain '{field}' field"


@skip_if_no_server
class TestTNPProfileRoutes:
    """
    Test suite for TNP profile endpoint.
    TNP 配置文件端点的测试套件。
    """

    def test_tnp_profile_returns_200(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that POST /developability/tnp-profile returns 200.
        测试 POST /developability/tnp-profile 返回 200。
        """
        resp = requests.post(
            f"{base_url}/developability/tnp-profile",
            json={"sequence": sample_sequence},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_tnp_profile_response_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test TNP profile response structure.
        测试 TNP 配置文件响应结构。
        """
        resp = requests.post(
            f"{base_url}/developability/tnp-profile",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["success", "flags"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_tnp_profile_flags_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that TNP flags is a dict mapping property names to colors.
        测试 TNP flags 是一个将属性名映射到颜色的字典。
        """
        resp = requests.post(
            f"{base_url}/developability/tnp-profile",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Flags is a dict mapping property names to color strings
        # Flags 是一个将属性名映射到颜色字符串的字典
        flags = data.get("flags")
        if flags is not None:
            assert isinstance(flags, dict), "'flags' should be a dict"


@skip_if_no_server
class TestDevelopabilityBatchRoutes:
    """
    Test suite for batch developability analysis endpoint.
    批量可开发性分析端点的测试套件。
    """

    def test_batch_analyze_returns_200(
        self, base_url: str, sequence_batch: List[str]
    ) -> None:
        """
        Test that POST /developability/analyze-batch returns 200.
        测试 POST /developability/analyze-batch 返回 200。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze-batch",
            json={"sequences": sequence_batch},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_batch_analyze_response_structure(
        self, base_url: str, sequence_batch: List[str]
    ) -> None:
        """
        Test batch analyze response structure.
        测试批量分析响应结构。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze-batch",
            json={"sequences": sequence_batch},
        )
        data = resp.json()
        
        # Check for results field
        # 检查 results 字段
        assert "results" in data, "Response should contain 'results' field"
        assert isinstance(data["results"], list), "'results' should be a list"

    def test_batch_analyze_result_count(
        self, base_url: str, sequence_batch: List[str]
    ) -> None:
        """
        Test that batch results count matches input count.
        测试批量结果数量与输入数量匹配。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze-batch",
            json={"sequences": sequence_batch},
        )
        data = resp.json()
        
        assert len(data["results"]) == len(sequence_batch), \
            f"Expected {len(sequence_batch)} results, got {len(data['results'])}"

    def test_batch_analyze_individual_results(
        self, base_url: str, sequence_batch: List[str]
    ) -> None:
        """
        Test that each batch result has expected structure.
        测试每个批量结果具有预期结构。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze-batch",
            json={"sequences": sequence_batch},
        )
        data = resp.json()
        
        for i, result in enumerate(data["results"]):
            assert "passed" in result, f"Result {i} should contain 'passed' field"
            assert isinstance(result["passed"], bool), f"Result {i} 'passed' should be boolean"

    def test_batch_analyze_empty_list(self, base_url: str) -> None:
        """
        Test batch analyze with empty sequence list.
        测试使用空序列列表的批量分析。
        """
        resp = requests.post(
            f"{base_url}/developability/analyze-batch",
            json={"sequences": []},
        )
        # Empty list should be handled
        # 空列表应被处理
        assert resp.status_code in [200, 400, 422], f"Unexpected status: {resp.status_code}"

