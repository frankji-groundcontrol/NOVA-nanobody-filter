"""
File / 文件:
    - metanano/tests/search/test_job_manager.py

Overview / 概述:
    Tests for JobManager — async job tracking with TTL cleanup.
    JobManager 的测试 — 异步任务跟踪与 TTL 清理。

Consumers / 调用方:
    - pytest
"""

import threading
import time
from typing import List

import pytest

from metanano.search.job_manager import JobManager, JobState, JobStatus


class TestJobCreation:
    """
    Job creation and initial state tests.
    任务创建和初始状态测试。
    """

    def test_create_job_returns_job_id(self) -> None:
        """
        create_job returns a valid UUID string as job_id.
        create_job 返回一个有效的 UUID 字符串作为 job_id。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        job_id = mgr.create_job()
        assert isinstance(job_id, str)
        assert len(job_id) == 36  # UUID4 format: 8-4-4-4-12

    def test_job_initial_status_pending(self) -> None:
        """
        Newly created job has status == JobStatus.pending.
        新创建的任务状态为 JobStatus.pending。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        job_id = mgr.create_job()
        job = mgr.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.pending


class TestJobStatusTransitions:
    """
    Job status transition tests.
    任务状态转换测试。
    """

    def test_job_status_transitions(self) -> None:
        """
        Job transitions: pending -> running -> completed with correct status at each step.
        任务转换：pending -> running -> completed，每步状态正确。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        job_id = mgr.create_job()

        # pending -> running
        mgr.update_status(job_id, JobStatus.running)
        job = mgr.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.running
        assert job.completed_at is None

        # running -> completed
        mgr.update_status(job_id, JobStatus.completed, result={"matches": 42})
        job = mgr.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.completed
        assert job.completed_at is not None

    def test_job_stores_result(self) -> None:
        """
        Completing a job with result dict makes result retrievable via get_job.
        使用结果字典完成任务后，可通过 get_job 检索结果。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        job_id = mgr.create_job()
        result_data = {"matches": 5, "top_hit": "seq_42"}

        mgr.update_status(job_id, JobStatus.running)
        mgr.update_status(job_id, JobStatus.completed, result=result_data)

        job = mgr.get_job(job_id)
        assert job is not None
        assert job.result == result_data

    def test_job_failed_status(self) -> None:
        """
        Marking job failed sets status=failed with error message and completed_at.
        标记任务失败时设置 status=failed，附带错误消息和 completed_at。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        job_id = mgr.create_job()

        mgr.update_status(job_id, JobStatus.running)
        mgr.update_status(job_id, JobStatus.failed, error="Timeout exceeded")

        job = mgr.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.failed
        assert job.error == "Timeout exceeded"
        assert job.completed_at is not None


class TestJobLookup:
    """
    Job lookup and listing tests.
    任务查找和列表测试。
    """

    def test_get_nonexistent_job_returns_none(self) -> None:
        """
        get_job with invalid job_id returns None.
        使用无效 job_id 调用 get_job 返回 None。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        result = mgr.get_job("nonexistent-uuid-1234")
        assert result is None


class TestTTLCleanup:
    """
    TTL-based cleanup tests.
    基于 TTL 的清理测试。
    """

    def test_ttl_cleanup_removes_old_jobs(self) -> None:
        """
        Completed jobs older than TTL are removed by cleanup_expired.
        超过 TTL 的已完成任务被 cleanup_expired 移除。
        """
        mgr = JobManager(ttl_seconds=1.0)
        job_id = mgr.create_job()
        mgr.update_status(job_id, JobStatus.running)
        mgr.update_status(job_id, JobStatus.completed, result={"done": True})

        # Wait for TTL to expire
        # 等待 TTL 过期
        time.sleep(2.0)

        mgr.cleanup_expired()
        assert mgr.get_job(job_id) is None

    def test_active_jobs_not_cleaned(self) -> None:
        """
        Running jobs are NOT removed by cleanup even if old.
        即使超时，运行中的任务也不会被清理。
        """
        mgr = JobManager(ttl_seconds=1.0)
        job_id = mgr.create_job()
        mgr.update_status(job_id, JobStatus.running)

        # Wait for TTL to expire
        # 等待 TTL 过期
        time.sleep(2.0)

        mgr.cleanup_expired()
        job = mgr.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.running


class TestConcurrency:
    """
    Thread safety tests.
    线程安全测试。
    """

    def test_concurrent_job_creation(self) -> None:
        """
        10 concurrent threads creating jobs produce all unique IDs and correct count.
        10 个并发线程创建任务产生所有唯一 ID 和正确数量。
        """
        mgr = JobManager(ttl_seconds=3600.0)
        job_ids: List[str] = []
        errors: List[Exception] = []
        lock = threading.Lock()

        def create() -> None:
            try:
                jid = mgr.create_job()
                with lock:
                    job_ids.append(jid)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(job_ids) == 10
        assert len(set(job_ids)) == 10  # all unique
        assert len(mgr.list_jobs()) == 10
