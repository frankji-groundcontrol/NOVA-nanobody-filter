"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Diversity Filter
    - metanano/filters/diversity.py: DiversityFilter
    - metanano/config.py: DiversityConfig

File / 文件:
    - metanano/services/diversity_service.py

Overview / 概述:
    Async diversity service with semaphore-based concurrency control.
    基于信号量的异步多样性服务并发控制。

Consumers / 调用方:
    - metanano/services/__init__.py
    - metanano/routes/diversity_routes.py
    - metanano/pipeline.py
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from metanano.config import DiversityConfig
from metanano.filters.diversity import DiversityFilter, DiversityResult
from metanano.services.async_manager import AsyncServiceManager, get_service_manager


class DiversityService:
    """
    Async service for diversity filter operations.
    多样性过滤器操作的异步服务。

    Wraps DiversityFilter with async execution and semaphore control.
    用异步执行和信号量控制封装 DiversityFilter。

    Example / 示例:
        >>> service = DiversityService(config)
        >>> result = await service.check_batch_diversity_async(seq, batch)

    Consumers / 调用方:
        - metanano/routes/diversity_routes.py
        - metanano/pipeline.py
    """

    def __init__(
        self,
        config: DiversityConfig,
        manager: Optional[AsyncServiceManager] = None,
    ) -> None:
        """
        Initialize the diversity service.
        初始化多样性服务。

        Args / 参数:
            config (DiversityConfig): Diversity filter configuration.
                多样性过滤器配置。
            manager (Optional[AsyncServiceManager]): Service manager for semaphores.
                用于信号量的服务管理器。
        """
        self.config = config
        self._filter = DiversityFilter(config)
        self._manager = manager

    @property
    def manager(self) -> AsyncServiceManager:
        """Get or create service manager. / 获取或创建服务管理器。"""
        if self._manager is None:
            self._manager = get_service_manager()
        return self._manager

    async def check_batch_diversity_async(
        self,
        sequence: str,
        batch_sequences: List[str],
    ) -> Tuple[bool, Optional[float]]:
        """
        Async check if sequence is diverse within batch.
        异步检查序列在批次内是否具有多样性。

        Args / 参数:
            sequence (str): The sequence to check. / 要检查的序列。
            batch_sequences (List[str]): Other sequences in batch. / 批次中的其他序列。

        Returns / 返回:
            Tuple[bool, Optional[float]]: (passed, max_identity_found)
        """
        await self.manager.initialize()
        async with self.manager.mmseqs2_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._filter.check_batch_diversity,
                    sequence,
                    batch_sequences,
                ),
                timeout=self.manager.task_timeout,
            )

    async def check_cdr_mutations_async(
        self,
        sequence: str,
        reference_sequence: Optional[str] = None,
    ) -> Tuple[bool, int, int]:
        """
        Async check CDR mutation requirements.
        异步检查 CDR 突变要求。

        Args / 参数:
            sequence (str): The sequence to check. / 要检查的序列。
            reference_sequence (Optional[str]): Reference sequence. / 参考序列。

        Returns / 返回:
            Tuple[bool, int, int]: (passed, cdrs_combined, cdr3_mutations)
        """
        await self.manager.initialize()
        return await asyncio.to_thread(
            self._filter.check_cdr_mutations,
            sequence,
            reference_sequence,
        )

    async def check_historical_similarity_async(
        self,
        sequence: str,
        historical_sequences: List[str],
    ) -> Tuple[bool, Optional[float]]:
        """
        Async check similarity against historical submissions.
        异步检查与历史提交的相似度。

        Args / 参数:
            sequence (str): The sequence to check. / 要检查的序列。
            historical_sequences (List[str]): Historical submissions. / 历史提交序列。

        Returns / 返回:
            Tuple[bool, Optional[float]]: (passed, max_similarity)
        """
        await self.manager.initialize()
        return await asyncio.to_thread(
            self._filter.check_historical_similarity,
            sequence,
            historical_sequences,
        )

    async def analyze_async(
        self,
        sequence: str,
        batch_sequences: Optional[List[str]] = None,
        historical_sequences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Perform complete async diversity analysis.
        执行完整的异步多样性分析。

        Args / 参数:
            sequence (str): The sequence to analyze. / 要分析的序列。
            batch_sequences (Optional[List[str]]): Other sequences in batch. / 批次中的其他序列。
            historical_sequences (Optional[List[str]]): Historical submissions. / 历史提交序列。

        Returns / 返回:
            Dict[str, Any]: Complete analysis result. / 完整的分析结果。
        """
        await self.manager.initialize()
        result: Dict[str, Any] = {"passed": True}

        # Check batch diversity
        # 检查批次多样性
        if batch_sequences:
            batch_passed, max_identity = await self.check_batch_diversity_async(
                sequence, batch_sequences
            )
            if max_identity is not None:
                result["global_cluster_identity"] = max_identity
            if not batch_passed:
                result["passed"] = False
                result["reason"] = (
                    f"Sequence too similar to batch (identity: {max_identity:.2f}). / "
                    f"序列与批次中其他序列过于相似（相似度：{max_identity:.2f}）。"
                )
                return result

        # Check CDR mutations
        # 检查 CDR 突变
        mutation_passed, combined, cdr3 = await self.check_cdr_mutations_async(sequence)
        result["cdrs_combined_mutations"] = combined
        result["cdr3_mutations"] = cdr3
        if not mutation_passed:
            result["passed"] = False
            result["reason"] = (
                f"Insufficient CDR mutations (combined: {combined}, cdr3: {cdr3}). / "
                f"CDR 突变不足（合计：{combined}，cdr3：{cdr3}）。"
            )
            return result

        # Check historical similarity
        # 检查历史相似度
        if historical_sequences:
            hist_passed, max_similarity = await self.check_historical_similarity_async(
                sequence, historical_sequences
            )
            if max_similarity is not None:
                result["jaccard_similarity"] = max_similarity
            if not hist_passed:
                result["passed"] = False
                result["reason"] = (
                    f"Sequence too similar to historical (similarity: {max_similarity:.2f}). / "
                    f"序列与历史提交过于相似（相似度：{max_similarity:.2f}）。"
                )
                return result

        return result

