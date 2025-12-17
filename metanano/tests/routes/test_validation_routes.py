"""
References / 参考:
    - metanano/routes/validation_routes.py
    - docs/en/README.md: Section 3.2 - Validation Routes

File / 文件:
    - metanano/tests/routes/test_validation_routes.py

Overview / 概述:
    Pytest tests for validation pipeline routes.
    验证管道路由的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. POST /validate - Single sequence validation
        2. POST /validate/batch - Batch validation
        3. Request/response structure validation
        4. Error handling for invalid inputs

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
import requests
from typing import Dict, Any, List
from .conftest import skip_if_no_server


@skip_if_no_server
class TestValidationRoutes:
    """
    Test suite for validation endpoints.
    验证端点的测试套件。
    """

    def test_validate_single_sequence(
        self, base_url: str, validation_request_payload: Dict[str, Any]
    ) -> None:
        """
        Test POST /validate with a valid sequence.
        测试使用有效序列的 POST /validate。
        """
        resp = requests.post(
            f"{base_url}/validate",
            json=validation_request_payload,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict), "Response should be a JSON object"

    def test_validate_response_structure(
        self, base_url: str, validation_request_payload: Dict[str, Any]
    ) -> None:
        """
        Test that validation response has expected structure.
        测试验证响应具有预期结构。
        """
        resp = requests.post(
            f"{base_url}/validate",
            json=validation_request_payload,
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["validation_status", "details"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_validate_status_field_is_string(
        self, base_url: str, validation_request_payload: Dict[str, Any]
    ) -> None:
        """
        Test that 'validation_status' field is a string.
        测试 'validation_status' 字段是字符串。
        """
        resp = requests.post(
            f"{base_url}/validate",
            json=validation_request_payload,
        )
        data = resp.json()
        assert isinstance(data["validation_status"], str), "'validation_status' should be a string"
        assert data["validation_status"] in ["Passed", "Failed"], \
            f"validation_status should be 'Passed' or 'Failed', got {data['validation_status']}"

    def test_validate_missing_sequence(self, base_url: str) -> None:
        """
        Test that missing sequence returns 422.
        测试缺少序列返回 422。
        """
        resp = requests.post(
            f"{base_url}/validate",
            json={},
        )
        assert resp.status_code == 422, f"Expected 422 for missing sequence, got {resp.status_code}"

    def test_validate_empty_sequence(self, base_url: str) -> None:
        """
        Test validation with empty sequence.
        测试使用空序列的验证。
        """
        resp = requests.post(
            f"{base_url}/validate",
            json={"sequence": ""},
        )
        # Empty sequence should be handled (either 400/422 or passed=false)
        # 空序列应被处理（返回 400/422 或 passed=false）
        assert resp.status_code in [200, 400, 422], f"Unexpected status: {resp.status_code}"

    def test_validate_invalid_sequence(
        self, base_url: str, invalid_sequence: str
    ) -> None:
        """
        Test validation with invalid/short sequence.
        测试使用无效/短序列的验证。
        """
        resp = requests.post(
            f"{base_url}/validate",
            json={"sequence": invalid_sequence},
        )
        # Short sequence may be rejected by validation (422) or return a result
        # 短序列可能被验证拒绝 (422) 或返回结果
        assert resp.status_code in [200, 422], f"Expected 200 or 422, got {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            # Invalid sequences should have validation_status
            # 无效序列应该有 validation_status
            assert "validation_status" in data, "Response should contain 'validation_status' field"


@skip_if_no_server
class TestBatchValidationRoutes:
    """
    Test suite for batch validation endpoints.
    批量验证端点的测试套件。
    """

    def test_batch_validate(
        self, base_url: str, batch_validation_payload: Dict[str, Any]
    ) -> None:
        """
        Test POST /validate/batch with multiple sequences.
        测试使用多个序列的 POST /validate/batch。
        """
        resp = requests.post(
            f"{base_url}/validate/batch",
            json=batch_validation_payload,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict), "Response should be a JSON object"

    def test_batch_validate_response_structure(
        self, base_url: str, batch_validation_payload: Dict[str, Any]
    ) -> None:
        """
        Test that batch validation response has expected structure.
        测试批量验证响应具有预期结构。
        """
        resp = requests.post(
            f"{base_url}/validate/batch",
            json=batch_validation_payload,
        )
        data = resp.json()
        
        # Check for results field
        # 检查 results 字段
        assert "results" in data, "Response should contain 'results' field"
        assert isinstance(data["results"], list), "'results' should be a list"

    def test_batch_validate_result_count(
        self, base_url: str, sequence_batch: List[str]
    ) -> None:
        """
        Test that batch results count matches input count.
        测试批量结果数量与输入数量匹配。
        """
        payload = {"sequences": sequence_batch}
        resp = requests.post(
            f"{base_url}/validate/batch",
            json=payload,
        )
        data = resp.json()
        
        assert len(data["results"]) == len(sequence_batch), \
            f"Expected {len(sequence_batch)} results, got {len(data['results'])}"

    def test_batch_validate_empty_list(self, base_url: str) -> None:
        """
        Test batch validation with empty sequence list.
        测试使用空序列列表的批量验证。
        """
        resp = requests.post(
            f"{base_url}/validate/batch",
            json={"sequences": []},
        )
        # Empty list should be handled gracefully
        # 空列表应被优雅处理
        assert resp.status_code in [200, 400, 422], f"Unexpected status: {resp.status_code}"

    def test_batch_validate_individual_results(
        self, base_url: str, batch_validation_payload: Dict[str, Any]
    ) -> None:
        """
        Test that each batch result has expected structure.
        测试每个批量结果具有预期结构。
        """
        resp = requests.post(
            f"{base_url}/validate/batch",
            json=batch_validation_payload,
        )
        data = resp.json()
        
        for i, result in enumerate(data["results"]):
            assert "validation_status" in result, f"Result {i} should contain 'validation_status' field"
            assert isinstance(result["validation_status"], str), f"Result {i} 'validation_status' should be string"

