"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Diversity Filter
    - metanano/services/diversity_service.py: DiversityService

File / 文件:
    - metanano/routes/diversity_routes.py

Overview / 概述:
    Diversity filter service routes.
    多样性过滤器服务路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from metanano.config import Config
from metanano.services.diversity_service import DiversityService

router = APIRouter(prefix="/diversity", tags=["Diversity"])

# Global service instance
# 全局服务实例
_config = Config()
_service = DiversityService(_config.diversity)


class DiversityRequest(BaseModel):
    """
    Request model for diversity analysis.
    多样性分析的请求模型。
    """

    sequence: str = Field(
        ...,
        min_length=10,
        description="Nanobody amino acid sequence. / 纳米抗体氨基酸序列。",
    )
    batch_sequences: Optional[List[str]] = Field(
        default=None,
        description="Other sequences in the same batch for comparison. / "
        "同一批次中用于比较的其他序列。",
    )
    historical_sequences: Optional[List[str]] = Field(
        default=None,
        description="Historical submissions for similarity check. / "
        "用于相似度检查的历史提交序列。",
    )


class DiversityResponse(BaseModel):
    """
    Response model for diversity analysis.
    多样性分析的响应模型。
    """

    passed: bool = Field(
        ...,
        description="Whether diversity requirements are met. / 是否满足多样性要求。",
    )
    global_cluster_identity: Optional[float] = Field(
        default=None,
        description="Maximum sequence identity in batch. / 批次中的最大序列相似度。",
    )
    cdrs_combined_mutations: Optional[int] = Field(
        default=None,
        description="Total mutations across CDRs. / CDR 总突变数。",
    )
    cdr3_mutations: Optional[int] = Field(
        default=None,
        description="Mutations in CDR3. / CDR3 突变数。",
    )
    jaccard_similarity: Optional[float] = Field(
        default=None,
        description="Max similarity to historical sequences. / 与历史序列的最大相似度。",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Failure reason if not passed. / 未通过时的失败原因。",
    )


@router.post(
    "/analyze",
    response_model=DiversityResponse,
    summary="Analyze Sequence Diversity / 分析序列多样性",
    description="Check if sequence meets diversity requirements against batch and historical sequences. / "
    "检查序列是否满足与批次和历史序列的多样性要求。",
)
async def analyze_diversity(request: DiversityRequest) -> DiversityResponse:
    """
    Analyze sequence diversity.
    分析序列多样性。
    """
    try:
        result = await _service.analyze_async(
            sequence=request.sequence.strip().upper(),
            batch_sequences=request.batch_sequences,
            historical_sequences=request.historical_sequences,
        )
        return DiversityResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diversity analysis failed: {str(e)} / 多样性分析失败：{str(e)}",
        )


class BatchDiversityRequest(BaseModel):
    """Request for batch diversity check. / 批次多样性检查请求。"""

    sequence: str = Field(..., min_length=10)
    batch_sequences: List[str] = Field(..., min_length=1)


class BatchDiversityResponse(BaseModel):
    """Response for batch diversity check. / 批次多样性检查响应。"""

    passed: bool
    max_identity: Optional[float] = None


@router.post(
    "/batch-check",
    response_model=BatchDiversityResponse,
    summary="Check Batch Diversity / 检查批次多样性",
    description="Check if sequence is diverse within a submission batch using MMseqs2. / "
    "使用 MMseqs2 检查序列在提交批次内是否具有多样性。",
)
async def check_batch_diversity(request: BatchDiversityRequest) -> BatchDiversityResponse:
    """
    Check batch diversity.
    检查批次多样性。
    """
    try:
        passed, max_identity = await _service.check_batch_diversity_async(
            sequence=request.sequence.strip().upper(),
            batch_sequences=[s.strip().upper() for s in request.batch_sequences],
        )
        return BatchDiversityResponse(passed=passed, max_identity=max_identity)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch diversity check failed: {str(e)}",
        )


class CDRMutationRequest(BaseModel):
    """Request for CDR mutation check. / CDR 突变检查请求。"""

    sequence: str = Field(..., min_length=10)
    reference_sequence: Optional[str] = Field(default=None)


class CDRMutationResponse(BaseModel):
    """Response for CDR mutation check. / CDR 突变检查响应。"""

    passed: bool
    cdrs_combined_mutations: int
    cdr3_mutations: int


@router.post(
    "/cdr-mutations",
    response_model=CDRMutationResponse,
    summary="Check CDR Mutations / 检查 CDR 突变",
    description="Check if sequence has sufficient CDR mutations. / "
    "检查序列是否有足够的 CDR 突变。",
)
async def check_cdr_mutations(request: CDRMutationRequest) -> CDRMutationResponse:
    """
    Check CDR mutations.
    检查 CDR 突变。
    """
    try:
        passed, combined, cdr3 = await _service.check_cdr_mutations_async(
            sequence=request.sequence.strip().upper(),
            reference_sequence=request.reference_sequence,
        )
        return CDRMutationResponse(
            passed=passed,
            cdrs_combined_mutations=combined,
            cdr3_mutations=cdr3,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CDR mutation check failed: {str(e)}",
        )

