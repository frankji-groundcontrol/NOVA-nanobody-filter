"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Diversity Filter
    - metanano/filters/diversity.py: DiversityFilter
    - metanano/config.py: DiversityConfig

File / 文件:
    - metanano/validators/diversity_validator.py

Overview / 概述:
    Diversity validator that orchestrates diversity filter execution.
    编排多样性过滤器执行的多样性验证器。

Consumers / 调用方:
    - metanano/validators/__init__.py
    - metanano/pipeline.py
"""

from typing import Any, Dict, List

from metanano.config import DiversityConfig
from metanano.filters.diversity import DiversityFilter
from metanano.models.filter_result import FilterResult


class DiversityValidator:
    """
    Validator for diversity requirements.
    多样性要求的验证器。

    Orchestrates the DiversityFilter to check batch diversity,
    CDR mutations, and historical similarity.
    编排 DiversityFilter 以检查批次多样性、CDR 突变和历史相似度。

    Consumers / 调用方:
        - metanano/pipeline.py: ValidationPipeline
    """

    def __init__(self, config: DiversityConfig) -> None:
        """
        Initialize the diversity validator.
        初始化多样性验证器。

        Args / 参数:
            config (DiversityConfig): Diversity configuration.
                多样性配置。
        """
        self.config = config
        self._filter = DiversityFilter(config)

    def validate(
        self,
        sequence: str,
        historical_sequences: List[str],
        batch_sequences: List[str],
    ) -> FilterResult:
        """
        Validate sequence diversity.
        验证序列多样性。

        Args / 参数:
            sequence (str): Sequence to validate.
                要验证的序列。
            historical_sequences (List[str]): Historical submissions.
                历史提交序列。
            batch_sequences (List[str]): Other sequences in batch.
                批次中的其他序列。

        Returns / 返回:
            FilterResult: Validation result.
                验证结果。

        Consumers / 调用方:
            - metanano/pipeline.py: ValidationPipeline.validate
        """
        details: Dict[str, Any] = {}

        # Check batch diversity
        # 检查批次多样性
        batch_passed, max_identity = self._filter.check_batch_diversity(
            sequence, batch_sequences
        )
        if max_identity is not None:
            details["global_cluster_identity"] = max_identity

        if not batch_passed:
            return FilterResult(
                passed=False,
                details=details,
                reason=f"Sequence too similar to batch (identity: {max_identity:.2f} "
                f">= {self.config.mmseqs2.global_cluster_identity}). / "
                f"序列与批次中其他序列过于相似（相似度：{max_identity:.2f} "
                f">= {self.config.mmseqs2.global_cluster_identity}）。",
            )

        # Check CDR mutations
        # 检查 CDR 突变
        mutation_passed, combined, cdr3 = self._filter.check_cdr_mutations(sequence)
        details["cdrs_combined_mutations"] = combined
        details["cdr3_mutations"] = cdr3

        if not mutation_passed:
            reasons = []
            if combined < self.config.mutations.cdrs_combined_min:
                reasons.append(
                    f"cdrs_combined ({combined}) < {self.config.mutations.cdrs_combined_min}"
                )
            if cdr3 < self.config.mutations.cdr3_min:
                reasons.append(
                    f"cdr3 ({cdr3}) < {self.config.mutations.cdr3_min}"
                )
            return FilterResult(
                passed=False,
                details=details,
                reason=f"Insufficient CDR mutations: {'; '.join(reasons)}. / "
                f"CDR 突变不足：{'; '.join(reasons)}。",
            )

        # Check historical similarity
        # 检查历史相似度
        hist_passed, max_similarity = self._filter.check_historical_similarity(
            sequence, historical_sequences
        )
        if max_similarity is not None:
            details["jaccard_similarity"] = max_similarity

        if not hist_passed:
            return FilterResult(
                passed=False,
                details=details,
                reason=f"Sequence too similar to historical submissions "
                f"(similarity: {max_similarity:.2f} >= "
                f"{self.config.comparison.plan_a.jaccard_threshold}). / "
                f"序列与历史提交过于相似（相似度：{max_similarity:.2f} >= "
                f"{self.config.comparison.plan_a.jaccard_threshold}）。",
            )

        return FilterResult(passed=True, details=details)


