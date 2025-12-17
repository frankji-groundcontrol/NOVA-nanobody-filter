"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - metanano/filters/nativeness.py: NativenessFilter
    - metanano/config.py: NativenessConfig

File / 文件:
    - metanano/services/nativeness_service.py

Overview / 概述:
    Async nativeness service with semaphore-based concurrency control.
    基于信号量的异步天然性服务并发控制。

    Uses GPU scheduler for AbnatiV scoring when available.
    当可用时使用 GPU 调度器进行 AbnatiV 评分。

Consumers / 调用方:
    - metanano/services/__init__.py
    - metanano/routes/nativeness_routes.py
    - metanano/pipeline.py
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from metanano.config import NativenessConfig
from metanano.filters.nativeness import NativenessFilter, NativenessResult
from metanano.services.async_manager import AsyncServiceManager, get_service_manager


class NativenessService:
    """
    Async service for nativeness filter operations.
    天然性过滤器操作的异步服务。

    Wraps NativenessFilter with async execution and semaphore control.
    Uses GPU scheduler for AbnatiV scoring when available.
    用异步执行和信号量控制封装 NativenessFilter。
    当可用时使用 GPU 调度器进行 AbnatiV 评分。

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
        Async compute nativeness score using AbnatiV v2.
        异步使用 AbnatiV v2 计算天然性分数。

        Uses GPU scheduler if available for GPU-bound computation.
        如果可用，使用 GPU 调度器进行 GPU 密集型计算。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Optional[float]: Nativeness score (0-1) or None.
        """
        await self.manager.initialize()

        # Use GPU scheduler if available
        # 如果可用，使用 GPU 调度器
        gpu_scheduler = self.manager.gpu_scheduler
        if gpu_scheduler and gpu_scheduler.config.enabled:
            async def compute_with_gpu(sequence: str, gpu_index: int) -> Optional[float]:
                """Compute with specific GPU. / 使用特定 GPU 计算。"""
                import os
                os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
                return self._filter.compute_nativeness_score(sequence)

            try:
                return await gpu_scheduler.run_on_gpu(compute_with_gpu, sequence)
            except Exception:
                pass  # Fall back to CPU

        # CPU fallback with semaphore
        # 使用信号量的 CPU 回退
        async with self.manager.abnativ_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._filter.compute_nativeness_score,
                    sequence,
                ),
                timeout=self.manager.task_timeout,
            )

    async def compute_humanness_score_async(self, sequence: str) -> Optional[float]:
        """
        Async compute humanness score using AbnatiV v2.
        异步使用 AbnatiV v2 计算人源性分数。

        Args / 参数:
            sequence (str): The nanobody sequence. / 纳米抗体序列。

        Returns / 返回:
            Optional[float]: Humanness score (0-1) or None.
        """
        await self.manager.initialize()
        async with self.manager.abnativ_semaphore:
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
        Perform complete async nativeness analysis.
        执行完整的异步天然性分析。

        Args / 参数:
            sequence (str): The sequence to analyze. / 要分析的序列。

        Returns / 返回:
            Dict[str, Any]: Complete analysis result. / 完整的分析结果。
        """
        await self.manager.initialize()

        # Step 1: IMGT numbering
        # 第1步：IMGT 编号
        numbered = await self.number_sequence_async(sequence)
        if not numbered:
            return {
                "passed": False,
                "imgt_numbered": False,
                "reason": "Failed to number sequence under IMGT scheme. / "
                "无法使用 IMGT 方案对序列编号。",
            }

        result: Dict[str, Any] = {
            "passed": True,
            "imgt_numbered": True,
            "cdr1": numbered.get("cdr1"),
            "cdr2": numbered.get("cdr2"),
            "cdr3": numbered.get("cdr3"),
        }

        # Step 2: Nativeness score
        # 第2步：天然性分数
        nativeness = await self.compute_nativeness_score_async(sequence)
        if nativeness is None:
            result["passed"] = False
            result["reason"] = "Failed to compute nativeness score. / 无法计算天然性分数。"
            return result

        result["nativeness_score"] = nativeness
        threshold = self.config.abnativ_v2.nativeness_threshold
        if nativeness < threshold:
            result["passed"] = False
            result["reason"] = (
                f"nativeness_score ({nativeness:.2f}) below threshold ({threshold}). / "
                f"天然性分数 ({nativeness:.2f}) 低于阈值 ({threshold})。"
            )
            return result

        # Step 3: Humanness score
        # 第3步：人源性分数
        humanness = await self.compute_humanness_score_async(sequence)
        if humanness is None:
            result["passed"] = False
            result["reason"] = "Failed to compute humanness score. / 无法计算人源性分数。"
            return result

        result["humanness_score"] = humanness
        threshold = self.config.abnativ_v2.humanness_threshold
        if humanness < threshold:
            result["passed"] = False
            result["reason"] = (
                f"humanness_score ({humanness:.2f}) below threshold ({threshold}). / "
                f"人源性分数 ({humanness:.2f}) 低于阈值 ({threshold})。"
            )
            return result

        # Step 4: Optional promb cross-validation
        # 第4步：可选的 promb 交叉验证
        promb_score = await self.compute_promb_score_async(sequence)
        if promb_score is not None:
            result["promb_score"] = promb_score

        return result

