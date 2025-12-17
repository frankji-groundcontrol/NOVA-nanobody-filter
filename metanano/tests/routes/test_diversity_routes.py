"""
References / 参考:
    - metanano/routes/diversity_routes.py
    - docs/en/README.md: Section 3.4 - Diversity Routes

File / 文件:
    - metanano/tests/routes/test_diversity_routes.py

Overview / 概述:
    Pytest tests for diversity service routes.
    多样性服务路由的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. POST /diversity/analyze - Single sequence diversity analysis
        2. POST /diversity/batch-check - Batch diversity check
        3. POST /diversity/cdr-mutations - CDR mutation analysis

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
import requests
from typing import List
from .conftest import skip_if_no_server


@skip_if_no_server
class TestDiversityAnalyzeRoutes:
    """
    Test suite for diversity analysis endpoint.
    多样性分析端点的测试套件。
    """

    def test_diversity_analyze_returns_200(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that POST /diversity/analyze returns 200.
        测试 POST /diversity/analyze 返回 200。
        """
        resp = requests.post(
            f"{base_url}/diversity/analyze",
            json={"sequence": sample_sequence},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_diversity_analyze_response_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test diversity analyze response structure.
        测试多样性分析响应结构。
        """
        resp = requests.post(
            f"{base_url}/diversity/analyze",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        assert "passed" in data, "Response should contain 'passed' field"
        assert isinstance(data["passed"], bool), "'passed' should be boolean"

    def test_diversity_analyze_with_existing_sequences(
        self, base_url: str, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test diversity analysis with existing sequences context.
        测试带有现有序列上下文的多样性分析。
        """
        resp = requests.post(
            f"{base_url}/diversity/analyze",
            json={
                "sequence": sample_sequence,
                "existing_sequences": [sample_sequence_2],
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "passed" in data


@skip_if_no_server
class TestDiversityBatchRoutes:
    """
    Test suite for batch diversity check endpoint.
    批量多样性检查端点的测试套件。
    
    Note: /diversity/batch-check requires a query sequence and batch_sequences
    to compare against, not just a list of sequences.
    """

    def test_batch_check_returns_200(
        self, base_url: str, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test that POST /diversity/batch-check returns 200.
        测试 POST /diversity/batch-check 返回 200。
        """
        resp = requests.post(
            f"{base_url}/diversity/batch-check",
            json={
                "sequence": sample_sequence,
                "batch_sequences": [sample_sequence_2],
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_batch_check_response_structure(
        self, base_url: str, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test batch check response structure.
        测试批量检查响应结构。
        """
        resp = requests.post(
            f"{base_url}/diversity/batch-check",
            json={
                "sequence": sample_sequence,
                "batch_sequences": [sample_sequence_2],
            },
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["passed", "max_identity"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_batch_check_max_identity(
        self, base_url: str, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test that batch check returns max_identity.
        测试批量检查返回 max_identity。
        """
        resp = requests.post(
            f"{base_url}/diversity/batch-check",
            json={
                "sequence": sample_sequence,
                "batch_sequences": [sample_sequence_2],
            },
        )
        data = resp.json()
        
        if data["max_identity"] is not None:
            assert 0.0 <= data["max_identity"] <= 1.0, \
                f"max_identity should be in [0, 1], got {data['max_identity']}"

    def test_batch_check_with_same_sequence(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test batch check with same sequence (high identity).
        测试使用相同序列的批量检查（高相似度）。
        """
        resp = requests.post(
            f"{base_url}/diversity/batch-check",
            json={
                "sequence": sample_sequence,
                "batch_sequences": [sample_sequence],  # Same sequence
            },
        )
        data = resp.json()
        
        # Same sequence should have high identity
        # 相同序列应该有高相似度
        assert "passed" in data
        if data["max_identity"] is not None:
            assert data["max_identity"] >= 0.9, "Same sequence should have high identity"

    def test_batch_check_missing_fields(self, base_url: str) -> None:
        """
        Test batch check with missing fields.
        测试缺少字段的批量检查。
        """
        resp = requests.post(
            f"{base_url}/diversity/batch-check",
            json={},
        )
        # Missing fields should return 422
        # 缺少字段应返回 422
        assert resp.status_code == 422, f"Unexpected status: {resp.status_code}"


@skip_if_no_server
class TestCDRMutationRoutes:
    """
    Test suite for CDR mutation analysis endpoint.
    CDR 突变分析端点的测试套件。
    """

    def test_cdr_mutations_returns_200(
        self, base_url: str, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test that POST /diversity/cdr-mutations returns 200.
        测试 POST /diversity/cdr-mutations 返回 200。
        """
        resp = requests.post(
            f"{base_url}/diversity/cdr-mutations",
            json={
                "sequence": sample_sequence,
                "reference_sequence": sample_sequence_2,
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_cdr_mutations_response_structure(
        self, base_url: str, sample_sequence: str, sample_sequence_2: str
    ) -> None:
        """
        Test CDR mutations response structure.
        测试 CDR 突变响应结构。
        """
        resp = requests.post(
            f"{base_url}/diversity/cdr-mutations",
            json={
                "sequence": sample_sequence,
                "reference_sequence": sample_sequence_2,
            },
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["passed", "cdrs_combined_mutations", "cdr3_mutations"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_cdr_mutations_same_sequence(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test CDR mutations with same sequence (should have 0 mutations).
        测试使用相同序列的 CDR 突变（应该有 0 个突变）。
        """
        resp = requests.post(
            f"{base_url}/diversity/cdr-mutations",
            json={
                "sequence": sample_sequence,
                "reference_sequence": sample_sequence,
            },
        )
        data = resp.json()
        
        # Same sequence should have 0 mutations
        # 相同序列应该有 0 个突变
        assert data.get("cdrs_combined_mutations", 0) == 0 or data.get("cdrs_combined_mutations") is None
        assert data.get("cdr3_mutations", 0) == 0 or data.get("cdr3_mutations") is None

