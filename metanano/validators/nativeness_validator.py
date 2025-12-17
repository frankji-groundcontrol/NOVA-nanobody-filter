"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - metanano/filters/nativeness.py: NativenessFilter
    - metanano/config.py: NativenessConfig

File / 文件:
    - metanano/validators/nativeness_validator.py

Overview / 概述:
    Nativeness validator that orchestrates nativeness filter execution.
    编排天然性过滤器执行的天然性验证器。

Consumers / 调用方:
    - metanano/validators/__init__.py
    - metanano/pipeline.py
"""

from metanano.config import NativenessConfig
from metanano.filters.nativeness import NativenessFilter
from metanano.models.filter_result import FilterResult


class NativenessValidator:
    """
    Validator for nativeness requirements.
    天然性要求的验证器。

    Orchestrates the NativenessFilter to check IMGT numbering,
    nativeness score, and humanness score.
    编排 NativenessFilter 以检查 IMGT 编号、天然性分数和人源性分数。

    Consumers / 调用方:
        - metanano/pipeline.py: ValidationPipeline
    """

    def __init__(self, config: NativenessConfig) -> None:
        """
        Initialize the nativeness validator.
        初始化天然性验证器。

        Args / 参数:
            config (NativenessConfig): Nativeness configuration.
                天然性配置。
        """
        self.config = config
        self._filter = NativenessFilter(config)

    def validate(self, sequence: str) -> FilterResult:
        """
        Validate sequence nativeness.
        验证序列天然性。

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


