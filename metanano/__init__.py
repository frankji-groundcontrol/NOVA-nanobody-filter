"""
References / 参考:
    - docs/en/README.md: Project architecture and design
    - docs/cn/README.md: 项目架构与设计

File / 文件:
    - metanano/__init__.py

Overview / 概述:
    MetaNano - NOVA Nanobody Challenge Submission Filter System.
    MetaNano - NOVA 纳米抗体挑战赛提交过滤系统。

    This package provides a modular nanobody validation pipeline with three
    cascading filters: Diversity, Nativeness, and Developability.
    该包提供模块化的纳米抗体验证流水线，包含三个级联过滤器：
    多样性、天然性和可开发性。

Consumers / 调用方:
    - app.py: Main application entry point / 主应用入口
    - External integrations / 外部集成
"""

__version__ = "0.1.0"
__author__ = "NOVA Team"

from metanano.config import Config
from metanano.pipeline import ValidationPipeline

__all__ = [
    "Config",
    "ValidationPipeline",
    "__version__",
]





