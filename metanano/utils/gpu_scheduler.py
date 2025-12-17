"""
References / 参考:
    - metanano/config.py: GPUSchedulerConfig, GPUConfig
    - docs/en/README.md: GPU Scheduling section

File / 文件:
    - metanano/utils/gpu_scheduler.py

Overview / 概述:
    In-memory GPU scheduler for managing GPU-bound async tasks.
    用于管理 GPU 密集型异步任务的内存 GPU 调度器。

    Features / 功能:
    - Real-time GPU utilization tracking (queue + active tasks)
    - 实时 GPU 利用率跟踪（队列 + 活动任务）
    - Assignment based on availability (round-robin, least-loaded, memory-aware)
    - 基于可用性的分配（轮询、最少负载、内存感知）
    - GPU registration and dynamic enable/disable
    - GPU 注册和动态启用/禁用

Consumers / 调用方:
    - metanano/filters/nativeness.py
    - metanano/pipeline.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional, TypeVar

from metanano.config import GPUConfig, GPUSchedulerConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GPUStatus(Enum):
    """
    GPU device status.
    GPU 设备状态。
    """

    AVAILABLE = "available"  # Ready for new tasks / 准备接受新任务
    BUSY = "busy"  # At max capacity / 已达最大容量
    OVERLOADED = "overloaded"  # Memory threshold exceeded / 超出内存阈值
    DISABLED = "disabled"  # Manually disabled / 手动禁用
    ERROR = "error"  # GPU error detected / 检测到 GPU 错误


@dataclass
class GPUState:
    """
    Runtime state for a single GPU device.
    单个 GPU 设备的运行时状态。
    """

    index: int
    config: GPUConfig
    status: GPUStatus = GPUStatus.AVAILABLE
    active_tasks: int = 0
    queued_tasks: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    gpu_util_percent: float = 0.0  # GPU utilization % / GPU 利用率 %
    last_health_check: float = field(default_factory=time.time)
    semaphore: Optional[asyncio.Semaphore] = None

    def __post_init__(self) -> None:
        """Initialize semaphore based on config."""
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

    @property
    def load(self) -> float:
        """
        Current load ratio (0.0 to 1.0+).
        当前负载比率（0.0 到 1.0+）。
        """
        max_tasks = self.config.max_concurrent_tasks
        return (self.active_tasks + self.queued_tasks) / max_tasks if max_tasks > 0 else 1.0

    @property
    def memory_percent(self) -> float:
        """
        Memory usage percentage.
        内存使用百分比。
        """
        if self.memory_total_mb <= 0:
            return 0.0
        return (self.memory_used_mb / self.memory_total_mb) * 100.0

    @property
    def is_available(self) -> bool:
        """
        Check if GPU can accept new tasks.
        检查 GPU 是否可以接受新任务。

        A GPU is available if:
        GPU 可用的条件是：
        - It is enabled / 已启用
        - Status is AVAILABLE or BUSY (not OVERLOADED, DISABLED, ERROR)
        - 状态为 AVAILABLE 或 BUSY（不是 OVERLOADED、DISABLED、ERROR）
        - Has capacity for more tasks / 有更多任务的容量
        """
        return (
            self.config.enabled
            and self.status in (GPUStatus.AVAILABLE, GPUStatus.BUSY)
            and self.active_tasks < self.config.max_concurrent_tasks
        )


@dataclass
class TaskInfo:
    """
    Information about a scheduled task.
    已调度任务的信息。
    """

    task_id: str
    gpu_index: int
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None


class GPUScheduler:
    """
    In-memory GPU scheduler for async task management.
    用于异步任务管理的内存 GPU 调度器。

    Example / 示例:
        >>> from metanano.config import Config
        >>> config = Config()
        >>> scheduler = GPUScheduler(config.async_config.gpu_scheduler)
        >>> await scheduler.initialize()
        >>> gpu_index = await scheduler.acquire_gpu()
        >>> try:
        ...     result = await run_gpu_task(gpu_index)
        ... finally:
        ...     scheduler.release_gpu(gpu_index)
    """

    def __init__(self, config: GPUSchedulerConfig) -> None:
        """
        Initialize GPU scheduler with configuration.
        使用配置初始化 GPU 调度器。

        Args:
            config: GPU scheduler configuration / GPU 调度器配置
        """
        self.config = config
        self._gpus: dict[int, GPUState] = {}
        self._task_queue: asyncio.Queue[TaskInfo] = asyncio.Queue(
            maxsize=config.queue_max_size
        )
        self._active_tasks: dict[str, TaskInfo] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._round_robin_index = 0
        self._health_check_task: Optional[asyncio.Task[None]] = None
        self._task_counter = 0
        # Track previously used GPUs to avoid reusing the same one
        # 跟踪之前使用的 GPU 以避免重复使用同一个
        self._last_used_gpu: Optional[int] = None
        self._gpu_usage_queue: list[int] = []  # Recent GPU usage history / 最近的 GPU 使用历史

    async def initialize(self) -> None:
        """
        Initialize scheduler and detect/register GPUs.
        初始化调度器并检测/注册 GPU。
        """
        if self._initialized:
            return

        async with self._lock:
            if not self.config.enabled:
                logger.info("GPU scheduler disabled, using CPU fallback")
                self._initialized = True
                return

            # Register manually configured GPUs
            # 注册手动配置的 GPU
            if self.config.gpus:
                for gpu_config in self.config.gpus:
                    await self._register_gpu(gpu_config)
                logger.info(f"Registered {len(self.config.gpus)} manual GPU(s)")

            # Auto-detect GPUs if enabled and no manual config
            # 如果启用且没有手动配置，自动检测 GPU
            elif self.config.auto_detect:
                detected = await self._detect_gpus()
                for gpu_index in detected:
                    gpu_config = GPUConfig(
                        index=gpu_index,
                        max_concurrent_tasks=self.config.default_max_concurrent_per_gpu,
                    )
                    await self._register_gpu(gpu_config)
                logger.info(f"Auto-detected {len(detected)} GPU(s)")

            # Start health check background task
            # 启动健康检查后台任务
            if self._gpus:
                self._health_check_task = asyncio.create_task(self._health_check_loop())

            self._initialized = True
            logger.info(f"GPU scheduler initialized with {len(self._gpus)} GPU(s)")

    async def shutdown(self) -> None:
        """
        Shutdown scheduler and cleanup resources.
        关闭调度器并清理资源。
        """
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            self._gpus.clear()
            self._active_tasks.clear()
            self._initialized = False
            logger.info("GPU scheduler shutdown complete")

    async def _detect_gpus(self) -> list[int]:
        """
        Auto-detect available CUDA GPUs.
        自动检测可用的 CUDA GPU。

        Returns:
            List of GPU indices / GPU 索引列表
        """
        try:
            import torch

            if torch.cuda.is_available():
                count = torch.cuda.device_count()
                logger.info(f"Detected {count} CUDA GPU(s)")
                return list(range(count))
        except ImportError:
            logger.debug("PyTorch not available, trying nvidia-smi")

        # Fallback to nvidia-smi
        # 回退到 nvidia-smi
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                indices = [int(line.strip()) for line in stdout.decode().strip().split("\n") if line.strip()]
                logger.info(f"Detected {len(indices)} GPU(s) via nvidia-smi")
                return indices
        except Exception as e:
            logger.debug(f"nvidia-smi detection failed: {e}")

        logger.warning("No GPUs detected")
        return []

    async def _register_gpu(self, config: GPUConfig) -> None:
        """
        Register a GPU device.
        注册一个 GPU 设备。

        Args:
            config: GPU configuration / GPU 配置
        """
        if config.index in self._gpus:
            logger.warning(f"GPU {config.index} already registered, updating config")

        state = GPUState(
            index=config.index,
            config=config,
            status=GPUStatus.AVAILABLE if config.enabled else GPUStatus.DISABLED,
        )

        # Get initial GPU stats (memory + utilization)
        # 获取初始 GPU 统计信息（内存 + 利用率）
        gpu_stats = await self._get_gpu_stats(config.index)
        if gpu_stats:
            state.memory_total_mb = gpu_stats["memory_total"]
            state.memory_used_mb = gpu_stats["memory_used"]
            state.gpu_util_percent = gpu_stats["gpu_util"]

            # Check if GPU is overloaded based on memory OR utilization threshold
            # 根据内存或利用率阈值检查 GPU 是否过载
            is_memory_overloaded = state.memory_percent >= self.config.memory_threshold_percent
            is_util_overloaded = state.gpu_util_percent >= self.config.gpu_util_threshold_percent

            if is_memory_overloaded or is_util_overloaded:
                state.status = GPUStatus.OVERLOADED
                reasons = []
                if is_memory_overloaded:
                    reasons.append(f"memory {state.memory_percent:.1f}% >= {self.config.memory_threshold_percent}%")
                if is_util_overloaded:
                    reasons.append(f"GPU-util {state.gpu_util_percent:.1f}% >= {self.config.gpu_util_threshold_percent}%")
                logger.warning(f"GPU {config.index} is overloaded: {', '.join(reasons)}")

        self._gpus[config.index] = state
        logger.debug(
            f"Registered GPU {config.index}: {state.memory_total_mb:.0f}MB total, "
            f"{state.memory_used_mb:.0f}MB used ({state.memory_percent:.1f}%), "
            f"GPU-util={state.gpu_util_percent:.1f}%, status={state.status.value}"
        )

    def register_gpu(self, index: int, max_concurrent_tasks: int = 2, enabled: bool = True) -> None:
        """
        Synchronously register a GPU (for use before event loop).
        同步注册 GPU（用于事件循环之前）。

        Args:
            index: GPU device index / GPU 设备索引
            max_concurrent_tasks: Max concurrent tasks / 最大并发任务数
            enabled: Whether GPU is enabled / 是否启用 GPU
        """
        config = GPUConfig(
            index=index,
            max_concurrent_tasks=max_concurrent_tasks,
            enabled=enabled,
        )
        state = GPUState(
            index=index,
            config=config,
            status=GPUStatus.AVAILABLE if enabled else GPUStatus.DISABLED,
        )
        self._gpus[index] = state
        logger.debug(f"Synchronously registered GPU {index}")

    async def _get_gpu_stats(self, gpu_index: int) -> Optional[dict[str, float]]:
        """
        Get GPU stats (memory AND utilization) using nvidia-smi.
        使用 nvidia-smi 获取 GPU 统计信息（内存和利用率）。

        Args:
            gpu_index: GPU device index / GPU 设备索引

        Returns:
            Dict with memory and utilization stats, or None if unavailable
            包含内存和利用率统计信息的字典，不可用时返回 None

        Note:
            We use nvidia-smi instead of torch.cuda.memory_allocated() because
            the latter only shows memory allocated by the current Python process,
            not total GPU memory usage from all processes.
            我们使用 nvidia-smi 而不是 torch.cuda.memory_allocated()，因为
            后者只显示当前 Python 进程分配的内存，而不是所有进程的总 GPU 内存使用量。
        """
        # Use nvidia-smi for actual system-wide GPU stats
        # 使用 nvidia-smi 获取实际的系统范围 GPU 统计信息
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                f"--id={gpu_index}",
                "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                parts = stdout.decode().strip().split(",")
                if len(parts) >= 3:
                    result = {
                        "memory_total": float(parts[0].strip()),
                        "memory_used": float(parts[1].strip()),
                        "memory_free": float(parts[2].strip()),
                        "gpu_util": float(parts[3].strip()) if len(parts) >= 4 else 0.0,
                    }
                    return result
        except Exception as e:
            logger.debug(f"nvidia-smi failed for GPU {gpu_index}: {e}")

        # Fallback to PyTorch for total memory only
        # 回退到 PyTorch 只获取总内存
        try:
            import torch

            if torch.cuda.is_available() and gpu_index < torch.cuda.device_count():
                props = torch.cuda.get_device_properties(gpu_index)
                total = props.total_memory / (1024 * 1024)
                return {
                    "memory_total": total,
                    "memory_used": 0.0,
                    "memory_free": total,
                    "gpu_util": 0.0,
                }
        except (ImportError, RuntimeError) as e:
            logger.debug(f"PyTorch fallback failed for GPU {gpu_index}: {e}")

        return None

    async def _health_check_loop(self) -> None:
        """
        Background task for periodic GPU health checks.
        用于定期 GPU 健康检查的后台任务。
        """
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._update_gpu_status()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _update_gpu_status(self) -> None:
        """
        Update status, memory, and utilization for all GPUs.
        更新所有 GPU 的状态、内存和利用率。
        """
        async with self._lock:
            for gpu_index, state in self._gpus.items():
                if not state.config.enabled:
                    state.status = GPUStatus.DISABLED
                    continue

                # Update GPU stats (memory + utilization)
                # 更新 GPU 统计信息（内存 + 利用率）
                gpu_stats = await self._get_gpu_stats(gpu_index)
                if gpu_stats:
                    state.memory_used_mb = gpu_stats["memory_used"]
                    state.memory_total_mb = gpu_stats["memory_total"]
                    state.gpu_util_percent = gpu_stats["gpu_util"]

                # Determine status based on load, memory, and utilization
                # 根据负载、内存和利用率确定状态
                is_memory_overloaded = state.memory_percent >= self.config.memory_threshold_percent
                is_util_overloaded = state.gpu_util_percent >= self.config.gpu_util_threshold_percent

                if is_memory_overloaded or is_util_overloaded:
                    state.status = GPUStatus.OVERLOADED
                elif state.active_tasks >= state.config.max_concurrent_tasks:
                    state.status = GPUStatus.BUSY
                else:
                    state.status = GPUStatus.AVAILABLE

                state.last_health_check = time.time()

    async def acquire_gpu(self, task_id: Optional[str] = None) -> int:
        """
        Acquire a GPU for task execution.
        获取一个 GPU 用于任务执行。

        Args:
            task_id: Optional task identifier / 可选的任务标识符

        Returns:
            GPU index assigned to the task / 分配给任务的 GPU 索引

        Raises:
            RuntimeError: If no GPUs available / 如果没有可用的 GPU
        """
        if not self._initialized:
            await self.initialize()

        if not self._gpus:
            raise RuntimeError("No GPUs registered")

        # Generate task ID if not provided
        # 如果未提供，生成任务 ID
        if task_id is None:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}_{time.time():.0f}"

        # Select GPU based on strategy
        # 根据策略选择 GPU
        gpu_index = await self._select_gpu()

        async with self._lock:
            state = self._gpus[gpu_index]

            # Wait for semaphore (blocks if at capacity)
            # 等待信号量（如果已满则阻塞）
            if state.semaphore:
                await state.semaphore.acquire()

            state.active_tasks += 1
            if state.active_tasks >= state.config.max_concurrent_tasks:
                state.status = GPUStatus.BUSY

            # Track task
            # 跟踪任务
            task_info = TaskInfo(
                task_id=task_id,
                gpu_index=gpu_index,
                started_at=time.time(),
            )
            self._active_tasks[task_id] = task_info

            # Track last used GPU for next selection
            # 跟踪上次使用的 GPU 以供下次选择
            self._last_used_gpu = gpu_index
            self._gpu_usage_queue.append(gpu_index)
            # Keep only last N entries (e.g., last 10)
            # 只保留最后 N 条记录（例如，最后 10 条）
            if len(self._gpu_usage_queue) > 10:
                self._gpu_usage_queue.pop(0)

        logger.debug(f"Acquired GPU {gpu_index} for task {task_id} (last_used: {self._last_used_gpu})")
        return gpu_index

    async def _select_gpu(self) -> int:
        """
        Select best GPU based on scheduling strategy.
        根据调度策略选择最佳 GPU。

        Selection rules / 选择规则:
        1. Avoid the previously used GPU (if possible) / 尽量避免使用之前使用的 GPU
        2. Prefer GPUs not overloaded (memory% AND GPU-util%) / 优先选择未过载的 GPU
        3. Apply scheduling strategy / 应用调度策略

        Returns:
            Selected GPU index / 选择的 GPU 索引
        """
        available_gpus = [
            (idx, state)
            for idx, state in self._gpus.items()
            if state.is_available
        ]

        if not available_gpus:
            # Wait for any GPU to become available
            # 等待任意 GPU 可用
            logger.debug("No GPU immediately available, waiting...")
            while True:
                await asyncio.sleep(0.1)
                # Refresh status before checking
                # 在检查之前刷新状态
                await self._update_gpu_status()
                available_gpus = [
                    (idx, state)
                    for idx, state in self._gpus.items()
                    if state.is_available
                ]
                if available_gpus:
                    break

        # Rule 1: Prefer GPUs NOT used in the previous task
        # 规则 1：优先选择上一个任务未使用的 GPU
        if self._last_used_gpu is not None and len(available_gpus) > 1:
            non_recent_gpus = [
                (idx, state) for idx, state in available_gpus
                if idx != self._last_used_gpu
            ]
            if non_recent_gpus:
                available_gpus = non_recent_gpus
                logger.debug(
                    f"Avoiding last used GPU {self._last_used_gpu}, "
                    f"{len(available_gpus)} alternatives available"
                )

        # Rule 2: Sort by combined score (lower is better)
        # 规则 2：按综合评分排序（越低越好）
        # Score = memory% * 0.5 + gpu_util% * 0.5 + load * 10
        # 评分 = 内存% * 0.5 + GPU利用率% * 0.5 + 负载 * 10
        def gpu_score(item: tuple[int, GPUState]) -> float:
            _, state = item
            return (
                state.memory_percent * 0.5 +
                state.gpu_util_percent * 0.5 +
                state.load * 10
            )

        if self.config.scheduling_strategy == "round_robin":
            # Round-robin but still avoid last used GPU
            # 轮询但仍然避免使用上一个 GPU
            indices = [idx for idx, _ in available_gpus]
            selected = indices[self._round_robin_index % len(indices)]
            self._round_robin_index += 1
            return selected

        elif self.config.scheduling_strategy == "memory_aware":
            # Select GPU with most free memory
            # 选择剩余内存最多的 GPU
            available_gpus.sort(key=lambda x: x[1].memory_percent)
            return available_gpus[0][0]

        else:  # least_loaded (default) - use combined score
            # Select GPU with lowest combined score
            # 选择综合评分最低的 GPU
            available_gpus.sort(key=gpu_score)
            return available_gpus[0][0]

    def release_gpu(self, gpu_index: int, task_id: Optional[str] = None, error: Optional[str] = None) -> None:
        """
        Release a GPU after task completion.
        任务完成后释放 GPU。

        Args:
            gpu_index: GPU index to release / 要释放的 GPU 索引
            task_id: Optional task identifier / 可选的任务标识符
            error: Optional error message if task failed / 如果任务失败的可选错误消息
        """
        if gpu_index not in self._gpus:
            logger.warning(f"Attempted to release unregistered GPU {gpu_index}")
            return

        state = self._gpus[gpu_index]

        # Update state
        # 更新状态
        state.active_tasks = max(0, state.active_tasks - 1)
        if error:
            state.total_tasks_failed += 1
        else:
            state.total_tasks_completed += 1

        # Release semaphore
        # 释放信号量
        if state.semaphore:
            state.semaphore.release()

        # Update status
        # 更新状态
        if state.config.enabled and state.status == GPUStatus.BUSY:
            state.status = GPUStatus.AVAILABLE

        # Remove from active tasks
        # 从活动任务中移除
        if task_id and task_id in self._active_tasks:
            task_info = self._active_tasks.pop(task_id)
            task_info.completed_at = time.time()
            task_info.error = error

        logger.debug(f"Released GPU {gpu_index}" + (f" (error: {error})" if error else ""))

    async def run_on_gpu(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        task_id: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        """
        Run an async function on an available GPU.
        在可用的 GPU 上运行异步函数。

        Args:
            func: Async function to run / 要运行的异步函数
            *args: Positional arguments / 位置参数
            task_id: Optional task identifier / 可选的任务标识符
            **kwargs: Keyword arguments (gpu_index will be injected) / 关键字参数（gpu_index 将被注入）

        Returns:
            Function result / 函数结果

        Example / 示例:
            >>> async def score_sequence(sequence: str, gpu_index: int) -> float:
            ...     # Use gpu_index for CUDA device
            ...     return 0.95
            >>> result = await scheduler.run_on_gpu(score_sequence, "QVQLV...")
        """
        gpu_index = await self.acquire_gpu(task_id)
        error: Optional[str] = None
        try:
            # Inject gpu_index into kwargs
            # 将 gpu_index 注入 kwargs
            kwargs["gpu_index"] = gpu_index
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.task_timeout,
            )
        except asyncio.TimeoutError:
            error = f"Task timed out after {self.config.task_timeout}s"
            raise
        except Exception as e:
            error = str(e)
            raise
        finally:
            self.release_gpu(gpu_index, task_id, error)

    async def refresh_status(self) -> None:
        """
        Refresh GPU status and memory info (on-demand).
        刷新 GPU 状态和内存信息（按需）。
        """
        await self._update_gpu_status()

    def get_status(self) -> dict[str, Any]:
        """
        Get current scheduler status (cached, call refresh_status first for real-time).
        获取当前调度器状态（缓存，调用 refresh_status 获取实时数据）。

        Returns:
            Status dict with GPU states and queue info / 包含 GPU 状态和队列信息的状态字典
        """
        return {
            "enabled": self.config.enabled,
            "initialized": self._initialized,
            "total_gpus": len(self._gpus),
            "available_gpus": sum(1 for s in self._gpus.values() if s.is_available),
            "active_tasks": len(self._active_tasks),
            "queue_size": self._task_queue.qsize(),
            "last_used_gpu": self._last_used_gpu,
            "recent_gpu_usage": self._gpu_usage_queue[-5:] if self._gpu_usage_queue else [],
            "gpus": {
                str(idx): {
                    "status": state.status.value,
                    "active_tasks": state.active_tasks,
                    "queued_tasks": state.queued_tasks,
                    "load": round(state.load, 2),
                    "memory_used_mb": round(state.memory_used_mb, 1),
                    "memory_total_mb": round(state.memory_total_mb, 1),
                    "memory_percent": round(state.memory_percent, 1),
                    "gpu_util_percent": round(state.gpu_util_percent, 1),
                    "total_completed": state.total_tasks_completed,
                    "total_failed": state.total_tasks_failed,
                    "enabled": state.config.enabled,
                }
                for idx, state in self._gpus.items()
            },
        }

    def get_gpu_status(self, gpu_index: int) -> Optional[dict[str, Any]]:
        """
        Get status for a specific GPU.
        获取特定 GPU 的状态。

        Args:
            gpu_index: GPU device index / GPU 设备索引

        Returns:
            GPU status dict or None if not found / GPU 状态字典，如果未找到则返回 None
        """
        if gpu_index not in self._gpus:
            return None

        state = self._gpus[gpu_index]
        return {
            "index": gpu_index,
            "status": state.status.value,
            "active_tasks": state.active_tasks,
            "queued_tasks": state.queued_tasks,
            "max_concurrent_tasks": state.config.max_concurrent_tasks,
            "load": round(state.load, 2),
            "memory_used_mb": round(state.memory_used_mb, 1),
            "memory_total_mb": round(state.memory_total_mb, 1),
            "memory_percent": round(state.memory_percent, 1),
            "gpu_util_percent": round(state.gpu_util_percent, 1),
            "enabled": state.config.enabled,
        }

    def enable_gpu(self, gpu_index: int) -> bool:
        """
        Enable a GPU for scheduling.
        启用 GPU 进行调度。

        Args:
            gpu_index: GPU device index / GPU 设备索引

        Returns:
            True if GPU was enabled, False if not found / 如果 GPU 已启用返回 True，未找到返回 False
        """
        if gpu_index not in self._gpus:
            return False

        state = self._gpus[gpu_index]
        state.config.enabled = True
        state.status = GPUStatus.AVAILABLE
        logger.info(f"Enabled GPU {gpu_index}")
        return True

    def disable_gpu(self, gpu_index: int) -> bool:
        """
        Disable a GPU from scheduling.
        从调度中禁用 GPU。

        Args:
            gpu_index: GPU device index / GPU 设备索引

        Returns:
            True if GPU was disabled, False if not found / 如果 GPU 已禁用返回 True，未找到返回 False
        """
        if gpu_index not in self._gpus:
            return False

        state = self._gpus[gpu_index]
        state.config.enabled = False
        state.status = GPUStatus.DISABLED
        logger.info(f"Disabled GPU {gpu_index}")
        return True


# Global scheduler instance (lazy initialization)
# 全局调度器实例（延迟初始化）
_scheduler: Optional[GPUScheduler] = None


def get_gpu_scheduler(config: Optional[GPUSchedulerConfig] = None) -> GPUScheduler:
    """
    Get or create the global GPU scheduler instance.
    获取或创建全局 GPU 调度器实例。

    Args:
        config: Optional configuration (uses default if not provided) / 可选配置（未提供时使用默认值）

    Returns:
        GPUScheduler instance / GPUScheduler 实例
    """
    global _scheduler
    if _scheduler is None:
        if config is None:
            config = GPUSchedulerConfig()
        _scheduler = GPUScheduler(config)
    return _scheduler


async def reset_gpu_scheduler() -> None:
    """
    Reset the global GPU scheduler.
    重置全局 GPU 调度器。
    """
    global _scheduler
    if _scheduler is not None:
        await _scheduler.shutdown()
        _scheduler = None

