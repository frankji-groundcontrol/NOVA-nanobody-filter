"""
References / 参考:
    - docs/en/README.md: Section 1.3 - Developability Filter
    - metanano/services/developability_service.py: DevelopabilityService

File / 文件:
    - metanano/routes/developability_routes.py

Overview / 概述:
    Developability filter service routes.
    可开发性过滤器服务路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from metanano.config import Config
from metanano.services.developability_service import DevelopabilityService

router = APIRouter(prefix="/developability", tags=["Developability"])

# Global service instance
# 全局服务实例
_config = Config()
_service = DevelopabilityService(_config.developability)


class DevelopabilityRequest(BaseModel):
    """
    Request model for developability analysis.
    可开发性分析的请求模型。
    """

    sequence: str = Field(
        ...,
        min_length=10,
        description="Nanobody amino acid sequence. / 纳米抗体氨基酸序列。",
    )


class DevelopabilityResponse(BaseModel):
    """
    Response model for developability analysis.
    可开发性分析的响应模型。
    """

    passed: bool = Field(
        ...,
        description="Whether sequence passed (no Red Region criteria triggered). / "
        "序列是否通过（无红区标准被触发）。",
    )
    total_cdr_length: Optional[int] = Field(
        default=None,
        description="Total CDR length (valid: 20-39). / 总 CDR 长度（有效：20-39）。",
    )
    cdr3_length: Optional[int] = Field(
        default=None,
        description="CDR3 length (valid: 5-23). / CDR3 长度（有效：5-23）。",
    )
    cdr3_compactness: Optional[float] = Field(
        default=None,
        description="CDR3 compactness (valid: 0.56-1.61). / CDR3 紧凑度（有效：0.56-1.61）。",
    )
    surface_hydrophobic_patches: Optional[float] = Field(
        default=None,
        description="PSH score (valid: 73.4-155.47). / PSH 分数（有效：73.4-155.47）。",
    )
    positive_charge_patches: Optional[float] = Field(
        default=None,
        description="PPC score (max: 1.18). / PPC 分数（最大：1.18）。",
    )
    negative_charge_patches: Optional[float] = Field(
        default=None,
        description="PNC score (max: 1.88). / PNC 分数（最大：1.88）。",
    )
    flags: Optional[Dict[str, str]] = Field(
        default=None,
        description="TNP flag colors for each property. / 每个属性的 TNP 标志颜色。",
    )
    red_flags: Optional[List[str]] = Field(
        default=None,
        description="Red Region criteria that were triggered. / 被触发的红区标准。",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Failure reason if not passed. / 未通过时的失败原因。",
    )


@router.post(
    "/analyze",
    response_model=DevelopabilityResponse,
    summary="Analyze Sequence Developability / 分析序列可开发性",
    description="Check if sequence meets therapeutic developability requirements (Red Region criteria). / "
    "检查序列是否满足治疗可开发性要求（红区标准）。",
)
async def analyze_developability(request: DevelopabilityRequest) -> DevelopabilityResponse:
    """
    Analyze sequence developability.
    分析序列可开发性。
    """
    try:
        result = await _service.analyze_async(
            sequence=request.sequence.strip().upper(),
        )
        return DevelopabilityResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Developability analysis failed: {str(e)} / 可开发性分析失败：{str(e)}",
        )


class TNPProfileRequest(BaseModel):
    """Request for TNP profiling. / TNP 分析请求。"""

    sequence: str = Field(..., min_length=10)


class TNPProfileResponse(BaseModel):
    """Response for TNP profiling. / TNP 分析响应。"""

    success: bool
    total_cdr_length: Optional[int] = None
    cdr3_length: Optional[int] = None
    cdr3_compactness: Optional[float] = None
    surface_hydrophobic_patches: Optional[float] = None
    positive_charge_patches: Optional[float] = None
    negative_charge_patches: Optional[float] = None
    flags: Optional[Dict[str, str]] = None


@router.post(
    "/tnp-profile",
    response_model=TNPProfileResponse,
    summary="Get TNP Profile / 获取 TNP 分析",
    description="Run TNP (Therapeutic Nanobody Profiler) on sequence. / "
    "对序列运行 TNP（治疗性纳米抗体分析器）。",
)
async def get_tnp_profile(request: TNPProfileRequest) -> TNPProfileResponse:
    """
    Get TNP profile.
    获取 TNP 分析。
    """
    try:
        result = await _service.compute_tnp_profile_async(
            sequence=request.sequence.strip().upper(),
        )
        if result is None:
            return TNPProfileResponse(success=False)
        return TNPProfileResponse(
            success=True,
            total_cdr_length=result.get("total_cdr_length"),
            cdr3_length=result.get("cdr3_length"),
            cdr3_compactness=result.get("cdr3_compactness"),
            surface_hydrophobic_patches=result.get("surface_hydrophobic_patches"),
            positive_charge_patches=result.get("positive_charge_patches"),
            negative_charge_patches=result.get("negative_charge_patches"),
            flags=result.get("flags"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TNP profiling failed: {str(e)}",
        )


class BatchDevelopabilityRequest(BaseModel):
    """Request for batch developability analysis. / 批量可开发性分析请求。"""

    sequences: List[str] = Field(..., min_length=1, max_length=100)


class BatchDevelopabilityResponse(BaseModel):
    """Response for batch developability analysis. / 批量可开发性分析响应。"""

    results: List[DevelopabilityResponse]
    passed_count: int
    failed_count: int


@router.post(
    "/analyze-batch",
    response_model=BatchDevelopabilityResponse,
    summary="Batch Analyze Developability / 批量分析可开发性",
    description="Analyze multiple sequences for developability. / "
    "批量分析多个序列的可开发性。",
)
async def analyze_batch(request: BatchDevelopabilityRequest) -> BatchDevelopabilityResponse:
    """
    Batch analyze developability.
    批量分析可开发性。
    """
    try:
        sequences = [s.strip().upper() for s in request.sequences]
        results = await _service.analyze_batch_async(sequences)

        responses = [DevelopabilityResponse(**r) for r in results]
        passed_count = sum(1 for r in responses if r.passed)

        return BatchDevelopabilityResponse(
            results=responses,
            passed_count=passed_count,
            failed_count=len(responses) - passed_count,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch analysis failed: {str(e)}",
        )

