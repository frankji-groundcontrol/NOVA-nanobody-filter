"""
References / 参考:
    - docs/en/README.md: Section 3 - Routes (API Definitions)
    - docs/cn/README.md: 第3节 - 路由（API定义）

File / 文件:
    - metanano/routes/__init__.py

Overview / 概述:
    API route definitions for the MetaNano service.
    MetaNano 服务的 API 路由定义。

    Routes:
    路由：
        - /submit (POST): Submit nanobody sequences
        - /validate (POST): Validate sequences without submission
        - /health (GET): Health check endpoint
        - /diversity/*: Diversity filter service endpoints
        - /nativeness/*: Nativeness filter service endpoints
        - /developability/*: Developability filter service endpoints
        - /services/*: Service management endpoints (GPU, semaphores)

Consumers / 调用方:
    - app.py: Main application
"""

from metanano.routes.submission_routes import router as submission_router
from metanano.routes.validation_routes import router as validation_router
from metanano.routes.health_routes import router as health_router
from metanano.routes.diversity_routes import router as diversity_router
from metanano.routes.nativeness_routes import router as nativeness_router
from metanano.routes.developability_routes import router as developability_router
from metanano.routes.service_routes import router as service_router

__all__ = [
    "submission_router",
    "validation_router",
    "health_router",
    "diversity_router",
    "nativeness_router",
    "developability_router",
    "service_router",
]



