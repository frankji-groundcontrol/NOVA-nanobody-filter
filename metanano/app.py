"""
References / 参考:
    - docs/en/README.md: Section 2 - File Structure, Section 3 - Routes
    - docs/cn/README.md: 第2节 - 文件结构, 第3节 - 路由

File / 文件:
    - metanano/app.py

Overview / 概述:
    Main FastAPI application entry point for the MetaNano service.
    MetaNano 服务的 FastAPI 主应用入口。

    This module creates and configures the FastAPI application with all routes.
    该模块创建并配置包含所有路由的 FastAPI 应用。

Consumers / 调用方:
    - uvicorn (runtime)
    - gunicorn (production)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from metanano import __version__
from metanano.routes import (
    health_router,
    submission_router,
    validation_router,
    diversity_router,
    nativeness_router,
    developability_router,
    service_router,
)
from metanano.services.async_manager import get_service_manager


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    创建并配置 FastAPI 应用。

    Returns / 返回:
        FastAPI: Configured application instance.
            配置好的应用实例。

    Example / 示例:
        >>> app = create_app()
        >>> # Run with: uvicorn metanano.app:app --reload

    Consumers / 调用方:
        - __main__ (when run directly)
        - ASGI servers (uvicorn, gunicorn)
    """
    app = FastAPI(
        title="MetaNano - NOVA Nanobody Filter",
        description=(
            "NOVA Nanobody Challenge Submission Filter System. "
            "Validates nanobody sequences through Diversity, Nativeness, "
            "and Developability filters. / "
            "NOVA 纳米抗体挑战赛提交过滤系统。"
            "通过多样性、天然性和可开发性过滤器验证纳米抗体序列。"
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers - Core endpoints
    # 包含路由 - 核心端点
    app.include_router(health_router)
    app.include_router(validation_router)
    app.include_router(submission_router)

    # Include routers - Individual service endpoints
    # 包含路由 - 独立服务端点
    app.include_router(diversity_router)
    app.include_router(nativeness_router)
    app.include_router(developability_router)
    app.include_router(service_router)

    @app.on_event("startup")
    async def startup_event():
        """Initialize async service manager on startup. / 启动时初始化异步服务管理器。"""
        manager = get_service_manager()
        await manager.initialize()

    @app.on_event("shutdown")
    async def shutdown_event():
        """Shutdown async service manager. / 关闭异步服务管理器。"""
        manager = get_service_manager()
        await manager.shutdown()

    return app


# Create application instance
# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "metanano.app:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
    )



