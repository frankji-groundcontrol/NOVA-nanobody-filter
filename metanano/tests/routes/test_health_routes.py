"""
References / 参考:
    - metanano/routes/health.py
    - docs/en/README.md: Section 3.1 - Health Check Routes

File / 文件:
    - metanano/tests/routes/test_health_routes.py

Overview / 概述:
    Pytest tests for health check routes.
    健康检查路由的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. GET /health - Basic health check
        2. Response structure and status codes

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
import requests
from .conftest import skip_if_no_server, get_base_url


@skip_if_no_server
class TestHealthRoutes:
    """
    Test suite for health check endpoints.
    健康检查端点的测试套件。
    """

    def test_health_check_returns_200(self, base_url: str) -> None:
        """
        Test that GET /health returns 200 OK.
        测试 GET /health 返回 200 OK。
        """
        resp = requests.get(f"{base_url}/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_health_check_returns_json(self, base_url: str) -> None:
        """
        Test that GET /health returns valid JSON.
        测试 GET /health 返回有效 JSON。
        """
        resp = requests.get(f"{base_url}/health")
        data = resp.json()
        assert isinstance(data, dict), "Response should be a JSON object"

    def test_health_check_status_field(self, base_url: str) -> None:
        """
        Test that health response contains status field.
        测试健康响应包含 status 字段。
        """
        resp = requests.get(f"{base_url}/health")
        data = resp.json()
        assert "status" in data, "Response should contain 'status' field"
        assert data["status"] == "healthy", f"Status should be 'healthy', got {data['status']}"

    def test_health_check_service_field(self, base_url: str) -> None:
        """
        Test that health response contains service field.
        测试健康响应包含 service 字段。
        """
        resp = requests.get(f"{base_url}/health")
        data = resp.json()
        assert "service" in data, "Response should contain 'service' field"
        assert isinstance(data["service"], str), "Service should be a string"

