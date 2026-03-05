"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - metanano/services/nativeness_service.py: NativenessService

File / 文件:
    - metanano/routes/nativeness_routes.py

Overview / 概述:
    Nativeness filter service routes.
    天然性过滤器服务路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from metanano.config import Config
from metanano.services.nativeness_service import NativenessService

router = APIRouter(prefix="/nativeness", tags=["Nativeness"])

# Global service instance
# 全局服务实例
_config = Config()
_service = NativenessService(_config.nativeness)


class NativenessRequest(BaseModel):
    """
    Request model for nativeness analysis.
    天然性分析的请求模型。
    """

    sequence: str = Field(
        ...,
        min_length=10,
        description="Nanobody amino acid sequence. / 纳米抗体氨基酸序列。",
    )


class NativenessResponse(BaseModel):
    """
    Response model for nativeness analysis.
    天然性分析的响应模型。
    """

    passed: bool = Field(
        ...,
        description="Whether nativeness requirements are met. / 是否满足天然性要求。",
    )
    imgt_numbered: Optional[bool] = Field(
        default=None,
        description="Whether IMGT numbering succeeded. / IMGT 编号是否成功。",
    )
    cdr1: Optional[str] = Field(
        default=None,
        description="CDR1 sequence. / CDR1 序列。",
    )
    cdr2: Optional[str] = Field(
        default=None,
        description="CDR2 sequence. / CDR2 序列。",
    )
    cdr3: Optional[str] = Field(
        default=None,
        description="CDR3 sequence. / CDR3 序列。",
    )
    nativeness_score: Optional[float] = Field(
        default=None,
        description="Nativeness score (0-1). / 天然性分数（0-1）。",
    )
    humanness_score: Optional[float] = Field(
        default=None,
        description="Humanness score (0-1). / 人源性分数（0-1）。",
    )
    promb_score: Optional[float] = Field(
        default=None,
        description="Optional promb OASis score. / 可选的 promb OASis 分数。",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Failure reason if not passed. / 未通过时的失败原因。",
    )


@router.post(
    "/analyze",
    response_model=NativenessResponse,
    summary="Analyze Sequence Nativeness / 分析序列天然性",
    description="Check if sequence meets nativeness and humanness requirements. / "
    "检查序列是否满足天然性和人源性要求。",
)
async def analyze_nativeness(request: NativenessRequest) -> NativenessResponse:
    """
    Analyze sequence nativeness.
    分析序列天然性。
    """
    try:
        result = await _service.analyze_async(
            sequence=request.sequence.strip().upper(),
        )
        return NativenessResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Nativeness analysis failed: {str(e)} / 天然性分析失败：{str(e)}",
        )


class IMGTRequest(BaseModel):
    """Request for IMGT numbering. / IMGT 编号请求。"""

    sequence: str = Field(..., min_length=10)


class IMGTResponse(BaseModel):
    """Response for IMGT numbering. / IMGT 编号响应。"""

    success: bool
    scheme: Optional[str] = None
    cdr1: Optional[str] = None
    cdr2: Optional[str] = None
    cdr3: Optional[str] = None


@router.post(
    "/imgt-number",
    response_model=IMGTResponse,
    summary="Apply IMGT Numbering / 应用 IMGT 编号",
    description="Apply IMGT numbering scheme to extract CDR regions. / "
    "应用 IMGT 编号方案提取 CDR 区域。",
)
async def imgt_number(request: IMGTRequest) -> IMGTResponse:
    """
    Apply IMGT numbering.
    应用 IMGT 编号。
    """
    try:
        result = await _service.number_sequence_async(
            sequence=request.sequence.strip().upper(),
        )
        if result is None:
            return IMGTResponse(success=False)
        return IMGTResponse(
            success=True,
            scheme=result.get("scheme"),
            cdr1=result.get("cdr1"),
            cdr2=result.get("cdr2"),
            cdr3=result.get("cdr3"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"IMGT numbering failed: {str(e)}",
        )


class ScoringRequest(BaseModel):
    """Request for scoring. / 评分请求。"""

    sequence: str = Field(..., min_length=10)


class ScoringResponse(BaseModel):
    """Response for scoring. / 评分响应。"""

    nativeness_score: Optional[float] = None
    humanness_score: Optional[float] = None
    promb_score: Optional[float] = None


@router.post(
    "/scores",
    response_model=ScoringResponse,
    summary="Get Nativeness Scores / 获取天然性分数",
    description="Compute nativeness, humanness, and optional promb scores. / "
    "计算天然性、人源性和可选的 promb 分数。",
)
async def get_scores(request: ScoringRequest) -> ScoringResponse:
    """
    Get nativeness scores.
    获取天然性分数。
    """
    try:
        sequence = request.sequence.strip().upper()

        # Run scoring in parallel
        # 并行运行评分
        import asyncio
        nativeness, humanness, promb = await asyncio.gather(
            _service.compute_nativeness_score_async(sequence),
            _service.compute_humanness_score_async(sequence),
            _service.compute_promb_score_async(sequence),
        )

        return ScoringResponse(
            nativeness_score=nativeness,
            humanness_score=humanness,
            promb_score=promb,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {str(e)}",
        )

