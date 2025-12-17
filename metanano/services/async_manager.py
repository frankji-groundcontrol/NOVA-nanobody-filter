"""
References / 参考:
    - docs/en/TODO.md: Section 0.7 - Async/Semaphore Concurrency Management
    - metanano/config.py: AsyncConfig, GPUSchedulerConfig

File / 文件:
    - metanano/services/async_manager.py

Overview / 概述:
    Centralized async service manager with semaphore-based concurrency control.
    基于信号量的集中式异步服务管理器并发控制。

    Manages semaphores for all async operations to prevent resource exhaustion.
    管理所有异步操作的信号量以防止资源耗尽。

Consumers / 调用方:
    - metanano/services/*.py
    - metanano/pipeline.py
    - metanano/routes/*.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from metanano.config import AsyncConfig, Config
from metanano.utils.gpu_scheduler import GPUScheduler, get_gpu_scheduler

logger = logging.getLogger(__name__)


class AsyncServiceManager:
    """
    Centralized manager for async service concurrency.
    异步服务并发的集中管理器。

    Provides semaphores for each type of operation to control
    concurrent execution and prevent resource exhaustion.
    为每种类型的操作提供信号量以控制并发执行并防止资源耗尽。

    Example / 示例:
        >>> manager = AsyncServiceManager(config.async_config)
        >>> await manager.initialize()
        >>> async with manager.tnp_semaphore:
        ...     result = await run_tnp_async(sequence)

    Consumers / 调用方:
        - metanano/services/*.py
        - metanano/pipeline.py
    """

    def __init__(self, config: Optional[AsyncConfig] = None) -> None:
        """
        Initialize the async service manager.
        初始化异步服务管理器。

        Args / 参数:
            config (Optional[AsyncConfig]): Async configuration.
                If None, uses default Config().
                异步配置。如果为 None，使用默认 Config()。
        """
        if config is None:
            config = Config().async_config
        self.config = config

        # Initialize semaphores
        # 初始化信号量
        self._validation_semaphore: Optional[asyncio.Semaphore] = None
        self._tnp_semaphore: Optional[asyncio.Semaphore] = None
        self._mmseqs2_semaphore: Optional[asyncio.Semaphore] = None
        self._abnativ_semaphore: Optional[asyncio.Semaphore] = None
        self._promb_semaphore: Optional[asyncio.Semaphore] = None

        # GPU scheduler
        # GPU 调度器
        self._gpu_scheduler: Optional[GPUScheduler] = None

        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """
        Initialize all semaphores and GPU scheduler.
        初始化所有信号量和 GPU 调度器。
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Create semaphores based on config
            # 根据配置创建信号量
            self._validation_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_validations
            )
            self._tnp_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_tnp
            )
            self._mmseqs2_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_mmseqs2
            )
            self._abnativ_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_abnativ
            )
            self._promb_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_promb
            )

            # Initialize GPU scheduler if enabled
            # 如果启用，初始化 GPU 调度器
            if self.config.gpu_scheduler.enabled:
                self._gpu_scheduler = get_gpu_scheduler(self.config.gpu_scheduler)
                await self._gpu_scheduler.initialize()

            self._initialized = True
            logger.info(
                f"AsyncServiceManager initialized: "
                f"validations={self.config.max_concurrent_validations}, "
                f"tnp={self.config.max_concurrent_tnp}, "
                f"mmseqs2={self.config.max_concurrent_mmseqs2}, "
                f"abnativ={self.config.max_concurrent_abnativ}, "
                f"promb={self.config.max_concurrent_promb}"
            )

    async def shutdown(self) -> None:
        """
        Shutdown manager and cleanup resources.
        关闭管理器并清理资源。
        """
        if self._gpu_scheduler:
            await self._gpu_scheduler.shutdown()
        self._initialized = False
        logger.info("AsyncServiceManager shutdown complete")

    @property
    def validation_semaphore(self) -> asyncio.Semaphore:
        """Global validation semaphore. / 全局验证信号量。"""
        if self._validation_semaphore is None:
            raise RuntimeError("AsyncServiceManager not initialized")
        return self._validation_semaphore

    @property
    def tnp_semaphore(self) -> asyncio.Semaphore:
        """TNP subprocess semaphore. / TNP 子进程信号量。"""
        if self._tnp_semaphore is None:
            raise RuntimeError("AsyncServiceManager not initialized")
        return self._tnp_semaphore

    @property
    def mmseqs2_semaphore(self) -> asyncio.Semaphore:
        """MMseqs2 clustering semaphore. / MMseqs2 聚类信号量。"""
        if self._mmseqs2_semaphore is None:
            raise RuntimeError("AsyncServiceManager not initialized")
        return self._mmseqs2_semaphore

    @property
    def abnativ_semaphore(self) -> asyncio.Semaphore:
        """AbnatiV scoring semaphore. / AbnatiV 评分信号量。"""
        if self._abnativ_semaphore is None:
            raise RuntimeError("AsyncServiceManager not initialized")
        return self._abnativ_semaphore

    @property
    def promb_semaphore(self) -> asyncio.Semaphore:
        """promb calculation semaphore. / promb 计算信号量。"""
        if self._promb_semaphore is None:
            raise RuntimeError("AsyncServiceManager not initialized")
        return self._promb_semaphore

    @property
    def gpu_scheduler(self) -> Optional[GPUScheduler]:
        """GPU scheduler instance. / GPU 调度器实例。"""
        return self._gpu_scheduler

    @property
    def task_timeout(self) -> float:
        """Task timeout in seconds. / 任务超时时间（秒）。"""
        return self.config.task_timeout

    @property
    def batch_size(self) -> int:
        """Default batch size. / 默认批次大小。"""
        return self.config.batch_size

    def get_status(self) -> dict:
        """
        Get current status of all semaphores.
        获取所有信号量的当前状态。

        Returns / 返回:
            dict: Status information / 状态信息
        """
        if not self._initialized:
            return {"initialized": False}

        status = {
            "initialized": True,
            "semaphores": {
                "validation": {
                    "max": self.config.max_concurrent_validations,
                    "locked": self._validation_semaphore.locked() if self._validation_semaphore else None,
                },
                "tnp": {
                    "max": self.config.max_concurrent_tnp,
                    "locked": self._tnp_semaphore.locked() if self._tnp_semaphore else None,
                },
                "mmseqs2": {
                    "max": self.config.max_concurrent_mmseqs2,
                    "locked": self._mmseqs2_semaphore.locked() if self._mmseqs2_semaphore else None,
                },
                "abnativ": {
                    "max": self.config.max_concurrent_abnativ,
                    "locked": self._abnativ_semaphore.locked() if self._abnativ_semaphore else None,
                },
                "promb": {
                    "max": self.config.max_concurrent_promb,
                    "locked": self._promb_semaphore.locked() if self._promb_semaphore else None,
                },
            },
            "batch_size": self.config.batch_size,
            "task_timeout": self.config.task_timeout,
        }

        if self._gpu_scheduler:
            status["gpu_scheduler"] = self._gpu_scheduler.get_status()

        return status


# Global service manager instance (singleton)
# 全局服务管理器实例（单例）
_service_manager: Optional[AsyncServiceManager] = None


def get_service_manager(config: Optional[AsyncConfig] = None) -> AsyncServiceManager:
    """
    Get or create the global service manager instance.
    获取或创建全局服务管理器实例。

    Args / 参数:
        config (Optional[AsyncConfig]): Configuration (only used on first call).
            配置（仅在首次调用时使用）。

    Returns / 返回:
        AsyncServiceManager: Global service manager instance.
            全局服务管理器实例。
    """
    global _service_manager
    if _service_manager is None:
        _service_manager = AsyncServiceManager(config)
    return _service_manager


async def reset_service_manager() -> None:
    """
    Reset the global service manager.
    重置全局服务管理器。
    """
    global _service_manager
    if _service_manager is not None:
        await _service_manager.shutdown()
        _service_manager = None

