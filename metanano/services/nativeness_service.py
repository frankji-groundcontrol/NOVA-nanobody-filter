"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - metanano/filters/nativeness.py: NativenessFilter
    - metanano/config.py: NativenessConfig

File / 文件:
    - metanano/services/nativeness_service.py

Overview / 概述:
    Async nativeness service with concurrency control.
    具有并发控制的异步天然性服务。

    Wraps the nativeness filter and runs scoring in background threads.
    封装天然性过滤器，并在后台线程中运行评分。

Consumers / 调用方:
    - metanano/services/__init__.py
    - metanano/routes/nativeness_routes.py
    - metanano/pipeline.py
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
import dataclasses

from metanano.config import NativenessConfig
from metanano.filters.nativeness import NativenessFilter, NativenessResult
from metanano.services.async_manager import AsyncServiceManager, get_service_manager


class NativenessService:
    """
    Async service for nativeness filter operations.
    天然性过滤器操作的异步服务。

    Wraps NativenessFilter with async execution.
    用异步执行封装 NativenessFilter。

    Example / 示例:
        >>> service = NativenessService(config)
        >>> result = await service.analyze_async(sequence)

    Consumers / 调用方:
        - metanano/routes/nativeness_routes.py
        - metanano/pipeline.py
    """

    def __init__(
        self,
        config: NativenessConfig,
        manager: Optional[AsyncServiceManager] = None,
    ) -> None:
        """
        Initialize the nativeness service.
        初始化天然性服务。

        Args / 参数:
            config (NativenessConfig): Nativeness filter configuration.
                天然性过滤器配置。
            manager (Optional[AsyncServiceManager]): Service manager for semaphores.
                用于信号量的服务管理器。
        """
        self.config = config
        self._filter = NativenessFilter(config)
        self._manager = manager

    @property
    def manager(self) -> AsyncServiceManager:
        """Get or create service manager. / 获取或创建服务管理器。"""
        if self._manager is None:
            self._manager = get_service_manager()
        return self._manager

    async def number_sequence_async(self, sequence: str) -> Optional[Dict[str, Any]]:
        """
        Async apply IMGT numbering to sequence.
        异步对序列应用 IMGT 编号。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Optional[Dict[str, Any]]: Numbered sequence data or None.
        """
        await self.manager.initialize()
        return await asyncio.to_thread(
            self._filter.number_sequence,
            sequence,
        )

    async def compute_nativeness_score_async(self, sequence: str) -> Optional[float]:
        """
        Async compute nativeness score using IgBLAST-based heuristic.
        异步使用基于 IgBLAST 的启发式方法计算天然性分数。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Optional[float]: Nativeness score (0-1) or None.
        """
        await self.manager.initialize()

        # Run in a background thread with standard timeout.
        # 在后台线程中运行，并应用通用超时。
        return await asyncio.wait_for(
            asyncio.to_thread(
                self._filter.compute_nativeness_score,
                sequence,
            ),
            timeout=self.manager.task_timeout,
        )

    async def compute_humanness_score_async(self, sequence: str) -> Optional[float]:
        """
        Async compute humanness score using IgBLAST-based heuristic.
        异步使用基于 IgBLAST 的启发式方法计算人源性分数。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Optional[float]: Humanness score (0-1) or None.
        """
        await self.manager.initialize()
        return await asyncio.wait_for(
            asyncio.to_thread(
                self._filter.compute_humanness_score,
                sequence,
            ),
            timeout=self.manager.task_timeout,
        )

    async def compute_promb_score_async(self, sequence: str) -> Optional[float]:
        """
        Async compute OASis humanness score using promb.
        异步使用 promb 计算 OASis 人源性分数。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Optional[float]: OASis score or None if disabled/failed.
        """
        if not self.config.promb.enabled:
            return None

        await self.manager.initialize()
        async with self.manager.promb_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._filter.compute_promb_score,
                    sequence,
                ),
                timeout=self.manager.task_timeout,
            )

    async def analyze_async(self, sequence: str) -> Dict[str, Any]:
        """
        Async analyze nanobody sequence.
        异步分析纳米抗体序列。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Dict[str, Any]: The analysis result. / 分析结果。
        """
        await self.manager.initialize()

        raw = await asyncio.wait_for(
            asyncio.to_thread(self._filter.analyze, sequence),
            timeout=self.manager.task_timeout,
        )

        # raw already has nativeness, humanness, CDRs, reject info
        result = dataclasses.asdict(raw)

        # Optional promb cross-validation
        if self.config.promb.enabled:
            async with self.manager.promb_semaphore:
                promb_score = await asyncio.wait_for(
                    asyncio.to_thread(self._filter.compute_promb_score, sequence),
                    timeout=self.manager.task_timeout,
                )
                if promb_score is not None:
                    result["promb_score"] = promb_score

        return result
