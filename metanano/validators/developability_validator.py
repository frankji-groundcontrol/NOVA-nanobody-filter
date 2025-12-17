"""
References / 参考:
    - docs/en/README.md: Section 1.3 - Developability Filter
    - metanano/filters/developability.py: DevelopabilityFilter
    - metanano/config.py: DevelopabilityConfig

File / 文件:
    - metanano/validators/developability_validator.py

Overview / 概述:
    Developability validator that orchestrates developability filter execution.
    编排可开发性过滤器执行的可开发性验证器。

Consumers / 调用方:
    - metanano/validators/__init__.py
    - metanano/pipeline.py
"""

from metanano.config import DevelopabilityConfig
from metanano.filters.developability import DevelopabilityFilter
from metanano.models.filter_result import FilterResult


class DevelopabilityValidator:
    """
    Validator for developability requirements.
    可开发性要求的验证器。

    Orchestrates the DevelopabilityFilter to check Red Region criteria.
    编排 DevelopabilityFilter 以检查红区标准。

    Consumers / 调用方:
        - metanano/pipeline.py: ValidationPipeline
    """

    def __init__(self, config: DevelopabilityConfig) -> None:
        """
        Initialize the developability validator.
        初始化可开发性验证器。

        Args / 参数:
            config (DevelopabilityConfig): Developability configuration.
                可开发性配置。
        """
        self.config = config
        self._filter = DevelopabilityFilter(config)

    def validate(self, sequence: str) -> FilterResult:
        """
        Validate sequence developability.
        验证序列可开发性。

        Args / 参数:
            sequence (str): Sequence to validate.
                要验证的序列。

        Returns / 返回:
            FilterResult: Validation result.
                验证结果。

        Consumers / 调用方:
            - metanano/pipeline.py: ValidationPipeline.validate
        """
        result = self._filter.analyze(sequence)

        return FilterResult(
            passed=result.passed,
            details=result.to_dict(),
            reason=result.reason,
        )


