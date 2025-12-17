"""
References / 参考:
    - metanano/routes/nativeness_routes.py
    - docs/en/README.md: Section 3.5 - Nativeness Routes

File / 文件:
    - metanano/tests/routes/test_nativeness_routes.py

Overview / 概述:
    Pytest tests for nativeness service routes.
    天然性服务路由的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. POST /nativeness/analyze - Full nativeness analysis
        2. POST /nativeness/imgt-number - IMGT numbering
        3. POST /nativeness/scores - Score computation

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
import requests
from .conftest import skip_if_no_server


@skip_if_no_server
class TestNativenessAnalyzeRoutes:
    """
    Test suite for nativeness analysis endpoint.
    天然性分析端点的测试套件。
    """

    def test_nativeness_analyze_returns_200(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that POST /nativeness/analyze returns 200.
        测试 POST /nativeness/analyze 返回 200。
        """
        resp = requests.post(
            f"{base_url}/nativeness/analyze",
            json={"sequence": sample_sequence},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_nativeness_analyze_response_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test nativeness analyze response structure.
        测试天然性分析响应结构。
        """
        resp = requests.post(
            f"{base_url}/nativeness/analyze",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["passed", "imgt_numbered"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_nativeness_analyze_cdr_fields(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that nativeness response contains CDR information.
        测试天然性响应包含 CDR 信息。
        """
        resp = requests.post(
            f"{base_url}/nativeness/analyze",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # CDR fields should be present (may be null if numbering failed)
        # CDR 字段应该存在（如果编号失败可能为 null）
        cdr_fields = ["cdr1", "cdr2", "cdr3"]
        for field in cdr_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_nativeness_analyze_score_fields(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that nativeness response contains score fields.
        测试天然性响应包含分数字段。
        """
        resp = requests.post(
            f"{base_url}/nativeness/analyze",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Score fields should be present (may be null if scoring failed)
        # 分数字段应该存在（如果评分失败可能为 null）
        score_fields = ["nativeness_score", "humanness_score"]
        for field in score_fields:
            assert field in data, f"Response should contain '{field}' field"


@skip_if_no_server
class TestIMGTNumberingRoutes:
    """
    Test suite for IMGT numbering endpoint.
    IMGT 编号端点的测试套件。
    """

    def test_imgt_number_returns_200(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that POST /nativeness/imgt-number returns 200.
        测试 POST /nativeness/imgt-number 返回 200。
        """
        resp = requests.post(
            f"{base_url}/nativeness/imgt-number",
            json={"sequence": sample_sequence},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_imgt_number_response_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test IMGT numbering response structure.
        测试 IMGT 编号响应结构。
        """
        resp = requests.post(
            f"{base_url}/nativeness/imgt-number",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["success", "cdr1", "cdr2", "cdr3"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_imgt_number_with_invalid_sequence(
        self, base_url: str, invalid_sequence: str
    ) -> None:
        """
        Test IMGT numbering with invalid sequence.
        测试使用无效序列的 IMGT 编号。
        """
        resp = requests.post(
            f"{base_url}/nativeness/imgt-number",
            json={"sequence": invalid_sequence},
        )
        # Should return 200 with success=false or appropriate error
        # 应返回 200 且 success=false 或适当的错误
        assert resp.status_code in [200, 400], f"Unexpected status: {resp.status_code}"


@skip_if_no_server
class TestNativenessScoresRoutes:
    """
    Test suite for nativeness scores endpoint.
    天然性分数端点的测试套件。
    """

    def test_scores_returns_200(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that POST /nativeness/scores returns 200.
        测试 POST /nativeness/scores 返回 200。
        """
        resp = requests.post(
            f"{base_url}/nativeness/scores",
            json={"sequence": sample_sequence},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_scores_response_structure(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test scores response structure.
        测试分数响应结构。
        """
        resp = requests.post(
            f"{base_url}/nativeness/scores",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # Check for expected fields
        # 检查预期字段
        expected_fields = ["nativeness_score", "humanness_score"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_scores_valid_range(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test that scores are in valid range [0, 1] when available.
        测试分数在有效范围 [0, 1] 内（当可用时）。
        """
        resp = requests.post(
            f"{base_url}/nativeness/scores",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        for field in ["nativeness_score", "humanness_score"]:
            score = data.get(field)
            if score is not None:
                assert 0.0 <= score <= 1.0, f"{field} should be in [0, 1], got {score}"

    def test_scores_with_promb(
        self, base_url: str, sample_sequence: str
    ) -> None:
        """
        Test scores endpoint includes promb score if available.
        测试分数端点是否包含 promb 分数（如果可用）。
        """
        resp = requests.post(
            f"{base_url}/nativeness/scores",
            json={"sequence": sample_sequence},
        )
        data = resp.json()
        
        # promb_score may or may not be present depending on config
        # promb_score 是否存在取决于配置
        if "promb_score" in data:
            score = data["promb_score"]
            if score is not None:
                assert isinstance(score, (int, float)), "promb_score should be numeric"

