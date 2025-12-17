"""
References / 参考:
    - docs/en/README.md: Section 3.2 - /validate (POST)
    - docs/cn/README.md: 第3.2节 - /validate (POST)

File / 文件:
    - metanano/routes/validation_routes.py

Overview / 概述:
    Validation route for checking nanobody sequences without submission.
    用于检查纳米抗体序列（不提交）的验证路由。

    Uses async pipeline for concurrent execution with semaphore control.
    使用异步流水线进行带信号量控制的并发执行。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from metanano.models.sequence import Sequence
from metanano.models.validation_result import ValidationResponse
from metanano.pipeline import ValidationPipeline
from metanano.config import Config

router = APIRouter(prefix="/validate", tags=["Validation"])

# Global pipeline instance (can be injected via dependency)
# 全局流水线实例（可通过依赖注入）
_pipeline = ValidationPipeline(Config())


class BatchValidationRequest(BaseModel):
    """Request for batch validation. / 批量验证请求。"""

    sequences: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of sequences to validate. / 要验证的序列列表。",
    )
    historical_sequences: Optional[List[str]] = Field(
        default=None,
        description="Historical sequences for diversity comparison. / "
        "用于多样性比较的历史序列。",
    )


class BatchValidationResponse(BaseModel):
    """Response for batch validation. / 批量验证响应。"""

    results: List[ValidationResponse]
    passed_count: int
    failed_count: int


@router.post(
    "",
    response_model=ValidationResponse,
    summary="Validate Nanobody Sequence / 验证纳米抗体序列",
    description="Validate a nanobody sequence against all filters without storing it. "
    "Returns detailed scores and metrics from each filter. Uses async execution. / "
    "对纳米抗体序列进行所有过滤器验证而不存储。返回每个过滤器的详细分数和指标。使用异步执行。",
)
async def validate_sequence(
    sequence_input: Sequence,
) -> ValidationResponse:
    """
    Validate a nanobody sequence against all filters (async).
    对纳米抗体序列进行所有过滤器验证（异步）。

    Args / 参数:
        sequence_input (Sequence): Sequence to validate.
            要验证的序列。

    Returns / 返回:
        ValidationResponse: Complete validation result with status and details.
            包含状态和详情的完整验证结果。

    Raises / 异常:
        HTTPException: If input is invalid (400) or server error (500).
            如果输入无效（400）或服务器错误（500）。

    References / 参考:
        - metanano/pipeline.py: ValidationPipeline.validate_async

    Consumers / 调用方:
        - External API clients
    """
    try:
        # Run async validation pipeline
        # 运行异步验证流水线
        result = await _pipeline.validate_async(sequence_input.sequence)

        return ValidationResponse(
            validation_status=result.validation_status,
            failed_filters=result.failed_filters,
            details=result.details,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)} / 内部服务器错误：{str(e)}",
        )


@router.post(
    "/batch",
    response_model=BatchValidationResponse,
    summary="Batch Validate Sequences / 批量验证序列",
    description="Validate multiple sequences concurrently. / "
    "并发验证多个序列。",
)
async def validate_batch(
    request: BatchValidationRequest,
) -> BatchValidationResponse:
    """
    Validate multiple sequences (async batch).
    验证多个序列（异步批量）。
    """
    try:
        results = await _pipeline.validate_batch_async(
            sequences=request.sequences,
            historical_sequences=request.historical_sequences,
        )

        responses = [
            ValidationResponse(
                validation_status=r.validation_status,
                failed_filters=r.failed_filters,
                details=r.details,
            )
            for r in results
        ]

        passed_count = sum(1 for r in responses if r.validation_status == "Passed")

        return BatchValidationResponse(
            results=responses,
            passed_count=passed_count,
            failed_count=len(responses) - passed_count,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch validation failed: {str(e)} / 批量验证失败：{str(e)}",
        )



