"""
References / 参考:
    - Standard health check patterns

File / 文件:
    - metanano/routes/health_routes.py

Overview / 概述:
    Health check route for service monitoring.
    用于服务监控的健康检查路由。

Consumers / 调用方:
    - metanano/routes/__init__.py
    - app.py
    - Load balancers, monitoring systems
"""

from typing import Dict

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    summary="Health Check / 健康检查",
    description="Check if the service is healthy and ready to accept requests. / "
    "检查服务是否健康并准备好接受请求。",
)
async def health_check() -> Dict[str, str]:
    """
    Return health status of the service.
    返回服务的健康状态。

    Returns / 返回:
        Dict[str, str]: Health status.
            健康状态。

    Consumers / 调用方:
        - Load balancers
        - Kubernetes probes
        - Monitoring systems
    """
    return {
        "status": "healthy",
        "service": "MetaNano",
        "message": "Service is running. / 服务运行中。",
    }





