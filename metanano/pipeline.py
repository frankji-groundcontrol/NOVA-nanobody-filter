"""
References / 参考:
    - docs/en/README.md: Section 4 - Workflow for Validation
    - docs/cn/README.md: 第4节 - 验证工作流程
    - metanano/config.py: Configuration models

File / 文件:
    - metanano/pipeline.py

Overview / 概述:
    Validation pipeline orchestrator for the MetaNano system.
    MetaNano 系统的验证流水线编排器。

    Chains filters in sequence (Diversity → Nativeness → Developability)
    with early termination on failure and detailed result reporting.
    按顺序串联过滤器（多样性 → 天然性 → 可开发性），
    失败时提前终止并提供详细的结果报告。

    Supports both sync and async execution.
    支持同步和异步执行。

Consumers / 调用方:
    - metanano/__init__.py
    - metanano/routes/validation_routes.py
    - app.py
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from metanano.config import Config
from metanano.models.filter_result import FilterResult, ValidationResult
from metanano.services.async_manager import AsyncServiceManager, get_service_manager
from metanano.services.diversity_service import DiversityService
from metanano.services.nativeness_service import NativenessService
from metanano.services.developability_service import DevelopabilityService
from metanano.validators.developability_validator import DevelopabilityValidator
from metanano.validators.diversity_validator import DiversityValidator
from metanano.validators.nativeness_validator import NativenessValidator


class ValidationPipeline:
    """
    Orchestrates the validation pipeline for nanobody sequences.
    编排纳米抗体序列的验证流水线。

    The pipeline runs three filters in sequence:
    流水线按顺序运行三个过滤器：
        1. Diversity Filter - Ensures sequence uniqueness / 多样性过滤器 - 确保序列唯一性
        2. Nativeness Filter - Validates nanobody structure / 天然性过滤器 - 验证纳米抗体结构
        3. Developability Filter - Checks therapeutic viability / 可开发性过滤器 - 检查治疗可行性

    Early termination occurs if any filter fails.
    如果任何过滤器失败，则提前终止。

    Supports both sync (validate) and async (validate_async) execution.
    支持同步（validate）和异步（validate_async）执行。

    Example / 示例:
        >>> config = Config()
        >>> pipeline = ValidationPipeline(config)
        >>> # Sync
        >>> result = pipeline.validate("EVQLVESGGGLVQPGG...")
        >>> # Async
        >>> result = await pipeline.validate_async("EVQLVESGGGLVQPGG...")
        >>> print(result.validation_status)
        "Passed"

    Consumers / 调用方:
        - metanano/__init__.py
        - metanano/routes/validation_routes.py
        - metanano/routes/submission_routes.py
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        manager: Optional[AsyncServiceManager] = None,
    ) -> None:
        """
        Initialize the validation pipeline.
        初始化验证流水线。

        Args / 参数:
            config (Optional[Config]): Pipeline configuration. If None, uses defaults.
                流水线配置。如果为 None，使用默认值。
            manager (Optional[AsyncServiceManager]): Service manager for async operations.
                用于异步操作的服务管理器。

        References / 参考:
            - metanano/config.py: Config
        """
        self.config = config or Config()
        self._manager = manager

        # Sync validators (for backward compatibility)
        # 同步验证器（用于向后兼容）
        self._diversity_validator = DiversityValidator(self.config.diversity)
        self._nativeness_validator = NativenessValidator(self.config.nativeness)
        self._developability_validator = DevelopabilityValidator(
            self.config.developability
        )

        # Async services
        # 异步服务
        self._diversity_service: Optional[DiversityService] = None
        self._nativeness_service: Optional[NativenessService] = None
        self._developability_service: Optional[DevelopabilityService] = None

    @property
    def manager(self) -> AsyncServiceManager:
        """Get or create service manager. / 获取或创建服务管理器。"""
        if self._manager is None:
            self._manager = get_service_manager(self.config.async_config)
        return self._manager

    def _get_diversity_service(self) -> DiversityService:
        """Lazy init diversity service. / 延迟初始化多样性服务。"""
        if self._diversity_service is None:
            self._diversity_service = DiversityService(
                self.config.diversity,
                self.manager,
            )
        return self._diversity_service

    def _get_nativeness_service(self) -> NativenessService:
        """Lazy init nativeness service. / 延迟初始化天然性服务。"""
        if self._nativeness_service is None:
            self._nativeness_service = NativenessService(
                self.config.nativeness,
                self.manager,
            )
        return self._nativeness_service

    def _get_developability_service(self) -> DevelopabilityService:
        """Lazy init developability service. / 延迟初始化可开发性服务。"""
        if self._developability_service is None:
            self._developability_service = DevelopabilityService(
                self.config.developability,
                self.manager,
            )
        return self._developability_service

    async def validate_async(
        self,
        sequence: str,
        historical_sequences: Optional[List[str]] = None,
        batch_sequences: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Run the full validation pipeline asynchronously.
        异步运行完整的验证流水线。

        Args / 参数:
            sequence (str): The nanobody amino acid sequence to validate.
                要验证的纳米抗体氨基酸序列。
            historical_sequences (Optional[List[str]]): Previous submissions for
                diversity comparison. 用于多样性比较的历史提交序列。
            batch_sequences (Optional[List[str]]): Other sequences in the same
                submission batch. 同一提交批次中的其他序列。

        Returns / 返回:
            ValidationResult: Complete validation result with status and details.
                包含状态和详情的完整验证结果。

        Raises / 异常:
            ValueError: If sequence is empty or invalid.
                如果序列为空或无效。
        """
        # Validate input
        # 验证输入
        if not sequence or not sequence.strip():
            raise ValueError("Sequence cannot be empty. / 序列不能为空。")

        sequence = sequence.strip().upper()
        result = ValidationResult(validation_status="Passed")

        # Initialize manager
        # 初始化管理器
        await self.manager.initialize()

        # Use validation semaphore
        # 使用验证信号量
        async with self.manager.validation_semaphore:
            # Step 1: Diversity Filter
            # 第1步：多样性过滤器
            diversity_result = await self._get_diversity_service().analyze_async(
                sequence=sequence,
                batch_sequences=batch_sequences,
                historical_sequences=historical_sequences,
            )
            result.details["diversity"] = diversity_result

            if not diversity_result.get("passed", False):
                result.validation_status = "Failed"
                result.failed_filters.append("Diversity")
                return result

            # Step 2: Nativeness Filter
            # 第2步：天然性过滤器
            nativeness_result = await self._get_nativeness_service().analyze_async(sequence)
            result.details["nativeness"] = nativeness_result

            if not nativeness_result.get("passed", False):
                result.validation_status = "Failed"
                result.failed_filters.append("Nativeness")
                return result

            # Step 3: Developability Filter
            # 第3步：可开发性过滤器
            developability_result = await self._get_developability_service().analyze_async(
                sequence
            )
            result.details["developability"] = developability_result

            if not developability_result.get("passed", False):
                result.validation_status = "Failed"
                result.failed_filters.append("Developability")
                return result

        return result

    async def validate_batch_async(
        self,
        sequences: List[str],
        historical_sequences: Optional[List[str]] = None,
    ) -> List[ValidationResult]:
        """
        Validate a batch of sequences asynchronously.
        异步验证一批序列。

        Args / 参数:
            sequences (List[str]): List of sequences to validate.
                要验证的序列列表。
            historical_sequences (Optional[List[str]]): Previous submissions.
                历史提交序列。

        Returns / 返回:
            List[ValidationResult]: Validation results for each sequence.
                每个序列的验证结果。
        """
        await self.manager.initialize()

        async def validate_one(i: int, seq: str) -> ValidationResult:
            batch_others = sequences[:i] + sequences[i + 1 :]
            return await self.validate_async(
                sequence=seq,
                historical_sequences=historical_sequences,
                batch_sequences=batch_others,
            )

        # Process in batches
        # 按批次处理
        batch_size = self.manager.batch_size
        results: List[ValidationResult] = []

        for i in range(0, len(sequences), batch_size):
            batch = list(enumerate(sequences[i : i + batch_size], start=i))
            batch_results = await asyncio.gather(
                *[validate_one(idx, seq) for idx, seq in batch],
                return_exceptions=True,
            )

            for result in batch_results:
                if isinstance(result, Exception):
                    results.append(
                        ValidationResult(
                            validation_status="Failed",
                            failed_filters=["Error"],
                            details={"error": str(result)},
                        )
                    )
                else:
                    results.append(result)

        return results

    def validate(
        self,
        sequence: str,
        historical_sequences: Optional[List[str]] = None,
        batch_sequences: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Run the full validation pipeline on a sequence (sync version).
        对序列运行完整的验证流水线（同步版本）。

        For async execution, use validate_async() instead.
        如需异步执行，请使用 validate_async()。

        Args / 参数:
            sequence (str): The nanobody amino acid sequence to validate.
                要验证的纳米抗体氨基酸序列。
            historical_sequences (Optional[List[str]]): Previous submissions for
                diversity comparison. 用于多样性比较的历史提交序列。
            batch_sequences (Optional[List[str]]): Other sequences in the same
                submission batch. 同一提交批次中的其他序列。

        Returns / 返回:
            ValidationResult: Complete validation result with status and details.
                包含状态和详情的完整验证结果。

        Raises / 异常:
            ValueError: If sequence is empty or invalid.
                如果序列为空或无效。
        """
        # Validate input
        # 验证输入
        if not sequence or not sequence.strip():
            raise ValueError("Sequence cannot be empty. / 序列不能为空。")

        sequence = sequence.strip().upper()
        result = ValidationResult(validation_status="Passed")

        # Step 1: Diversity Filter
        # 第1步：多样性过滤器
        diversity_result = self._diversity_validator.validate(
            sequence=sequence,
            historical_sequences=historical_sequences or [],
            batch_sequences=batch_sequences or [],
        )
        result.details["diversity"] = diversity_result.details

        if not diversity_result.passed:
            result.validation_status = "Failed"
            result.failed_filters.append("Diversity")
            result.details["diversity"]["passed"] = False
            result.details["diversity"]["reason"] = diversity_result.reason
            return result

        result.details["diversity"]["passed"] = True

        # Step 2: Nativeness Filter
        # 第2步：天然性过滤器
        nativeness_result = self._nativeness_validator.validate(sequence)
        result.details["nativeness"] = nativeness_result.details

        if not nativeness_result.passed:
            result.validation_status = "Failed"
            result.failed_filters.append("Nativeness")
            result.details["nativeness"]["passed"] = False
            result.details["nativeness"]["reason"] = nativeness_result.reason
            return result

        result.details["nativeness"]["passed"] = True

        # Step 3: Developability Filter
        # 第3步：可开发性过滤器
        developability_result = self._developability_validator.validate(sequence)
        result.details["developability"] = developability_result.details

        if not developability_result.passed:
            result.validation_status = "Failed"
            result.failed_filters.append("Developability")
            result.details["developability"]["passed"] = False
            result.details["developability"]["reason"] = developability_result.reason
            return result

        result.details["developability"]["passed"] = True

        return result

    def validate_batch(
        self,
        sequences: List[str],
        historical_sequences: Optional[List[str]] = None,
    ) -> List[ValidationResult]:
        """
        Validate a batch of sequences (sync version).
        验证一批序列（同步版本）。

        For async execution, use validate_batch_async() instead.
        如需异步执行，请使用 validate_batch_async()。

        Args / 参数:
            sequences (List[str]): List of sequences to validate.
                要验证的序列列表。
            historical_sequences (Optional[List[str]]): Previous submissions.
                历史提交序列。

        Returns / 返回:
            List[ValidationResult]: Validation results for each sequence.
                每个序列的验证结果。
        """
        results = []
        for i, sequence in enumerate(sequences):
            batch_others = sequences[:i] + sequences[i + 1 :]
            result = self.validate(
                sequence=sequence,
                historical_sequences=historical_sequences,
                batch_sequences=batch_others,
            )
            results.append(result)
        return results


