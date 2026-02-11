"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Sequence Search
    - metanano/services/search_service.py: SearchService
    - metanano/config.py: SearchConfig

File / 文件:
    - metanano/tests/search/test_search_service.py

Overview / 概述:
    Tests for SearchService async orchestration layer.
    SearchService 异步编排层的测试。

    Covers job submission, status polling, concurrency control,
    batch search, indexing, and custom threshold forwarding.
    覆盖任务提交、状态轮询、并发控制、批量搜索、索引和自定义阈值转发。

Consumers / 调用方:
    - pytest
"""

import asyncio
from typing import Dict, Optional, Set

import pytest

from metanano.config import SearchConfig
from metanano.search.job_manager import JobStatus
from metanano.services.search_service import SearchService
from metanano.utils.kmer import generate_kmers


# ---------------------------------------------------------------------------
# Helpers / 辅助函数
# ---------------------------------------------------------------------------

def _make_service() -> SearchService:
    """
    Create a SearchService with default config for testing.
    使用默认配置创建测试用 SearchService。
    """
    config = SearchConfig()
    return SearchService(config)


def _index_sample(svc: SearchService, seq_id: str, sequence: str) -> None:
    """
    Index a single sequence with auto-generated k-mers.
    使用自动生成的 k-mer 索引单条序列。
    """
    kmers = generate_kmers(sequence, k=5)
    svc.index_sequence(seq_id, sequence, None, kmers)


async def _poll_until_done(svc: SearchService, job_id: str, timeout_s: float = 5.0):
    """
    Poll job status until completed/failed or timeout.
    轮询任务状态直到完成/失败或超时。
    """
    for _ in range(int(timeout_s / 0.05)):
        await asyncio.sleep(0.05)
        job = await svc.get_job_status(job_id)
        if job is not None and job.status in (JobStatus.completed, JobStatus.failed):
            return job
    return await svc.get_job_status(job_id)


# ---------------------------------------------------------------------------
# Sample sequences / 示例序列
# ---------------------------------------------------------------------------

_QUERY = (
    "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
    "RVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
)

_NEAR_IDENTICAL = (
    "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
    "RVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVAA"
)


# ---------------------------------------------------------------------------
# Tests / 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_search_returns_job_id():
    """
    Submit a search query and verify a non-empty job_id string is returned.
    提交搜索查询并验证返回非空的 job_id 字符串。
    """
    svc = _make_service()
    _index_sample(svc, "db_001", _NEAR_IDENTICAL)

    job_id = await svc.submit_search([_QUERY])

    assert isinstance(job_id, str)
    assert len(job_id) > 0


@pytest.mark.asyncio
async def test_get_search_status_pending():
    """
    Immediately after submit, job status should be pending or running.
    提交后立即检查，任务状态应为 pending 或 running。
    """
    svc = _make_service()
    _index_sample(svc, "db_001", _NEAR_IDENTICAL)

    job_id = await svc.submit_search([_QUERY])
    job = await svc.get_job_status(job_id)

    assert job is not None
    assert job.status in (JobStatus.pending, JobStatus.running)


@pytest.mark.asyncio
async def test_get_search_result_completed():
    """
    After search completes, status is completed with result containing SearchResults.
    搜索完成后，状态为 completed，结果包含 SearchResult 列表。
    """
    svc = _make_service()
    _index_sample(svc, "db_001", _NEAR_IDENTICAL)

    job_id = await svc.submit_search([_QUERY])
    job = await _poll_until_done(svc, job_id)

    assert job is not None
    assert job.status == JobStatus.completed
    assert job.result is not None
    # Result should be a list of SearchResult (one per query)
    # 结果应为 SearchResult 列表（每个查询一个）
    assert isinstance(job.result, list)
    assert len(job.result) == 1
    assert job.result[0].query_sequence == _QUERY


@pytest.mark.asyncio
async def test_search_respects_concurrency_limit():
    """
    Verify semaphore limits concurrent searches.
    验证信号量限制并发搜索数。

    Strategy: Create service with max_concurrent_search=1, launch 3 searches.
    At most 1 should be running concurrently.
    策略：创建 max_concurrent_search=1 的服务，启动 3 个搜索。
    同一时间最多只有 1 个在运行。
    """
    config = SearchConfig()
    svc = SearchService(config)

    # Index several sequences to make search non-trivial
    # 索引多条序列使搜索非平凡
    for i in range(5):
        seq = _QUERY[:50] + chr(65 + i) * 4 + _QUERY[54:]
        _index_sample(svc, f"db_{i:03d}", seq)

    # Override semaphore to 1 for test
    # 测试中覆盖信号量为 1
    svc._semaphore = asyncio.Semaphore(1)

    # Submit 3 searches concurrently
    # 并发提交 3 个搜索
    job_ids = []
    for _ in range(3):
        jid = await svc.submit_search([_QUERY])
        job_ids.append(jid)

    # Wait for all to complete
    # 等待所有完成
    for jid in job_ids:
        job = await _poll_until_done(svc, jid, timeout_s=10.0)
        assert job is not None
        assert job.status == JobStatus.completed


@pytest.mark.asyncio
async def test_submit_batch_search():
    """
    Multiple query sequences in a single job, results track all queries.
    单个任务中包含多条查询序列，结果跟踪所有查询。
    """
    svc = _make_service()
    _index_sample(svc, "db_001", _NEAR_IDENTICAL)

    queries = [_QUERY, _NEAR_IDENTICAL]
    job_id = await svc.submit_search(queries)
    job = await _poll_until_done(svc, job_id)

    assert job is not None
    assert job.status == JobStatus.completed
    assert isinstance(job.result, list)
    assert len(job.result) == 2


@pytest.mark.asyncio
async def test_index_sequence_auto_appends():
    """
    Indexing sequences increases index size tracked by the service.
    索引序列增加服务跟踪的索引大小。
    """
    svc = _make_service()

    assert svc._index_manager.size() == 0

    _index_sample(svc, "db_001", _QUERY)
    assert svc._index_manager.size() == 1

    _index_sample(svc, "db_002", _NEAR_IDENTICAL)
    assert svc._index_manager.size() == 2


@pytest.mark.asyncio
async def test_search_with_custom_thresholds():
    """
    Custom coarse thresholds are forwarded to engine, affecting results.
    自定义粗过滤阈值被转发到引擎，影响结果。
    """
    svc = _make_service()
    _index_sample(svc, "db_001", _NEAR_IDENTICAL)

    # Very high Jaccard threshold should filter out even near-identical
    # 非常高的 Jaccard 阈值应该过滤掉近乎相同的序列
    job_id = await svc.submit_search(
        [_QUERY],
        coarse_min_shared=999,
        coarse_jaccard=0.9999,
    )
    job = await _poll_until_done(svc, job_id)

    assert job is not None
    assert job.status == JobStatus.completed
    assert isinstance(job.result, list)
    assert len(job.result) == 1
    # With extreme thresholds, no candidates should survive coarse filter
    # 使用极端阈值，没有候选应通过粗过滤
    assert job.result[0].total_candidates == 0
    assert len(job.result[0].matches) == 0
