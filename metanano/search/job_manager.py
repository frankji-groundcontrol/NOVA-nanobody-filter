"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Async Search Architecture
    - docs/cn/README.md: 第1.1节 - 异步搜索架构
    - metanano/search/index_manager.py: Thread-safe pattern with threading.Lock

File / 文件:
    - metanano/search/job_manager.py

Overview / 概述:
    Thread-safe in-memory job state tracker for async search operations.
    线程安全的内存任务状态跟踪器，用于异步搜索操作。

    Manages search job lifecycle (pending -> running -> completed/failed)
    with automatic TTL-based cleanup of expired jobs.
    管理搜索任务生命周期（pending -> running -> completed/failed），
    带有基于 TTL 的自动过期任务清理。

Consumers / 调用方:
    - metanano/search/__init__.py
    - metanano/routes/search_routes.py (future)
"""

import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    """
    Enumeration of possible job states.
    任务状态枚举。

    Values are JSON-serializable strings for API responses.
    值为 JSON 可序列化的字符串，用于 API 响应。

    Consumers / 调用方:
        - metanano/search/job_manager.py: JobManager
        - metanano/routes/search_routes.py (future)
    """

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


@dataclass
class JobState:
    """
    State snapshot for a single search job.
    单个搜索任务的状态快照。

    Attributes / 属性:
        job_id (str): Unique job identifier (UUID4).
            唯一任务标识符（UUID4）。
        status (JobStatus): Current job status.
            当前任务状态。
        created_at (float): Job creation timestamp (time.time()).
            任务创建时间戳（time.time()）。
        completed_at (Optional[float]): Completion timestamp, set when completed/failed.
            完成时间戳，当 completed/failed 时设置。
        result (Optional[Any]): Job result data (set on completion).
            任务结果数据（完成时设置）。
        error (Optional[str]): Error message (set on failure).
            错误消息（失败时设置）。

    Consumers / 调用方:
        - metanano/search/job_manager.py: JobManager
    """

    job_id: str
    status: JobStatus
    created_at: float
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class JobManager:
    """
    Thread-safe in-memory job state tracker with TTL-based cleanup.
    线程安全的内存任务状态跟踪器，带 TTL 清理。

    Tracks async search job lifecycle: pending -> running -> completed/failed.
    跟踪异步搜索任务生命周期：pending -> running -> completed/failed。

    Args:
        ttl_seconds (float): Time-to-live for completed/failed jobs before cleanup.
            已完成/失败任务在清理前的存活时间。

    Example / 示例:
        >>> mgr = JobManager(ttl_seconds=3600.0)
        >>> job_id = mgr.create_job()
        >>> mgr.update_status(job_id, JobStatus.running)
        >>> mgr.update_status(job_id, JobStatus.completed, result={"matches": 5})
        >>> mgr.get_job(job_id).status
        <JobStatus.completed: 'completed'>

    Consumers / 调用方:
        - metanano/search/__init__.py
        - metanano/routes/search_routes.py (future)
    """

    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        """
        Initialize JobManager with TTL configuration.
        使用 TTL 配置初始化 JobManager。

        Args:
            ttl_seconds (float): Time-to-live in seconds for completed/failed jobs.
                已完成/失败任务的存活时间（秒）。
        """
        self._ttl_seconds = ttl_seconds
        self._jobs: Dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create_job(self) -> str:
        """
        Create a new job with pending status.
        创建一个新的 pending 状态任务。

        Returns:
            str: UUID4 job identifier.
                UUID4 任务标识符。
        """
        job_id = str(uuid.uuid4())
        job_state = JobState(
            job_id=job_id,
            status=JobStatus.pending,
            created_at=time.time(),
        )
        with self._lock:
            self._jobs[job_id] = job_state
        return job_id

    def get_job(self, job_id: str) -> Optional[JobState]:
        """
        Retrieve job state by ID. Returns None for nonexistent jobs.
        通过 ID 检索任务状态。不存在的任务返回 None。

        Args:
            job_id (str): Job identifier to look up.
                要查找的任务标识符。

        Returns:
            Optional[JobState]: Job state or None if not found.
                任务状态，如果未找到则返回 None。
        """
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update job status, optionally setting result or error.
        更新任务状态，可选设置结果或错误。

        Sets completed_at when status transitions to completed or failed.
        当状态转换为 completed 或 failed 时设置 completed_at。

        Args:
            job_id (str): Job identifier to update.
                要更新的任务标识符。
            status (JobStatus): New status value.
                新的状态值。
            result (Optional[Any]): Result data (typically set on completion).
                结果数据（通常在完成时设置）。
            error (Optional[str]): Error message (typically set on failure).
                错误消息（通常在失败时设置）。

        Notes:
            Nonexistent job IDs are ignored to keep update calls idempotent.
            对不存在的 job_id 会静默忽略，以保持更新操作幂等。
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            if status in (JobStatus.completed, JobStatus.failed):
                job.completed_at = time.time()

    def cleanup_expired(self) -> None:
        """
        Remove completed/failed jobs older than TTL. Never removes pending/running jobs.
        移除超过 TTL 的已完成/失败任务。永远不移除 pending/running 任务。
        """
        now = time.time()
        with self._lock:
            expired_ids = [
                job_id
                for job_id, job in self._jobs.items()
                if job.status in (JobStatus.completed, JobStatus.failed)
                and job.completed_at is not None
                and (now - job.completed_at) > self._ttl_seconds
            ]
            for job_id in expired_ids:
                del self._jobs[job_id]

    def list_jobs(self) -> List[JobState]:
        """
        List all tracked jobs for monitoring.
        列出所有跟踪的任务以供监控。

        Returns:
            List[JobState]: All current job states.
                所有当前任务状态。
        """
        with self._lock:
            return list(self._jobs.values())
