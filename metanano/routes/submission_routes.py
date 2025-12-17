"""
References / 参考:
    - docs/en/README.md: Section 3.1 - /submit (POST)
    - docs/cn/README.md: 第3.1节 - /submit (POST)

File / 文件:
    - metanano/routes/submission_routes.py

Overview / 概述:
    Submission route for handling nanobody sequence submissions.
    处理纳米抗体序列提交的提交路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
"""

from fastapi import APIRouter, HTTPException, status

from metanano.models.sequence import SequenceSubmission
from metanano.models.validation_result import SubmissionResponse
from metanano.pipeline import ValidationPipeline
from metanano.config import Config

router = APIRouter(prefix="/submit", tags=["Submission"])

# Global pipeline instance (can be injected via dependency)
# 全局流水线实例（可通过依赖注入）
_pipeline = ValidationPipeline(Config())


@router.post(
    "",
    response_model=SubmissionResponse,
    summary="Submit Nanobody Sequence / 提交纳米抗体序列",
    description="Submit a nanobody sequence for validation and storage. "
    "The sequence will be validated through all filters before acceptance. / "
    "提交纳米抗体序列进行验证和存储。序列在接受前将通过所有过滤器验证。",
)
async def submit_sequence(
    submission: SequenceSubmission,
) -> SubmissionResponse:
    """
    Handle nanobody sequence submission.
    处理纳米抗体序列提交。

    Args / 参数:
        submission (SequenceSubmission): Submission request with sequence and user_id.
            包含序列和 user_id 的提交请求。

    Returns / 返回:
        SubmissionResponse: Success or error response.
            成功或错误响应。

    Raises / 异常:
        HTTPException: If validation fails (400) or server error (500).
            如果验证失败（400）或服务器错误（500）。

    References / 参考:
        - metanano/pipeline.py: ValidationPipeline

    Consumers / 调用方:
        - External API clients
    """
    try:
        # Run validation pipeline
        # 运行验证流水线
        result = _pipeline.validate(submission.sequence)

        if result.validation_status == "Failed":
            # Return error with details
            # 返回带详情的错误
            failed_filters = ", ".join(result.failed_filters)
            return SubmissionResponse(
                status="Error",
                message=f"Validation failed: {failed_filters}. "
                f"See details for more information. / "
                f"验证失败：{failed_filters}。详情请查看 details。",
            )

        # TODO: Save valid sequence to database
        # TODO: 将有效序列保存到数据库
        # save_submission(submission.sequence, submission.user_id)

        return SubmissionResponse(
            status="Success",
            message="Sequence submitted successfully! / 序列提交成功！",
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





