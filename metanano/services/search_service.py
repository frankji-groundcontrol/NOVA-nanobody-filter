"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Sequence Search
    - docs/cn/README.md: 第1.1节 - 序列搜索
    - metanano/services/nativeness_service.py: Async service pattern
    - metanano/config.py: SearchConfig

File / 文件:
    - metanano/services/search_service.py

Overview / 概述:
    Async search service orchestrating SearchEngine, IndexManager,
    AlignmentEngine, and JobManager with asyncio-based job submission,
    polling, and semaphore-based concurrency control.
    异步搜索服务，编排 SearchEngine、IndexManager、AlignmentEngine
    和 JobManager，基于 asyncio 的任务提交、轮询和信号量并发控制。

Consumers / 调用方:
    - metanano/routes/search_routes.py (future)
    - metanano/pipeline.py (future)
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Set

from metanano.config import SearchConfig
from metanano.search.index_manager import IndexManager
from metanano.search.job_manager import JobManager, JobState, JobStatus
from metanano.search.search_engine import SearchEngine, SearchResult
from metanano.utils.alignment import AlignmentEngine


class SearchService:
    """
    Async orchestration layer for sequence-search operations.
    序列搜索操作的异步编排层。

    Combines SearchEngine, IndexManager, AlignmentEngine, and JobManager
    into a unified service with asyncio-based job lifecycle management
    and semaphore-based concurrency control.
    将 SearchEngine、IndexManager、AlignmentEngine 和 JobManager 组合
    为统一服务，提供基于 asyncio 的任务生命周期管理和信号量并发控制。

    Args:
        config (SearchConfig): Search configuration.
            搜索配置。

    Example / 示例:
        >>> import asyncio
        >>> from metanano.config import SearchConfig
        >>> svc = SearchService(SearchConfig())
        >>> job_id = asyncio.run(svc.submit_search(["EVQLVQS..."]))

    Consumers / 调用方:
        - metanano/routes/search_routes.py (future)
        - metanano/pipeline.py (future)
    """

    def __init__(self, config: SearchConfig) -> None:
        """
        Initialize SearchService with all sub-components.
        使用所有子组件初始化 SearchService。

        Args:
            config (SearchConfig): Search configuration containing coarse filter,
                fine alignment, and concurrency settings.
                搜索配置，包含粗过滤、精细对齐和并发设置。
        """
        self._config = config
        self._index_manager = IndexManager(config)
        self._alignment_engine = AlignmentEngine(config.fine_alignment)
        self._search_engine = SearchEngine(config, self._index_manager, self._alignment_engine)

        ttl_seconds = config.job_ttl_seconds
        self._job_manager = JobManager(ttl_seconds=ttl_seconds)

        max_concurrent = config.max_concurrent_search
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def submit_search(
        self,
        queries: List[str],
        include_alignment: bool = False,
        coarse_min_shared: Optional[int] = None,
        coarse_jaccard: Optional[float] = None,
    ) -> str:
        """
        Submit an async search job and return immediately with a job_id.
        提交异步搜索任务并立即返回 job_id。

        Creates a job, spawns a background task to execute the search,
        and returns the job_id for status polling.
        创建任务，生成后台任务执行搜索，并返回 job_id 供状态轮询。

        Args:
            queries (List[str]): Query amino-acid sequences to search.
                要搜索的查询氨基酸序列列表。
            include_alignment (bool): Include aligned strings in results.
                是否在结果中包含对齐字符串。
            coarse_min_shared (Optional[int]): Override coarse min shared k-mers.
                覆盖粗过滤最小共享 k-mer 数。
            coarse_jaccard (Optional[float]): Override coarse Jaccard threshold.
                覆盖粗过滤 Jaccard 阈值。

        Returns:
            str: UUID4 job identifier for status polling.
                用于状态轮询的 UUID4 任务标识符。
        
        Notes:
            The search runs in a background task created by `asyncio.create_task`.
            搜索任务通过 `asyncio.create_task` 在后台执行。
        """
        job_id = self._job_manager.create_job()
        asyncio.create_task(
            self._run_search(
                job_id,
                queries,
                include_alignment,
                coarse_min_shared,
                coarse_jaccard,
            )
        )
        return job_id

    async def get_job_status(self, job_id: str) -> Optional[JobState]:
        """
        Retrieve current job state by ID.
        通过 ID 检索当前任务状态。

        Args:
            job_id (str): Job identifier to look up.
                要查找的任务标识符。

        Returns:
            Optional[JobState]: Job state or None if not found.
                任务状态，如果未找到则返回 None。
        """
        return self._job_manager.get_job(job_id)

    def index_sequence(
        self,
        seq_id: str,
        sequence: str,
        cdrs: Optional[Dict[str, str]],
        kmers: Optional[Set[str]],
    ) -> None:
        """
        Add a sequence to the search index.
        将序列添加到搜索索引。

        Args:
            seq_id (str): Unique sequence identifier.
                唯一序列标识符。
            sequence (str): Full amino acid sequence.
                完整氨基酸序列。
            cdrs (Optional[Dict[str, str]]): CDR regions or None.
                CDR 区域或 None。
            kmers (Optional[Set[str]]): Pre-generated k-mer set.
                预生成的 k-mer 集合。

        Notes:
            If `kmers` is None, an empty set is used.
            当 `kmers` 为 None 时，会使用空集合。
        """
        self._index_manager.add_sequence(seq_id, sequence, cdrs, kmers or set())

    async def _run_search(
        self,
        job_id: str,
        queries: List[str],
        include_alignment: bool,
        coarse_min_shared: Optional[int],
        coarse_jaccard: Optional[float],
    ) -> None:
        """
        Execute search in background with semaphore-based concurrency control.
        使用信号量并发控制在后台执行搜索。

        Acquires semaphore, runs each query via SearchEngine.search() in a
        thread pool, collects results, and updates job status.
        获取信号量，通过线程池运行每个查询的 SearchEngine.search()，
        收集结果，并更新任务状态。

        Args:
            job_id (str): Job identifier to update.
                要更新的任务标识符。
            queries (List[str]): Query sequences.
                查询序列列表。
            include_alignment (bool): Include aligned strings.
                是否包含对齐字符串。
            coarse_min_shared (Optional[int]): Override min shared k-mers.
                覆盖最小共享 k-mer 数。
            coarse_jaccard (Optional[float]): Override Jaccard threshold.
                覆盖 Jaccard 阈值。

        Raises:
            None. Exceptions are captured and written to JobManager as failed jobs.
            无。异常会被捕获并作为失败任务写入 JobManager。
        """
        async with self._semaphore:
            self._job_manager.update_status(job_id, JobStatus.running)
            try:
                results: List[SearchResult] = []
                for query in queries:
                    result = await asyncio.to_thread(
                        self._search_engine.search,
                        query,
                        include_alignment,
                        None,
                        coarse_min_shared,
                        coarse_jaccard,
                    )
                    results.append(result)
                self._job_manager.update_status(
                    job_id, JobStatus.completed, result=results
                )
            except Exception as exc:
                self._job_manager.update_status(
                    job_id, JobStatus.failed, error=str(exc)
                )
