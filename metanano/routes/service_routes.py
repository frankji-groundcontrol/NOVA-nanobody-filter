"""
References / 参考:
    - docs/en/TODO.md: Section 0.7 - Async/Semaphore Concurrency Management
    - metanano/services/async_manager.py: AsyncServiceManager
    - metanano/utils/gpu_scheduler.py: GPUScheduler

File / 文件:
    - metanano/routes/service_routes.py

Overview / 概述:
    Service management routes for GPU scheduler and async manager status.
    GPU 调度器和异步管理器状态的服务管理路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from metanano.services.async_manager import get_service_manager

router = APIRouter(prefix="/services", tags=["Services"])


class ServiceStatusResponse(BaseModel):
    """
    Response model for service status.
    服务状态的响应模型。
    """

    initialized: bool = Field(
        ...,
        description="Whether service manager is initialized. / 服务管理器是否已初始化。",
    )
    semaphores: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Semaphore status for each operation type. / 每种操作类型的信号量状态。",
    )
    batch_size: Optional[int] = Field(
        default=None,
        description="Default batch size. / 默认批次大小。",
    )
    task_timeout: Optional[float] = Field(
        default=None,
        description="Task timeout in seconds. / 任务超时时间（秒）。",
    )
    gpu_scheduler: Optional[Dict[str, Any]] = Field(
        default=None,
        description="GPU scheduler status. / GPU 调度器状态。",
    )


@router.get(
    "/status",
    response_model=ServiceStatusResponse,
    summary="Get Service Status / 获取服务状态",
    description="Get status of async service manager and GPU scheduler. / "
    "获取异步服务管理器和 GPU 调度器的状态。",
)
async def get_service_status() -> ServiceStatusResponse:
    """
    Get service status.
    获取服务状态。
    """
    try:
        manager = get_service_manager()
        await manager.initialize()
        status_data = manager.get_status()
        return ServiceStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service status: {str(e)}",
        )


class GPUStatusResponse(BaseModel):
    """
    Response model for GPU status.
    GPU 状态的响应模型。
    """

    enabled: bool = Field(
        ...,
        description="Whether GPU scheduling is enabled. / GPU 调度是否启用。",
    )
    initialized: bool = Field(
        default=False,
        description="Whether GPU scheduler is initialized. / GPU 调度器是否已初始化。",
    )
    total_gpus: int = Field(
        default=0,
        description="Total number of registered GPUs. / 注册的 GPU 总数。",
    )
    available_gpus: int = Field(
        default=0,
        description="Number of GPUs available for tasks. / 可用于任务的 GPU 数量。",
    )
    active_tasks: int = Field(
        default=0,
        description="Number of currently active GPU tasks. / 当前活动的 GPU 任务数。",
    )
    queue_size: int = Field(
        default=0,
        description="Number of tasks in queue. / 队列中的任务数。",
    )
    last_used_gpu: Optional[int] = Field(
        default=None,
        description="Index of the last GPU used for a task. / 上次用于任务的 GPU 索引。",
    )
    recent_gpu_usage: Optional[list] = Field(
        default=None,
        description="Recent GPU usage history (last 5). / 最近的 GPU 使用历史（最后 5 条）。",
    )
    gpus: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed status for each GPU. / 每个 GPU 的详细状态。",
    )


@router.get(
    "/gpu",
    response_model=GPUStatusResponse,
    summary="Get GPU Scheduler Status / 获取 GPU 调度器状态",
    description="Get real-time status of GPU scheduler including per-GPU metrics. / "
    "获取 GPU 调度器的实时状态，包括每个 GPU 的指标。",
)
async def get_gpu_status() -> GPUStatusResponse:
    """
    Get GPU scheduler status (real-time).
    获取 GPU 调度器状态（实时）。
    """
    try:
        manager = get_service_manager()
        await manager.initialize()

        if manager.gpu_scheduler is None:
            return GPUStatusResponse(enabled=False)

        # Refresh GPU status to get real-time memory info
        # 刷新 GPU 状态以获取实时内存信息
        await manager.gpu_scheduler.refresh_status()

        status_data = manager.gpu_scheduler.get_status()
        return GPUStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get GPU status: {str(e)}",
        )


class GPUControlRequest(BaseModel):
    """Request for GPU control operations. / GPU 控制操作请求。"""

    gpu_index: int = Field(..., ge=0, description="GPU device index. / GPU 设备索引。")
    action: str = Field(
        ...,
        pattern="^(enable|disable)$",
        description="Action: 'enable' or 'disable'. / 操作：'enable' 或 'disable'。",
    )


class GPUControlResponse(BaseModel):
    """Response for GPU control operations. / GPU 控制操作响应。"""

    success: bool
    gpu_index: int
    action: str
    message: str


@router.post(
    "/gpu/control",
    response_model=GPUControlResponse,
    summary="Control GPU / 控制 GPU",
    description="Enable or disable a specific GPU for scheduling. / "
    "启用或禁用特定 GPU 进行调度。",
)
async def control_gpu(request: GPUControlRequest) -> GPUControlResponse:
    """
    Control GPU enable/disable.
    控制 GPU 启用/禁用。
    """
    try:
        manager = get_service_manager()
        await manager.initialize()

        if manager.gpu_scheduler is None:
            return GPUControlResponse(
                success=False,
                gpu_index=request.gpu_index,
                action=request.action,
                message="GPU scheduler is not enabled. / GPU 调度器未启用。",
            )

        if request.action == "enable":
            success = manager.gpu_scheduler.enable_gpu(request.gpu_index)
        else:
            success = manager.gpu_scheduler.disable_gpu(request.gpu_index)

        return GPUControlResponse(
            success=success,
            gpu_index=request.gpu_index,
            action=request.action,
            message=f"GPU {request.gpu_index} {request.action}d successfully"
            if success
            else f"GPU {request.gpu_index} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPU control failed: {str(e)}",
        )

