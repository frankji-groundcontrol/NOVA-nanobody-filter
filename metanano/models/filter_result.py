"""
References / 参考:
    - docs/en/README.md: Section 4 - Workflow for Validation
    - docs/cn/README.md: 第4节 - 验证工作流程

File / 文件:
    - metanano/models/filter_result.py

Overview / 概述:
    Filter result models for validation pipeline.
    验证流水线的过滤器结果模型。

    This module is separate from pipeline.py to avoid circular imports
    with validators.
    此模块与 pipeline.py 分开以避免与验证器的循环导入。

Consumers / 调用方:
    - metanano/models/__init__.py
    - metanano/validators/*.py
    - metanano/pipeline.py
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FilterResult:
    """
    Result from a single filter execution.
    单个过滤器执行的结果。

    Attributes / 属性:
        passed: Whether the filter passed / 过滤器是否通过
        details: Detailed metrics and scores / 详细指标和分数
        reason: Failure reason if not passed / 未通过时的失败原因

    Consumers / 调用方:
        - metanano/pipeline.py: ValidationResult
        - metanano/validators/*.py
    """

    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None


@dataclass
class ValidationResult:
    """
    Complete validation pipeline result.
    完整的验证流水线结果。

    Attributes / 属性:
        validation_status: "Passed" or "Failed" / 验证状态
        failed_filters: List of filter names that failed / 失败的过滤器名称列表
        details: Detailed results from each filter / 每个过滤器的详细结果

    Consumers / 调用方:
        - metanano/routes/validation_routes.py
        - metanano/routes/submission_routes.py
    """

    validation_status: str
    failed_filters: List[str] = field(default_factory=list)
    details: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.
        转换为字典用于 JSON 序列化。

        Returns / 返回:
            Dict[str, Any]: Dictionary representation / 字典表示

        Consumers / 调用方:
            - metanano/routes/validation_routes.py
        """
        return {
            "validation_status": self.validation_status,
            "failed_filters": self.failed_filters,
            "details": self.details,
        }




