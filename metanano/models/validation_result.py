"""
References / 参考:
    - docs/en/README.md: Section 3 - Routes (API Definitions)
    - docs/cn/README.md: 第3节 - 路由（API定义）

File / 文件:
    - metanano/models/validation_result.py

Overview / 概述:
    Pydantic models for API response structures.
    API 响应结构的 Pydantic 模型。

Consumers / 调用方:
    - metanano/models/__init__.py
    - metanano/routes/submission_routes.py
    - metanano/routes/validation_routes.py
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DiversityDetails(BaseModel):
    """
    Details from diversity filter analysis.
    多样性过滤器分析详情。

    Consumers / 调用方:
        - ValidationDetails
    """

    passed: Optional[bool] = Field(
        default=None,
        description="Whether diversity check passed. / 多样性检查是否通过。",
    )
    global_cluster_identity: Optional[float] = Field(
        default=None,
        description="Maximum sequence identity found in batch clustering. / "
        "批次聚类中发现的最大序列相似度。",
    )
    cdrs_combined_mutations: Optional[int] = Field(
        default=None,
        description="Total mutations across all CDRs. / 所有 CDR 的总突变数。",
    )
    cdr3_mutations: Optional[int] = Field(
        default=None,
        description="Mutations in CDR3 region. / CDR3 区域的突变数。",
    )
    jaccard_similarity: Optional[float] = Field(
        default=None,
        description="Maximum Jaccard similarity to historical sequences. / "
        "与历史序列的最大 Jaccard 相似度。",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Failure reason if check failed. / 检查失败时的原因。",
    )


class NativenessDetails(BaseModel):
    """
    Details from nativeness filter analysis.
    天然性过滤器分析详情。

    Consumers / 调用方:
        - ValidationDetails
    """

    passed: Optional[bool] = Field(
        default=None,
        description="Whether nativeness check passed. / 天然性检查是否通过。",
    )
    imgt_numbered: Optional[bool] = Field(
        default=None,
        description="Whether IMGT numbering succeeded. / IMGT 编号是否成功。",
    )
    nativeness_score: Optional[float] = Field(
        default=None,
        description="AbnatiV nativeness score (0-1). / AbnatiV 天然性分数（0-1）。",
    )
    humanness_score: Optional[float] = Field(
        default=None,
        description="AbnatiV humanness score (0-1). / AbnatiV 人源性分数（0-1）。",
    )
    promb_score: Optional[float] = Field(
        default=None,
        description="Optional promb OASis score. / 可选的 promb OASis 分数。",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Failure reason if check failed. / 检查失败时的原因。",
    )


class DevelopabilityDetails(BaseModel):
    """
    Details from developability filter analysis.
    可开发性过滤器分析详情。

    Consumers / 调用方:
        - ValidationDetails
    """

    passed: Optional[bool] = Field(
        default=None,
        description="Whether developability check passed (no red flags triggered). / "
        "可开发性检查是否通过（无红旗触发）。",
    )
    total_cdr_length: Optional[int] = Field(
        default=None,
        description="Total length of all CDRs. Valid range: [20, 39]. / "
        "所有 CDR 的总长度。有效范围：[20, 39]。",
    )
    cdr3_length: Optional[int] = Field(
        default=None,
        description="Length of CDR3 region. Valid range: [5, 23]. / "
        "CDR3 区域的长度。有效范围：[5, 23]。",
    )
    cdr3_compactness: Optional[float] = Field(
        default=None,
        description="CDR3 compactness score. Valid range: [0.56, 1.61]. / "
        "CDR3 紧凑度分数。有效范围：[0.56, 1.61]。",
    )
    surface_hydrophobic_patches: Optional[float] = Field(
        default=None,
        description="Surface hydrophobic patches (PSH). Valid range: [73.4, 155.47]. / "
        "表面疏水性斑块（PSH）。有效范围：[73.4, 155.47]。",
    )
    positive_charge_patches: Optional[float] = Field(
        default=None,
        description="Positive charge patches (PPC). Max threshold: 1.18. / "
        "正电荷斑块（PPC）。最大阈值：1.18。",
    )
    negative_charge_patches: Optional[float] = Field(
        default=None,
        description="Negative charge patches (PNC). Max threshold: 1.88. / "
        "负电荷斑块（PNC）。最大阈值：1.88。",
    )
    red_flags: Optional[List[str]] = Field(
        default=None,
        description="List of Red Region criteria that were triggered (rejection reasons). / "
        "被触发的红区标准列表（拒绝原因）。",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Combined failure reason if check failed. / "
        "检查失败时的综合失败原因。",
    )


class ValidationDetails(BaseModel):
    """
    Complete validation details from all filters.
    所有过滤器的完整验证详情。

    Consumers / 调用方:
        - ValidationResponse
    """

    diversity: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Diversity filter results. / 多样性过滤器结果。",
    )
    nativeness: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Nativeness filter results. / 天然性过滤器结果。",
    )
    developability: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Developability filter results. / 可开发性过滤器结果。",
    )


class ValidationResponse(BaseModel):
    """
    Response model for /validate endpoint.
    /validate 端点的响应模型。

    Example / 示例:
        >>> response = ValidationResponse(
        ...     validation_status="Passed",
        ...     failed_filters=[],
        ...     details={...}
        ... )

    Consumers / 调用方:
        - metanano/routes/validation_routes.py
    """

    validation_status: Literal["Passed", "Failed"] = Field(
        ...,
        description="Overall validation result: 'Passed' or 'Failed'. / "
        "整体验证结果：'Passed' 或 'Failed'。",
    )
    failed_filters: List[str] = Field(
        default_factory=list,
        description="List of filter names that failed. / 失败的过滤器名称列表。",
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed results from each filter. / 每个过滤器的详细结果。",
    )

    class Config:
        """Pydantic configuration. / Pydantic 配置。"""

        json_schema_extra = {
            "example": {
                "validation_status": "Passed",
                "failed_filters": [],
                "details": {
                    "diversity": {
                        "passed": True,
                        "global_cluster_identity": 0.85,
                        "cdrs_combined_mutations": 3,
                        "cdr3_mutations": 2,
                        "jaccard_similarity": 0.72,
                    },
                    "nativeness": {
                        "passed": True,
                        "imgt_numbered": True,
                        "nativeness_score": 0.92,
                        "humanness_score": 0.88,
                    },
                    "developability": {
                        "passed": True,
                        "total_cdr_length": 18,
                        "cdr3_length": 4,
                        "cdr3_compactness": 0.45,
                        "surface_hydrophobic_patches": 70.2,
                        "positive_charge_patches": 1.25,
                        "negative_charge_patches": 1.95,
                    },
                },
            }
        }


class SubmissionResponse(BaseModel):
    """
    Response model for /submit endpoint.
    /submit 端点的响应模型。

    Consumers / 调用方:
        - metanano/routes/submission_routes.py
    """

    status: Literal["Success", "Error"] = Field(
        ...,
        description="Submission status: 'Success' or 'Error'. / "
        "提交状态：'Success' 或 'Error'。",
    )
    message: str = Field(
        ...,
        description="Status message with details. / 包含详情的状态消息。",
    )

    class Config:
        """Pydantic configuration. / Pydantic 配置。"""

        json_schema_extra = {
            "example": {
                "status": "Success",
                "message": "Sequence submitted successfully!",
            }
        }

