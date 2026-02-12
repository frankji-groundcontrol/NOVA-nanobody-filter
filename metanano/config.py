"""
References / 参考:
    - docs/en/README.md: Section 5 - Configuration Parameters
    - docs/cn/README.md: 第5节 - 配置参数

File / 文件:
    - metanano/config.py

Overview / 概述:
    Configuration management for the MetaNano validation pipeline.
    MetaNano 验证流水线的配置管理。

    Provides Pydantic models for type-safe configuration with sensible defaults
    matching the NOVA Nanobody Challenge specification (July 2025).
    提供 Pydantic 模型用于类型安全的配置，默认值符合 NOVA 纳米抗体挑战赛规范（2025年7月）。

Consumers / 调用方:
    - metanano/__init__.py
    - metanano/pipeline.py
    - metanano/filters/*.py
    - metanano/validators/*.py
"""

from pathlib import Path
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, Field, model_validator


class MMseqs2Config(BaseModel):
    """
    MMseqs2 clustering configuration.
    MMseqs2 聚类配置。

    Consumers / 调用方:
        - metanano/filters/diversity.py
        - metanano/utils/mmseqs2_wrapper.py
    """

    global_cluster_identity: float = Field(
        default=0.98,
        ge=0.0,
        le=1.0,
        description="Minimum sequence identity for clustering (0.98 = 98%). "
        "Sequences above this threshold are considered near-duplicates. / "
        "聚类的最小序列相似度（0.98 = 98%）。高于此阈值的序列被视为近似重复。",
    )
    threads: int = Field(
        default=4,
        ge=1,
        description="Number of threads for MMseqs2. / MMseqs2 使用的线程数。",
    )
    temp_dir: Optional[Path] = Field(
        default=None,
        description="Temporary directory for MMseqs2 databases. "
        "If None, uses system temp. / "
        "MMseqs2 数据库的临时目录。如果为 None，使用系统临时目录。",
    )


class MutationConfig(BaseModel):
    """
    CDR mutation thresholds configuration.
    CDR 突变阈值配置。

    Consumers / 调用方:
        - metanano/filters/diversity.py
        - metanano/utils/cdr_utils.py
    """

    cdrs_combined_min: int = Field(
        default=2,
        ge=0,
        description="Minimum total mutations across all CDRs combined. / "
        "所有 CDR 区域合计的最小突变数。",
    )
    cdr3_min: int = Field(
        default=1,
        ge=0,
        description="Minimum mutations required in CDR3 region. / "
        "CDR3 区域所需的最小突变数。",
    )


class KmerConfig(BaseModel):
    """
    K-mer indexing configuration.
    K-mer 索引配置。

    Consumers / 调用方:
        - metanano/utils/kmer.py
        - metanano/utils/similarity.py
    """

    k: int = Field(
        default=5,
        ge=3,
        le=10,
        description="K-mer length for sequence indexing (5 or 6 recommended). / "
        "序列索引的 k-mer 长度（推荐 5 或 6）。",
    )


class PlanAConfig(BaseModel):
    """
    Plan A comparison strategy (all historical submissions).
    方案 A 比较策略（所有历史提交）。

    Consumers / 调用方:
        - metanano/validators/diversity_validator.py
    """

    jaccard_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Maximum Jaccard similarity allowed (< 0.9 to pass). / "
        "允许的最大 Jaccard 相似度（< 0.9 通过）。",
    )


class PlanBConfig(BaseModel):
    """
    Plan B comparison strategy (top N leaderboard).
    方案 B 比较策略（排行榜前 N 名）。

    Consumers / 调用方:
        - metanano/validators/diversity_validator.py
    """

    current_top_n: int = Field(
        default=50,
        ge=1,
        description="Number of top leaderboard sequences to compare against. / "
        "用于比较的排行榜前 N 名序列数。",
    )


class ComparisonConfig(BaseModel):
    """
    Historical comparison strategy configuration.
    历史比较策略配置。

    Consumers / 调用方:
        - metanano/validators/diversity_validator.py
    """

    strategy: Literal["plan_a", "plan_b"] = Field(
        default="plan_b",
        description="Comparison strategy: 'plan_a' (all historical) or "
        "'plan_b' (top N leaderboard, preferred). / "
        "比较策略：'plan_a'（所有历史）或 'plan_b'（排行榜前N名，首选）。",
    )
    plan_a: PlanAConfig = Field(
        default_factory=PlanAConfig,
        description="Plan A configuration. / 方案 A 配置。",
    )
    plan_b: PlanBConfig = Field(
        default_factory=PlanBConfig,
        description="Plan B configuration. / 方案 B 配置。",
    )


class DiversityConfig(BaseModel):
    """
    Diversity filter configuration.
    多样性过滤器配置。

    Consumers / 调用方:
        - metanano/filters/diversity.py
        - metanano/validators/diversity_validator.py
    """

    mmseqs2: MMseqs2Config = Field(
        default_factory=MMseqs2Config,
        description="MMseqs2 clustering settings. / MMseqs2 聚类设置。",
    )
    mutations: MutationConfig = Field(
        default_factory=MutationConfig,
        description="CDR mutation thresholds. / CDR 突变阈值。",
    )
    kmer_index: KmerConfig = Field(
        default_factory=KmerConfig,
        description="K-mer indexing settings. / K-mer 索引设置。",
    )
    comparison: ComparisonConfig = Field(
        default_factory=ComparisonConfig,
        description="Historical comparison strategy. / 历史比较策略。",
    )


class AbnumberConfig(BaseModel):
    """
    AbNumber (IMGT numbering) configuration.
    AbNumber（IMGT 编号）配置。

    Consumers / 调用方:
        - metanano/filters/nativeness.py
    """

    scheme: Literal["imgt", "chothia", "kabat"] = Field(
        default="imgt",
        description="Numbering scheme to use (IMGT recommended for nanobodies). / "
        "使用的编号方案（纳米抗体推荐使用 IMGT）。",
    )


class AbnativConfig(BaseModel):
    """
    AbnatiV v2 scoring configuration.
    AbnatiV v2 评分配置。

    Consumers / 调用方:
        - metanano/filters/nativeness.py
    """

    nativeness_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum nativeness score to pass (>= 0.80). / "
        "通过所需的最小天然性分数（>= 0.80）。",
    )
    humanness_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum humanness score to pass (>= 0.75). / "
        "通过所需的最小人源性分数（>= 0.75）。",
    )


class PrombConfig(BaseModel):
    """
    promb (OASis humanness) configuration.
    promb（OASis 人源性）配置。

    Consumers / 调用方:
        - metanano/filters/nativeness.py
    """

    enabled: bool = Field(
        default=False,
        description="Enable promb cross-validation (optional). / "
        "启用 promb 交叉验证（可选）。",
    )
    db: Literal["human-oas", "human-swissprot", "human-reference"] = Field(
        default="human-oas",
        description="Reference database for humanness calculation. / "
        "用于人源性计算的参考数据库。",
    )
    peptide_length: int = Field(
        default=9,
        ge=5,
        le=15,
        description="Peptide length for humanness scoring. / "
        "人源性评分的肽段长度。",
    )


class NativenessConfig(BaseModel):
    """
    Nativeness filter configuration.
    天然性过滤器配置。

    Consumers / 调用方:
        - metanano/filters/nativeness.py
        - metanano/validators/nativeness_validator.py
    """

    abnumber: AbnumberConfig = Field(
        default_factory=AbnumberConfig,
        description="AbNumber IMGT numbering settings. / AbNumber IMGT 编号设置。",
    )
    abnativ_v2: AbnativConfig = Field(
        default_factory=AbnativConfig,
        description="AbnatiV v2 scoring settings. / AbnatiV v2 评分设置。",
    )
    promb: PrombConfig = Field(
        default_factory=PrombConfig,
        description="promb OASis settings (optional). / promb OASis 设置（可选）。",
    )


class RangeThreshold(BaseModel):
    """
    Range-based threshold for Red Region criteria (REJECT if outside range).
    红区标准的范围阈值（范围外则拒绝）。

    Defines the valid/acceptable range. Sequences with values OUTSIDE this
    range are REJECTED (fall into the Red Region).
    定义有效/可接受的范围。值在此范围之外的序列将被拒绝（落入红区）。

    Consumers / 调用方:
        - metanano/filters/developability.py
    """

    min: float = Field(
        description="Lower bound of valid range - values BELOW this trigger rejection. / "
        "有效范围下界 - 低于此值触发拒绝。"
    )
    max: float = Field(
        description="Upper bound of valid range - values ABOVE this trigger rejection. / "
        "有效范围上界 - 高于此值触发拒绝。"
    )


class SingleThreshold(BaseModel):
    """
    Single threshold for Red Region criteria (REJECT if above threshold).
    红区标准的单一阈值（高于阈值则拒绝）。

    Defines the maximum acceptable value. Sequences with values ABOVE this
    threshold are REJECTED (fall into the Red Region).
    定义最大可接受值。值高于此阈值的序列将被拒绝（落入红区）。

    Consumers / 调用方:
        - metanano/filters/developability.py
    """

    threshold: float = Field(
        description="Maximum acceptable value - values ABOVE this trigger rejection. / "
        "最大可接受值 - 高于此值触发拒绝。"
    )


class GPUConfig(BaseModel):
    """
    Single GPU device configuration.
    单个 GPU 设备配置。

    Consumers / 调用方:
        - metanano/utils/gpu_scheduler.py
    """

    index: int = Field(
        ge=0,
        description="GPU device index (CUDA_VISIBLE_DEVICES). / "
        "GPU 设备索引（CUDA_VISIBLE_DEVICES）。",
    )
    memory_limit_gb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Maximum GPU memory to use in GB (None = no limit). / "
        "最大使用 GPU 内存（GB）（None = 无限制）。",
    )
    max_concurrent_tasks: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Max concurrent tasks on this GPU. / "
        "此 GPU 上的最大并发任务数。",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this GPU is enabled for scheduling. / "
        "是否启用此 GPU 进行调度。",
    )


class GPUSchedulerConfig(BaseModel):
    """
    GPU scheduler configuration for managing GPU-bound tasks.
    用于管理 GPU 密集型任务的 GPU 调度器配置。

    Provides in-memory scheduling with:
    - Real-time GPU usage tracking
    - Queue-based task assignment
    - Multi-GPU load balancing
    提供内存调度功能：
    - 实时 GPU 使用跟踪
    - 基于队列的任务分配
    - 多 GPU 负载均衡

    Consumers / 调用方:
        - metanano/utils/gpu_scheduler.py
        - metanano/filters/nativeness.py
    """

    enabled: bool = Field(
        default=True,
        description="Enable GPU scheduling (False = CPU fallback). / "
        "启用 GPU 调度（False = 回退到 CPU）。",
    )
    auto_detect: bool = Field(
        default=True,
        description="Auto-detect available GPUs on startup. / "
        "启动时自动检测可用 GPU。",
    )
    gpus: list[GPUConfig] = Field(
        default_factory=list,
        description="Manually registered GPU devices (overrides auto_detect). / "
        "手动注册的 GPU 设备（覆盖自动检测）。",
    )
    default_max_concurrent_per_gpu: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Default max concurrent tasks per GPU (for auto-detected). / "
        "每个 GPU 的默认最大并发任务数（用于自动检测）。",
    )
    scheduling_strategy: Literal["round_robin", "least_loaded", "memory_aware"] = Field(
        default="least_loaded",
        description="GPU assignment strategy: 'round_robin', 'least_loaded', or 'memory_aware'. / "
        "GPU 分配策略：'round_robin'（轮询）、'least_loaded'（最少负载）或 'memory_aware'（内存感知）。",
    )
    queue_max_size: int = Field(
        default=500,
        ge=10,
        le=10000,
        description="Maximum pending tasks in GPU scheduler queue. / "
        "GPU 调度器队列中的最大待处理任务数。",
    )
    task_timeout: float = Field(
        default=600.0,
        ge=30.0,
        le=7200.0,
        description="Timeout for GPU tasks in seconds. / "
        "GPU 任务超时时间（秒）。",
    )
    health_check_interval: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Interval for GPU health/utilization checks in seconds. / "
        "GPU 健康/利用率检查间隔（秒）。",
    )
    memory_threshold_percent: float = Field(
        default=85.0,
        ge=50.0,
        le=100.0,
        description="GPU memory usage threshold (%) to pause new task assignment. / "
        "暂停新任务分配的 GPU 内存使用阈值（%）。",
    )
    gpu_util_threshold_percent: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="GPU utilization threshold (%) to pause new task assignment. / "
        "暂停新任务分配的 GPU 利用率阈值（%）。",
    )


class AsyncConfig(BaseModel):
    """
    Async concurrency configuration using semaphores.
    使用信号量的异步并发配置。

    Controls concurrent execution limits for various async operations
    to prevent resource exhaustion and ensure stable performance.
    控制各种异步操作的并发执行限制，以防止资源耗尽并确保稳定性能。

    Consumers / 调用方:
        - metanano/pipeline.py
        - metanano/filters/*.py
        - metanano/validators/*.py
        - metanano/utils/*.py
    """

    gpu_scheduler: GPUSchedulerConfig = Field(
        default_factory=GPUSchedulerConfig,
        description="GPU scheduler configuration for GPU-bound tasks. / "
        "GPU 密集型任务的 GPU 调度器配置。",
    )
    max_concurrent_validations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent sequence validations (semaphore limit). / "
        "最大并发序列验证数（信号量限制）。",
    )
    max_concurrent_tnp: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum concurrent TNP subprocess calls (CPU-bound). / "
        "最大并发 TNP 子进程调用数（CPU 密集型）。",
    )
    max_concurrent_mmseqs2: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Maximum concurrent MMseqs2 clustering jobs. / "
        "最大并发 MMseqs2 聚类任务数。",
    )
    max_concurrent_abnativ: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum concurrent AbnatiV scoring calls (GPU-aware). / "
        "最大并发 AbnatiV 评分调用数（GPU 感知）。",
    )
    max_concurrent_promb: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum concurrent promb humanness calculations. / "
        "最大并发 promb 人源性计算数。",
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Default batch size for async batch processing. / "
        "异步批处理的默认批次大小。",
    )
    task_timeout: float = Field(
        default=300.0,
        ge=10.0,
        le=3600.0,
        description="Timeout in seconds for individual async tasks. / "
        "单个异步任务的超时时间（秒）。",
    )
    queue_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum size of the async task queue. / "
        "异步任务队列的最大大小。",
    )


class CoarseFilterConfig(BaseModel):
    """
    Coarse filter configuration for sequence search.
    序列搜索的粗过滤配置。

    Consumers / 调用方:
        - metanano/search/coarse_filter.py (future)
    """

    min_shared_kmers: int = Field(
        default=3,
        ge=1,
        description="Minimum number of shared k-mers to consider sequences similar. / "
        "认为序列相似所需的最小共享 k-mer 数量。",
    )
    jaccard_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum Jaccard similarity threshold for coarse filtering. / "
        "粗过滤的最小 Jaccard 相似度阈值。",
    )
    max_candidates: int = Field(
        default=500,
        ge=1,
        description="Maximum number of coarse-filter candidates to keep. / "
        "粗过滤阶段保留的最大候选数量。",
    )
    retrieval_strategy: Literal["kmer_jaccard", "lsh"] = Field(
        default="kmer_jaccard",
        description="Candidate retrieval strategy used before alignment. / 对齐前的候选检索策略。",
    )


class LSHConfig(BaseModel):
    num_perm: int = Field(
        default=128,
        ge=16,
        description="Number of MinHash permutations. / MinHash 排列数。",
    )
    lsh_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="LSH similarity threshold for candidate retrieval. / 候选检索的 LSH 相似度阈值。",
    )
    weights: Tuple[float, float] = Field(
        default=(0.5, 0.5),
        description="LSH optimization weights (false_positive, false_negative). / LSH 优化权重。",
    )


class FineAlignmentConfig(BaseModel):
    """
    Fine alignment configuration for sequence search.
    序列搜索的精细对齐配置。

    Consumers / 调用方:
        - metanano/search/fine_alignment.py (future)
    """

    gap_open: int = Field(
        default=10,
        ge=0,
        description="Gap opening penalty for sequence alignment. / "
        "序列对齐的间隙开放惩罚。",
    )


class SearchConfig(BaseModel):
    """
    Sequence search configuration.
    序列搜索配置。

    Consumers / 调用方:
        - metanano/search/*.py (future)
    """

    coarse_filter: CoarseFilterConfig = Field(
        default_factory=CoarseFilterConfig,
        description="Coarse filter settings for fast candidate selection. / "
        "用于快速候选选择的粗过滤设置。",
    )
    fine_alignment: FineAlignmentConfig = Field(
        default_factory=FineAlignmentConfig,
        description="Fine alignment settings for precise similarity scoring. / "
        "用于精确相似度评分的精细对齐设置。",
    )
    k: int = Field(
        default=5,
        ge=1,
        description="K-mer length used by sequence search indexing and query generation. / "
        "序列搜索索引和查询生成使用的 k-mer 长度。",
    )
    job_ttl_seconds: float = Field(
        default=3600.0,
        ge=1.0,
        description="TTL in seconds for asynchronous search jobs. / 异步搜索任务的过期时间（秒）。",
    )
    max_concurrent_search: int = Field(
        default=4,
        ge=1,
        description="Maximum number of concurrent search jobs executed by SearchService. / "
        "SearchService 同时执行的最大搜索任务数。",
    )
    lsh: LSHConfig = Field(
        default_factory=LSHConfig,
        description="LSH-related configuration for approximate retrieval. / 近似检索的 LSH 配置。",
    )

    @model_validator(mode="after")
    def _validate_lsh_threshold(self) -> "SearchConfig":
        if self.lsh.lsh_threshold > self.coarse_filter.jaccard_threshold:
            raise ValueError("lsh.lsh_threshold must be <= coarse_filter.jaccard_threshold")
        return self


class DevelopabilityConfig(BaseModel):
    """
    Developability filter configuration (Red Region - July 2025).
    可开发性过滤器配置（红区 - 2025年7月）。

    Red Region criteria define REJECTION conditions. If ANY property falls outside
    the valid range (into the Red Region), the sequence is REJECTED/dumped.
    红区标准定义拒绝条件。如果任何属性落在有效范围之外（进入红区），序列将被拒绝/丢弃。

    Consumers / 调用方:
        - metanano/filters/developability.py
        - metanano/validators/developability_validator.py
    """

    total_cdr_length: RangeThreshold = Field(
        default_factory=lambda: RangeThreshold(min=20, max=39),
        description="Total CDR length valid range [20, 39]. REJECT if L < 20 OR L > 39. / "
        "总 CDR 长度有效范围 [20, 39]。L < 20 或 L > 39 时拒绝。",
    )
    cdr3_length: RangeThreshold = Field(
        default_factory=lambda: RangeThreshold(min=5, max=23),
        description="CDR3 length valid range [5, 23]. REJECT if L3 < 5 OR L3 > 23. / "
        "CDR3 长度有效范围 [5, 23]。L3 < 5 或 L3 > 23 时拒绝。",
    )
    cdr3_compactness: RangeThreshold = Field(
        default_factory=lambda: RangeThreshold(min=0.56, max=1.61),
        description="CDR3 compactness valid range [0.56, 1.61]. REJECT if C < 0.56 OR C > 1.61. / "
        "CDR3 紧凑度有效范围 [0.56, 1.61]。C < 0.56 或 C > 1.61 时拒绝。",
    )
    surface_hydrophobic_patches: RangeThreshold = Field(
        default_factory=lambda: RangeThreshold(min=73.4, max=155.47),
        description="Surface hydrophobic patches valid range [73.4, 155.47]. "
        "REJECT if PSH < 73.4 OR PSH > 155.47. / "
        "表面疏水性斑块有效范围 [73.4, 155.47]。PSH < 73.4 或 PSH > 155.47 时拒绝。",
    )
    positive_charge_patches: SingleThreshold = Field(
        default_factory=lambda: SingleThreshold(threshold=1.18),
        description="Positive charge patches max threshold 1.18. REJECT if PPC > 1.18. / "
        "正电荷斑块最大阈值 1.18。PPC > 1.18 时拒绝。",
    )
    negative_charge_patches: SingleThreshold = Field(
        default_factory=lambda: SingleThreshold(threshold=1.88),
        description="Negative charge patches max threshold 1.88. REJECT if PNC > 1.88. / "
        "负电荷斑块最大阈值 1.88。PNC > 1.88 时拒绝。",
    )


class Config(BaseModel):
    """
    Main configuration for the MetaNano validation pipeline.
    MetaNano 验证流水线的主配置。

    Example / 示例:
        >>> config = Config()
        >>> config.diversity.mmseqs2.global_cluster_identity
        0.98
        >>> config.nativeness.abnativ_v2.nativeness_threshold
        0.80

    Consumers / 调用方:
        - metanano/__init__.py
        - metanano/pipeline.py
        - app.py
    """

    async_config: AsyncConfig = Field(
        default_factory=AsyncConfig,
        description="Async concurrency configuration. / 异步并发配置。",
    )
    diversity: DiversityConfig = Field(
        default_factory=DiversityConfig,
        description="Diversity filter configuration. / 多样性过滤器配置。",
    )
    nativeness: NativenessConfig = Field(
        default_factory=NativenessConfig,
        description="Nativeness filter configuration. / 天然性过滤器配置。",
    )
    developability: DevelopabilityConfig = Field(
        default_factory=DevelopabilityConfig,
        description="Developability filter configuration. / 可开发性过滤器配置。",
    )
    search: SearchConfig = Field(
        default_factory=SearchConfig,
        description="Sequence search configuration. / 序列搜索配置。",
    )

    class Config:
        """Pydantic model configuration. / Pydantic 模型配置。"""

        # Allow extra fields for future extensibility
        # 允许额外字段以便未来扩展
        extra = "allow"
