"""
References / 参考:
    - docs/en/README.md: Section 3 - API Routes
    - docs/cn/README.md: 第3节 - API 路由

File / 文件:
    - metanano/tests/search/test_search_routes.py

Overview / 概述:
    Integration-style tests for search API routes using FastAPI TestClient.
    使用 FastAPI TestClient 的搜索 API 路由集成测试。

Consumers / 调用方:
    - pytest
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from metanano.routes.search_routes import _search_service, router


@pytest.fixture
def client() -> TestClient:
    """
    Build isolated test client with search router only.
    构建仅包含搜索路由的隔离测试客户端。
    """
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_search_state() -> None:
    """
    Reset shared in-memory state before each test.
    每个测试前重置共享内存状态。
    """
    _search_service._index_manager.clear()


def test_post_search_returns_202_with_job_id(client: TestClient, query_sequence: str) -> None:
    """POST /search returns 202 and job_id. / POST /search 返回 202 和 job_id。"""
    response = client.post("/search", json={"sequences": [query_sequence]})

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str)
    assert body["job_id"]


def test_post_search_invalid_sequence_returns_422(client: TestClient) -> None:
    """Invalid sequence is rejected with 422. / 无效序列返回 422。"""
    response = client.post("/search", json={"sequences": ["INVALID123!!!"]})

    assert response.status_code == 422


def test_get_search_status_returns_job(client: TestClient, query_sequence: str) -> None:
    """GET /search/{job_id} returns job status. / GET /search/{job_id} 返回任务状态。"""
    submit = client.post("/search", json={"sequences": [query_sequence]})
    job_id = submit.json()["job_id"]

    response = client.get(f"/search/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] in {"pending", "running", "completed", "failed"}


def test_get_search_nonexistent_returns_404(client: TestClient) -> None:
    """Unknown job returns 404. / 未知任务返回 404。"""
    response = client.get("/search/nonexistent")

    assert response.status_code == 404


def test_post_search_batch(client: TestClient, query_sequence: str, similar_sequence: str) -> None:
    """POST /search accepts multiple sequences. / POST /search 支持多序列查询。"""
    response = client.post(
        "/search",
        json={"sequences": [query_sequence, similar_sequence]},
    )

    assert response.status_code == 202
    assert "job_id" in response.json()


def test_post_search_with_options(client: TestClient, query_sequence: str) -> None:
    """Search options are accepted. / 支持搜索选项参数。"""
    response = client.post(
        "/search",
        json={
            "sequences": [query_sequence],
            "include_alignment": True,
            "coarse_min_shared": 1,
            "coarse_jaccard": 0.1,
        },
    )

    assert response.status_code == 202
    assert "job_id" in response.json()


def test_post_index_sequence(client: TestClient, query_sequence: str) -> None:
    """POST /search/index indexes one sequence. / POST /search/index 可索引单条序列。"""
    response = client.post(
        "/search/index",
        json={"id": "db_001", "sequence": query_sequence},
    )

    assert response.status_code == 201


def test_get_index_stats(client: TestClient, query_sequence: str) -> None:
    """GET /search/index/stats returns total indexed count. / 返回索引总数量。"""
    client.post(
        "/search/index",
        json={"id": "db_001", "sequence": query_sequence},
    )

    response = client.get("/search/index/stats")

    assert response.status_code == 200
    body = response.json()
    assert "total_sequences" in body
    assert body["total_sequences"] >= 1
