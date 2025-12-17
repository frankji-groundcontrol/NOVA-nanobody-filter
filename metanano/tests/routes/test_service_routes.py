"""
References / 参考:
    - metanano/routes/service_routes.py
    - docs/en/README.md: Section 3.7 - Service Routes

File / 文件:
    - metanano/tests/routes/test_service_routes.py

Overview / 概述:
    Pytest tests for service management routes.
    服务管理路由的 Pytest 测试。

    Tests cover:
    测试覆盖：
        1. GET /services/status - Service status
        2. GET /services/gpu - GPU scheduler status
        3. POST /services/gpu/control - GPU control

Consumers / 调用方:
    - pytest (test runner)
"""

import pytest
import requests
from .conftest import skip_if_no_server


@skip_if_no_server
class TestServiceStatusRoutes:
    """
    Test suite for service status endpoints.
    服务状态端点的测试套件。
    """

    def test_service_status_returns_200(self, base_url: str) -> None:
        """
        Test that GET /services/status returns 200.
        测试 GET /services/status 返回 200。
        """
        resp = requests.get(f"{base_url}/services/status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_service_status_structure(self, base_url: str) -> None:
        """
        Test service status response structure.
        测试服务状态响应结构。
        """
        resp = requests.get(f"{base_url}/services/status")
        data = resp.json()
        
        expected_fields = ["initialized", "semaphores", "gpu_scheduler"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_service_status_semaphores(self, base_url: str) -> None:
        """
        Test that semaphores info is available.
        测试信号量信息是否可用。
        """
        resp = requests.get(f"{base_url}/services/status")
        data = resp.json()
        
        assert "semaphores" in data, "Response should contain 'semaphores'"
        semaphores = data["semaphores"]
        assert isinstance(semaphores, dict), "'semaphores' should be a dict"


@skip_if_no_server
class TestGPUSchedulerRoutes:
    """
    Test suite for GPU scheduler endpoints.
    GPU 调度器端点的测试套件。
    """

    def test_gpu_status_returns_200(self, base_url: str) -> None:
        """
        Test that GET /services/gpu returns 200.
        测试 GET /services/gpu 返回 200。
        """
        resp = requests.get(f"{base_url}/services/gpu")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_gpu_status_structure(self, base_url: str) -> None:
        """
        Test GPU status response structure.
        测试 GPU 状态响应结构。
        """
        resp = requests.get(f"{base_url}/services/gpu")
        data = resp.json()
        
        expected_fields = ["enabled", "total_gpus", "available_gpus", "queue_size", "gpus"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"

    def test_gpu_status_types(self, base_url: str) -> None:
        """
        Test GPU status field types.
        测试 GPU 状态字段类型。
        """
        resp = requests.get(f"{base_url}/services/gpu")
        data = resp.json()
        
        assert isinstance(data["enabled"], bool), "'enabled' should be boolean"
        assert isinstance(data["total_gpus"], int), "'total_gpus' should be integer"
        assert isinstance(data["available_gpus"], int), "'available_gpus' should be integer"
        assert isinstance(data["queue_size"], int), "'queue_size' should be integer"
        assert isinstance(data["gpus"], dict), "'gpus' should be a dict"

    def test_gpu_control_enable(self, base_url: str) -> None:
        """
        Test GPU enable control action.
        测试 GPU 启用控制操作。
        """
        # First get current status
        # 首先获取当前状态
        status_resp = requests.get(f"{base_url}/services/gpu")
        status_data = status_resp.json()
        
        if status_data["total_gpus"] == 0:
            pytest.skip("No GPUs registered, skipping GPU control test")
        
        # Try to enable GPU 0
        # 尝试启用 GPU 0
        resp = requests.post(
            f"{base_url}/services/gpu/control",
            json={"gpu_index": 0, "action": "enable"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_gpu_control_disable(self, base_url: str) -> None:
        """
        Test GPU disable control action.
        测试 GPU 禁用控制操作。
        """
        # First get current status
        # 首先获取当前状态
        status_resp = requests.get(f"{base_url}/services/gpu")
        status_data = status_resp.json()
        
        if status_data["total_gpus"] == 0:
            pytest.skip("No GPUs registered, skipping GPU control test")
        
        # Try to disable GPU 0
        # 尝试禁用 GPU 0
        resp = requests.post(
            f"{base_url}/services/gpu/control",
            json={"gpu_index": 0, "action": "disable"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Re-enable for other tests
        # 为其他测试重新启用
        requests.post(
            f"{base_url}/services/gpu/control",
            json={"gpu_index": 0, "action": "enable"},
        )

    def test_gpu_control_invalid_action(self, base_url: str) -> None:
        """
        Test GPU control with invalid action.
        测试使用无效操作的 GPU 控制。
        """
        resp = requests.post(
            f"{base_url}/services/gpu/control",
            json={"gpu_index": 0, "action": "invalid_action"},
        )
        # Should return validation error
        # 应返回验证错误
        assert resp.status_code == 422, f"Expected 422 for invalid action, got {resp.status_code}"

    def test_gpu_control_missing_fields(self, base_url: str) -> None:
        """
        Test GPU control with missing fields.
        测试缺少字段的 GPU 控制。
        """
        resp = requests.post(
            f"{base_url}/services/gpu/control",
            json={},
        )
        assert resp.status_code == 422, f"Expected 422 for missing fields, got {resp.status_code}"

