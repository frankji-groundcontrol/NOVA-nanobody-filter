# NOVA 纳米抗体挑战赛 - 提交过滤系统

使用 Python 实现的模块化纳米抗体挑战赛提交系统的实施计划。目标是构建一个干净、模块化的应用程序，能够良好扩展并保持逻辑分离。

## 相关文档

- [搜索快速上手](SEARCH_QUICKSTART.md) - 索引、提交任务、轮询结果的一页式指南
- [真实数据搜索复现](SEARCH_REAL_DATA_REPRO.md) - 用公开 VHH 数据复现端到端搜索测试
- [成对比对方案说明](PAIRWISE_ALIGNMENT_NOTES.md) - 当前后端与更快选项对比
- [English Search Quickstart](../en/SEARCH_QUICKSTART.md) - Search quickstart in English
- [排序说明（12.1）](#121-搜索能力概览) - 搜索结果并列时的稳定排序与截断规则
- [搜索性能基准测试](#12-搜索性能基准测试) - 真实数据上的 Tier 1 和 Tier 2 搜索基准测试结果
- [搜索架构](SEARCH_ARCHITECTURE.md) - 序列搜索原理、全部参数及纳米抗体重复检测调参指南

---

## **1. 功能**

### **1.1 多样性过滤器 - 创意强制**

* **目的：** 确保矿工提交的纳米抗体序列具有多样性，防止提交非常相似的序列。

#### **1.1.1 提交批次内的多样性**

| 参数 | 阈值 | 描述 |
|------|------|------|
| `global_cluster_identity` | >= 0.98 | MMseqs2 聚类以消除内部近似重复 |
| `cdrs_combined_mutations` | >= 2 | 所有 CDR 合计的最小突变数 |
| `cdr3_mutations` | >= 1 | CDR3 区域的最小突变数 |

* **核心操作：**
  * **MMseqs2 聚类：** 识别并移除全局相似度 >= 98% 的序列。
  * **突变检查：** 强制要求所有 CDR 合计至少有 2 个突变（`cdrs_combined_mutations >= 2`），CDR3 至少有 1 个突变（`cdr3_mutations >= 1`）。

#### **1.1.2 与历史提交的多样性**

* **K-mer 索引：** 为当前过滤后的序列构建 k-mer 索引（k=5 或 k=6）。

* **比较策略：**

  | 方案 | 策略 | 阈值 |
  |------|------|------|
  | **方案 A（基线）** | 针对所有历史提交进行加权 MinHash | Jaccard 相似度 < 0.9 |
  | **方案 B（首选）** | 仅与排行榜前 50 名序列比较 | `current_top_n = 50` |

  * **方案 B 原理：** 通过聚焦于表现最佳的序列来鼓励优化和创新。

* **比较后处理：** 合并匹配的命中结果，重新运行内部批次过滤器以强制执行重用后的新颖性。

---

### **1.2 天然性过滤器 - 纳米抗体有效性**

* **目的：** 确保提交的序列是有效的纳米抗体（VHH）并且可以正确人源化。

#### **1.2.1 评分阈值**

| 指标 | 阈值 | 工具 |
|------|------|------|
| IMGT 编号 | 成功编号 | abnumber |
| 天然性分数 | >= 0.80 | 基于 IgBLAST 的 VHH 天然性（内部） |
| 人源性分数 | >= 0.75 | 基于 IgBLAST 的人源框架（内部） |

* **核心操作：**
  * **abnumber：** 仅保留在 IMGT 方案下成功编号的序列。
  * **基于 IgBLAST 的评分（`metanano.utils.igblast_nativeness`）：** 
    * 天然性阈值：`nativeness_score >= 0.80`
    * 人源性阈值：`humanness_score >= 0.75`
  * **可选交叉检查：** 使用 [promb](https://github.com/MSDLLCpapers/promb)（OASis 分数）验证人源性以进行额外验证。

---

### **1.3 可开发性过滤器 - 治疗就绪性**

* **目的：** 确保序列作为治疗性纳米抗体是可行的。

* **应用顺序：** 在通过多样性和天然性过滤器后应用 TNP（治疗性纳米抗体分析器）。

#### **1.3.1 红区标准（2025年7月）**

如果触发以下任一红区标准，则**拒绝**序列：

| 属性 | 参数 | 有效范围 | 红区（触发拒绝） |
|------|------|----------|------------------|
| 总 CDR 长度 | L | 20 ≤ L ≤ 39 | L < 20 或 L > 39 |
| CDR3 长度 | L3 | 5 ≤ L3 ≤ 23 | L3 < 5 或 L3 > 23 |
| CDR3 紧凑度 | C | 0.56 ≤ C ≤ 1.61 | C < 0.56 或 C > 1.61 |
| 表面疏水性斑块 | PSH | 73.4 ≤ PSH ≤ 155.47 | PSH < 73.4 或 PSH > 155.47 |
| 正电荷斑块 | PPC | PPC ≤ 1.18 | PPC > 1.18 |
| 负电荷斑块 | PNC | PNC ≤ 1.88 | PNC > 1.88 |

* **核心操作：**
  * **TNP 分析：** 根据 CDR 长度、表面疏水性、电荷斑块和紧凑度评估序列的可开发性。
  * **属性验证：** 如果任何属性落入红区，序列将被**拒绝/丢弃**。
  * **通过条件：** 仅当所有属性都在有效范围内时，序列才通过。

---

### **1.4 序列验证流水线**

* **目的：** 整合所有检查并按正确顺序应用以实现高效验证。
* **核心操作：**
  * 按顺序串联过滤器：**多样性 → 天然性 → 可开发性**
  * 提前终止：如果任何过滤器失败则停止处理
  * 提供详细反馈并返回每次提交的验证状态

---

## **2. 文件结构**

### **根项目结构**

```
NOVA-nanobody-filter/
├── README.md                   # 项目概述（链接到文档）
├── LICENSE                     # 许可证文件
├── docs/                       # 文档
│   ├── en/
│   │   ├── README.md           # 英文文档
│   │   ├── TODO.md             # 英文任务清单
│   │   └── BUGS.md             # 英文问题跟踪
│   └── cn/
│       ├── README.md           # 中文文档
│       ├── TODO.md             # 中文任务清单
│       └── BUGS.md             # 中文问题跟踪
├── install/                    # 安装脚本和配置
│   ├── install.sh              # 主安装脚本
│   ├── environment.yml         # 完整 conda 环境
│   ├── environment-minimal.yml # 精简 conda 环境
│   ├── requirements.txt        # 完整 pip 依赖
│   └── requirements-minimal.txt # 精简 pip 依赖
└── metanano/                   # 主应用程序包
    ├── __init__.py             # 包初始化，导出 Config 和 ValidationPipeline
    ├── app.py                  # FastAPI 应用入口
    ├── config.py               # Pydantic 配置模型
    ├── pipeline.py             # 验证流水线编排器
    ├── filters/                # 过滤器实现（同步）
    │   ├── __init__.py
    │   ├── diversity.py        # 多样性过滤器（MMseqs2、k-mer、突变）
    │   ├── nativeness.py       # 天然性过滤器（abnumber、基于 IgBLAST 的天然性/人源性）
    │   └── developability.py   # 可开发性过滤器（TNP、红区）
    ├── services/               # 异步服务层（封装过滤器）
    │   ├── __init__.py
    │   ├── async_manager.py    # 集中式异步管理器（含信号量）
    │   ├── diversity_service.py    # 异步多样性操作
    │   ├── nativeness_service.py   # 异步天然性操作（GPU 感知）
    │   └── developability_service.py # 异步可开发性操作
    ├── validators/             # 验证器编排器
    │   ├── __init__.py
    │   ├── diversity_validator.py
    │   ├── nativeness_validator.py
    │   └── developability_validator.py
    ├── models/                 # Pydantic 数据模型
    │   ├── __init__.py
    │   ├── sequence.py         # 序列和批次模型
    │   └── validation_result.py # 响应模型
    ├── routes/                 # FastAPI 路由定义
    │   ├── __init__.py
    │   ├── submission_routes.py    # POST /submit
    │   ├── validation_routes.py    # POST /validate, /validate/batch
    │   ├── health_routes.py        # GET /health
    │   ├── diversity_routes.py     # POST /diversity/*
    │   ├── nativeness_routes.py    # POST /nativeness/*
    │   ├── developability_routes.py # POST /developability/*
    │   └── service_routes.py       # GET/POST /services/*
    ├── utils/                  # 工具函数
    │   ├── __init__.py
    │   ├── cdr_utils.py        # CDR 提取和突变计数 (abnumber)
    │   ├── kmer.py             # K-mer 生成和索引
    │   ├── similarity.py       # Jaccard、MinHash 相似度 (datasketch)
    │   ├── mmseqs2_wrapper.py  # MMseqs2 命令行封装
    │   ├── tnp_wrapper.py      # TNP 命令行封装
    │   └── gpu_scheduler.py    # 内存 GPU 任务调度器
    └── tests/                  # 测试套件
        ├── __init__.py
        ├── test_diversity.py
        ├── test_nativeness.py
        ├── test_developability.py
        ├── test_submission.py
        ├── test_validation.py
        ├── test_utils.py
        ├── tools/              # 外部工具集成测试（84 个测试）
        │   ├── __init__.py
        │   ├── conftest.py     # 共享固件和测试数据
        │   ├── test_tnp.py     # TNP 封装测试（12 个测试）
        │   ├── test_mmseqs2.py # MMseqs2 封装测试（11 个测试）
        │   ├── test_abnumber.py # abnumber/CDR 提取测试（15 个测试）
        │   ├── test_igblast_nativeness.py  # IgBLAST 天然性/人源性测试（12 个测试）
        │   ├── test_promb.py    # promb/OASis 人源性测试（16 个测试）
        │   └── test_datasketch.py # datasketch/MinHash 测试（18 个测试）
        └── routes/             # API 路由集成测试（58 个测试）
            ├── __init__.py
            ├── conftest.py     # 共享固件（base_url、序列、有效载荷）
            ├── test_health_routes.py      # 健康检查测试（4 个测试）
            ├── test_validation_routes.py  # 验证流水线测试（11 个测试）
            ├── test_service_routes.py     # 服务/GPU 状态测试（10 个测试）
            ├── test_diversity_routes.py   # 多样性服务测试（11 个测试）
            ├── test_nativeness_routes.py  # 天然性服务测试（11 个测试）
            └── test_developability_routes.py # 可开发性测试（11 个测试）
```

### **模块描述**

| 模块 | 用途 |
|------|------|
| `metanano/` | 包含所有过滤逻辑和 API 的主应用包 |
| `metanano/filters/` | 核心过滤逻辑（同步，多样性、天然性、可开发性） |
| `metanano/services/` | 异步服务层，封装过滤器并提供信号量和 GPU 调度 |
| `metanano/validators/` | 应用过滤器并生成结果的编排器 |
| `metanano/models/` | 请求、响应和验证的 Pydantic 模型 |
| `metanano/routes/` | HTTP 端点的 FastAPI 路由处理器 |
| `metanano/utils/` | 辅助函数（k-mer、相似度、CDR 提取、MMseqs2、TNP、GPU 调度器） |
| `metanano/tests/` | 单元测试和集成测试 |
| `metanano/tests/tools/` | 外部工具集成测试（共 84 个测试） |
| `metanano/tests/routes/` | API 路由集成测试（共 58 个测试） |

---

## **3. 路由（API 定义）**

### **3.1 /submit** (POST)

**目的：** 处理纳米抗体序列提交。

**输入：**

* `sequence` (str)：纳米抗体的氨基酸序列。
* `user_id` (str)：提交用户的 ID。

**输出：**

* `status` (str)："Success" 或 "Error"。
* `message` (str)：如果有错误，提供描述（例如，"序列与先前提交过于相似"）。

**实现：** `metanano/routes/submission_routes.py`

```python
@router.post("")
async def submit_sequence(submission: SequenceSubmission) -> SubmissionResponse:
    result = pipeline.validate(submission.sequence)
    
    if result.validation_status == "Failed":
        return SubmissionResponse(status="Error", message=f"验证失败: {result.failed_filters}")
    
    # 将有效序列保存到数据库
    return SubmissionResponse(status="Success", message="序列提交成功！")
```

### **3.2 /validate** (POST)

**目的：** 对纳米抗体序列进行过滤器验证。

**输入：**

* `sequence` (str)：要验证的纳米抗体序列。

**输出：**

* `validation_status` (str)：验证状态（例如，"Passed"、"Failed"）。
* `failed_filters` (list)：序列未通过的过滤器列表（例如，["Diversity", "Nativeness"]）。
* `details` (object)：每个过滤器的详细分数和指标。

**实现：** `metanano/routes/validation_routes.py`

```python
@router.post("")
async def validate_sequence(sequence_input: Sequence) -> ValidationResponse:
    result = pipeline.validate(sequence_input.sequence)
    return ValidationResponse(
        validation_status=result.validation_status,
        failed_filters=result.failed_filters,
        details=result.details,
    )
```

### **3.3 /health** (GET)

**目的：** 用于监控的健康检查端点。

**输出：**

* `status` (str)："healthy"
* `service` (str)："MetaNano"
* `message` (str)：状态消息

**实现：** `metanano/routes/health_routes.py`

### **3.4 /diversity/** (服务路由)

**目的：** 直接访问多样性过滤器操作。

| 端点 | 方法 | 描述 |
|------|------|------|
| `/diversity/analyze` | POST | 分析序列多样性 |
| `/diversity/batch-check` | POST | 通过 MMseqs2 检查批次多样性 |
| `/diversity/cdr-mutations` | POST | 检查 CDR 突变要求 |

**实现：** `metanano/routes/diversity_routes.py`

### **3.5 /nativeness/** (服务路由)

**目的：** 直接访问天然性过滤器操作。

| 端点 | 方法 | 描述 |
|------|------|------|
| `/nativeness/analyze` | POST | 完整天然性分析 |
| `/nativeness/imgt-number` | POST | 仅 IMGT 编号 |
| `/nativeness/scores` | POST | 计算天然性/人源性分数 |

**实现：** `metanano/routes/nativeness_routes.py`

### **3.6 /developability/** (服务路由)

**目的：** 直接访问可开发性过滤器操作。

| 端点 | 方法 | 描述 |
|------|------|------|
| `/developability/analyze` | POST | 完整可开发性分析 |
| `/developability/tnp-profile` | POST | 仅 TNP 分析 |
| `/developability/analyze-batch` | POST | 批量可开发性分析 |

**实现：** `metanano/routes/developability_routes.py`

### **3.7 /services/** (管理路由)

**目的：** 服务管理和 GPU 调度器控制。

| 端点 | 方法 | 描述 |
|------|------|------|
| `/services/status` | GET | 获取异步管理器和服务状态 |
| `/services/gpu` | GET | 获取 GPU 调度器状态（队列、利用率） |
| `/services/gpu/control` | POST | 动态启用/禁用 GPU |

**实现：** `metanano/routes/service_routes.py`

---

## **4. 验证工作流程**

### **4.1 验证步骤：**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        输入序列                                      │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  第1步：多样性过滤器                                                  │
│  ├── MMseqs2 聚类 (global_cluster_identity >= 0.98)                 │
│  ├── CDR 突变检查 (cdrs_combined >= 2, cdr3 >= 1)                   │
│  └── 历史比较 (方案 A 或 方案 B)                                      │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                          通过?   │
                     ┌───────────┴───────────┐
                     │ 否                    │ 是
                     ▼                       ▼
              ┌──────────────┐    ┌─────────────────────────────────────┐
              │ 拒绝         │    │  第2步：天然性过滤器                   │
              │ (多样性)      │    │  ├── abnumber IMGT 编号              │
              └──────────────┘    │  ├── 天然性分数 >= 0.80               │
                                  │  └── 人源性分数 >= 0.75               │
                                  └─────────────────────────────────────┘
                                                   │
                                            通过?   │
                                       ┌───────────┴───────────┐
                                       │ 否                    │ 是
                                       ▼                       ▼
                                ┌──────────────┐    ┌─────────────────────────────────────┐
                                │ 拒绝         │    │  第3步：可开发性过滤器                 │
                                │ (天然性)      │    │  ├── TNP 分析器                      │
                                └──────────────┘    │  └── 红区标准检查                     │
                                                    └─────────────────────────────────────┘
                                                                     │
                                                              通过?   │
                                                         ┌───────────┴───────────┐
                                                         │ 否                    │ 是
                                                         ▼                       ▼
                                                  ┌──────────────┐    ┌──────────────┐
                                                  │ 拒绝         │    │ 接受         │
                                                  │(可开发性)     │    │ 序列         │
                                                  └──────────────┘    └──────────────┘
```

1. **多样性验证：**
   * 检查序列在批次内的多样性（MMseqs2、CDR 突变）。
   * 然后使用加权 MinHash 与历史提交进行比较。
   * **方案 B（首选）：** 仅与排行榜前 50 名序列比较。
   * 如果任何步骤失败，验证停止并返回反馈。

2. **天然性验证：**
   * 使用 **abnumber** 工具在 IMGT 方案下对序列进行编号。
   * 使用 **基于 IgBLAST 的 VHH 天然性启发式方法** 计算天然性分数（阈值：>= 0.80）。
   * 使用 **基于 IgBLAST 的人源框架启发式方法** 计算人源性分数（阈值：>= 0.75）。
   * 可选：使用 **promb**（OASis 人源性分数）进行交叉检查。

3. **可开发性验证：**
   * 使用 **TNP**（治疗性纳米抗体分析器）检查序列。
   * 如果任何属性落入**红区**，序列将被**拒绝**。
   * 仅当所有属性都在有效范围内时，序列才通过此过滤器。

### **4.2 输出：**

* 如果序列通过所有过滤器，则标记为有效。
* 如果失败，反馈消息中将包含失败的具体过滤器以及实际分数/值。

---

## **5. 配置参数**

所有配置通过 `metanano/config.py` 中的 Pydantic 模型管理。

### **5.1 多样性过滤器配置**

```python
from metanano.config import Config

config = Config()

# 访问多样性设置
config.diversity.mmseqs2.global_cluster_identity  # 0.98
config.diversity.mutations.cdrs_combined_min      # 2
config.diversity.mutations.cdr3_min               # 1
config.diversity.kmer_index.k                     # 5
config.diversity.comparison.strategy              # "plan_b"
config.diversity.comparison.plan_b.current_top_n  # 50
```

### **5.2 天然性过滤器配置**

```python
config.nativeness.abnumber.scheme                    # "imgt"
config.nativeness.abnativ_v2.nativeness_threshold    # 0.80
config.nativeness.abnativ_v2.humanness_threshold     # 0.75
config.nativeness.promb.enabled                      # False
```

### **5.3 可开发性过滤器配置（红区 - 2025年7月）**

```python
config.developability.total_cdr_length.min           # 20
config.developability.total_cdr_length.max           # 39
config.developability.cdr3_length.min                # 5
config.developability.cdr3_length.max                # 23
config.developability.cdr3_compactness.min           # 0.56
config.developability.cdr3_compactness.max           # 1.61
config.developability.surface_hydrophobic_patches.min # 73.4
config.developability.surface_hydrophobic_patches.max # 155.47
config.developability.positive_charge_patches.threshold # 1.18
config.developability.negative_charge_patches.threshold # 1.88
```

### **5.4 异步并发配置**

```python
# 并发操作的信号量限制
config.async_config.max_concurrent_validations  # 10（整体流水线）
config.async_config.max_concurrent_tnp          # 4 （TNP CLI 调用）
config.async_config.max_concurrent_mmseqs2      # 2 （MMseqs2 聚类）
config.async_config.max_concurrent_abnativ      # 4 （基于 IgBLAST 的天然性评分）
config.async_config.max_concurrent_promb        # 4 （promb 人源性）

# 批处理设置
config.async_config.batch_size                  # 50（每批序列数）
config.async_config.task_timeout                # 300.0（秒）
config.async_config.queue_size                  # 1000（最大待处理任务数）
```

### **5.5 GPU 调度器配置**

```python
# GPU 调度器设置
config.gpu_scheduler.enabled                    # True
config.gpu_scheduler.auto_detect                # True（自动检测 GPU）
config.gpu_scheduler.scheduling_strategy        # "least_loaded"
config.gpu_scheduler.default_max_concurrent_per_gpu  # 2
config.gpu_scheduler.queue_max_size             # 500
config.gpu_scheduler.task_timeout               # 600.0（秒）
config.gpu_scheduler.health_check_interval      # 30.0（秒）
config.gpu_scheduler.memory_threshold_percent   # 85.0（达到则标记为过载）
config.gpu_scheduler.gpu_util_threshold_percent # 80.0（达到则标记为过载）

# 手动 GPU 注册（覆盖自动检测）
config.gpu_scheduler.gpus = [
    GPUConfig(index=0, max_concurrent_tasks=2, enabled=True),
    GPUConfig(index=1, max_concurrent_tasks=4, memory_limit_gb=8.0),
]
```

**过载阈值：**

| 阈值 | 默认值 | 描述 |
|------|--------|------|
| `memory_threshold_percent` | 85% | 内存% >= 阈值时标记为过载 |
| `gpu_util_threshold_percent` | 80% | GPU 利用率% >= 阈值时标记为过载 |

**调度策略：**

| 策略 | 描述 |
|------|------|
| `round_robin` | 按顺序轮询 GPU（避免使用上次的 GPU） |
| `least_loaded` | 选择综合评分最低的 GPU（内存% + 利用率% + 负载） |
| `memory_aware` | 选择可用内存最多的 GPU |

---

## **6. 示例**

### **6.1 序列提交：**

```bash
curl -X POST http://localhost:5000/submit \
-H "Content-Type: application/json" \
-d '{"sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS", "user_id": "12345"}'
```

**预期输出：**

```json
{
  "status": "Success",
  "message": "序列提交成功！"
}
```

### **6.2 序列验证：**

```bash
curl -X POST http://localhost:5000/validate \
-H "Content-Type: application/json" \
-d '{"sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS"}'
```

**预期输出（通过）：**

```json
{
  "validation_status": "Passed",
  "failed_filters": [],
  "details": {
    "diversity": {
      "passed": true,
      "global_cluster_identity": 0.85,
      "cdrs_combined_mutations": 3,
      "cdr3_mutations": 2,
      "jaccard_similarity": 0.72
    },
    "nativeness": {
      "passed": true,
      "imgt_numbered": true,
      "nativeness_score": 0.92,
      "humanness_score": 0.88
    },
    "developability": {
      "passed": true,
      "total_cdr_length": 28,
      "cdr3_length": 12,
      "cdr3_compactness": 1.05,
      "surface_hydrophobic_patches": 95.2,
      "positive_charge_patches": 0.85,
      "negative_charge_patches": 1.45
    }
  }
}
```

**预期输出（失败 - 可开发性红区）：**

```json
{
  "validation_status": "Failed",
  "failed_filters": ["Developability"],
  "details": {
    "diversity": {
      "passed": true
    },
    "nativeness": {
      "passed": true
    },
    "developability": {
      "passed": false,
      "total_cdr_length": 18,
      "cdr3_length": 4,
      "cdr3_compactness": 0.45,
      "surface_hydrophobic_patches": 70.2,
      "positive_charge_patches": 1.25,
      "negative_charge_patches": 1.95,
      "red_flags": [
        "total_cdr_length (18) outside valid range [20, 39] / 总CDR长度 (18) 超出有效范围 [20, 39]",
        "cdr3_length (4) outside valid range [5, 23] / CDR3长度 (4) 超出有效范围 [5, 23]",
        "positive_charge_patches (1.25) > threshold (1.18) / 正电荷斑块 (1.25) > 阈值 (1.18)",
        "negative_charge_patches (1.95) > threshold (1.88) / 负电荷斑块 (1.95) > 阈值 (1.88)"
      ],
      "reason": "总CDR长度超出有效范围; CDR3长度超出有效范围; 正电荷斑块超过阈值; 负电荷斑块超过阈值"
    }
  }
}
```

### **6.3 健康检查：**

```bash
curl http://localhost:5000/health
```

**预期输出：**

```json
{
  "status": "healthy",
  "service": "MetaNano",
  "message": "服务运行中。"
}
```

### **6.4 Python 使用：**

```python
from metanano import Config, ValidationPipeline

# 使用默认配置创建流水线
config = Config()
pipeline = ValidationPipeline(config)

# 验证序列
result = pipeline.validate("EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS")

print(f"状态: {result.validation_status}")
print(f"失败的过滤器: {result.failed_filters}")
print(f"详情: {result.details}")
```

---

## **7. 依赖**

| 包 | 用途 | 仓库 |
|----|------|------|
| `mmseqs2` | 多样性过滤器的序列聚类 | [GitHub](https://github.com/soedinglab/MMseqs2) |
| `abnumber` | 纳米抗体序列的 IMGT 编号 | [GitHub](https://github.com/prihoda/AbNumber) |
| `igblast`（随项目分发） | VHH 天然性与人源框架启发式评分后端 | [IgBLAST 文档](https://ncbi.github.io/igblast/) |
| `promb` | 可选的人源性交叉验证（OASis 分数） | [GitHub](https://github.com/MSDLLCpapers/promb) |
| `tnp` | 可开发性的治疗性纳米抗体分析器 | [GitHub](https://github.com/oxpig/TNP) |
| `datasketch` | 相似度计算的加权 MinHash | [GitHub](https://github.com/ekzhu/datasketch) |
| `fastapi` | API 端点的 Web 框架 | [GitHub](https://github.com/tiangolo/fastapi) |
| `pydantic` | 数据验证和设置管理 | [GitHub](https://github.com/pydantic/pydantic) |

---

## **8. 安装**

### **8.1 快速开始**

```bash
# 克隆仓库
git clone <repository-url>
cd NOVA-nanobody-filter

# 运行安装脚本（推荐）
chmod +x install/install.sh
./install/install.sh --minimal

# 激活环境
conda activate metanano

# 运行应用（从项目根目录）
python -m uvicorn metanano.app:app --reload --port 5000
```

**注意：** 请始终从项目根目录（`NOVA-nanobody-filter/`）运行服务器，而不是从 `metanano/` 目录内部运行。

### **8.2 运行测试**

```bash
# 激活环境
conda activate metanano

# 运行所有工具测试（84 个测试）
python -m pytest metanano/tests/tools/ -v

# 运行特定工具测试
python -m pytest metanano/tests/tools/test_tnp.py -v                 # TNP（12 个测试）
python -m pytest metanano/tests/tools/test_mmseqs2.py -v             # MMseqs2（11 个测试）
python -m pytest metanano/tests/tools/test_abnumber.py -v            # abnumber（15 个测试）
python -m pytest metanano/tests/tools/test_igblast_nativeness.py -v  # IgBLAST 天然性（12 个测试）
python -m pytest metanano/tests/tools/test_promb.py -v               # promb（16 个测试）
python -m pytest metanano/tests/tools/test_datasketch.py -v          # datasketch（18 个测试）
```

### **8.3 运行路由测试**

路由测试需要运行中的服务器。请先启动服务器，然后运行测试：

```bash
# 终端 1：启动服务器
conda activate metanano
python -m uvicorn metanano.app:app --host 0.0.0.0 --port 5000

# 终端 2：运行路由测试（58 个测试）
conda activate metanano
python -m pytest metanano/tests/routes/ -v

# 运行特定路由测试
python -m pytest metanano/tests/routes/test_health_routes.py -v       # 健康检查（4 个测试）
python -m pytest metanano/tests/routes/test_validation_routes.py -v   # 验证（11 个测试）
python -m pytest metanano/tests/routes/test_service_routes.py -v      # 服务/GPU（10 个测试）
python -m pytest metanano/tests/routes/test_diversity_routes.py -v    # 多样性（11 个测试）
python -m pytest metanano/tests/routes/test_nativeness_routes.py -v   # 天然性（11 个测试）
python -m pytest metanano/tests/routes/test_developability_routes.py -v # 可开发性（11 个测试）
```

**注意：** 如果服务器未运行，路由测试会自动跳过。

| 测试类别 | 测试数 | 描述 |
|----------|--------|------|
| 健康检查 | 4 | 健康检查端点验证 |
| 验证 | 11 | 单个和批量验证流水线 |
| 服务/GPU | 10 | 异步管理器和 GPU 调度器状态/控制 |
| 多样性 | 11 | 多样性分析、批次检查、CDR 突变 |
| 天然性 | 11 | 天然性分析、IMGT 编号、分数 |
| 可开发性 | 11 | 可开发性分析、TNP 分析、批量 |
| **总计** | **58** | 全部路由测试 |

### **8.4 Docker（即将推出）**

```bash
docker-compose up -d
```

---

## **9. 外部工具集成**

所有外部工具均已通过 Python 封装器集成，并包含全面的测试。

### **9.1 测试汇总**

| 类别 | 测试数 | 位置 | 用途 |
|------|--------|------|------|
| **工具测试** | 84 | `tests/tools/` | 外部工具集成 |
| **路由测试** | 58 | `tests/routes/` | API 端点集成 |
| **总计** | **142** | | 全部测试通过 |

### **9.2 工具测试详情**

| 工具 | 测试数 | 封装器/模块 | 用途 |
|------|--------|-------------|------|
| **TNP** | 12 | `utils/tnp_wrapper.py` | 可开发性分析（CLI 封装） |
| **MMseqs2** | 11 | `utils/mmseqs2_wrapper.py` | 序列聚类（CLI 封装） |
| **abnumber** | 15 | `utils/cdr_utils.py` | IMGT 编号和 CDR 提取 |
| **IgBLAST 天然性** | 12 | `utils/igblast_nativeness.py` | 天然性/人源性评分后端 |
| **promb** | 16 | `filters/nativeness.py` | OASis 人源性评分 |
| **datasketch** | 18 | `utils/similarity.py` | 加权 MinHash 相似度 |
| **总计** | **84** | | 全部工具测试通过 |

### **9.3 工具可用性检查**

系统可以优雅地处理缺失的工具：

```python
from metanano.utils import TNPWrapper, MMseqs2Wrapper

# 检查 TNP 是否可用
tnp = TNPWrapper()
if tnp.is_available():
    result = tnp.profile_nanobody(sequence)

# 检查 MMseqs2 是否可用
mmseqs2 = MMseqs2Wrapper()
if mmseqs2.is_available():
    clusters = mmseqs2.cluster(sequences)
```

---

## **10. 参考**

* NOVA 纳米抗体挑战赛提交过滤器规范（2025年7月）

### **10.1 工具仓库**

| 工具 | 描述 | 仓库 |
|------|------|------|
| **MMseqs2** | 超快速序列聚类和搜索 | [GitHub](https://github.com/soedinglab/MMseqs2) |
| **AbNumber** | 使用 IMGT、Chothia、Kabat 方案的抗体编号 | [GitHub](https://github.com/prihoda/AbNumber) |
| **IgBLAST** | 免疫球蛋白 V(D)J 比对与注释引擎 | [IgBLAST 文档](https://ncbi.github.io/igblast/) |
| **BioPhi** | 抗体设计和人源化平台 | [GitHub](https://github.com/Merck/BioPhi) |
| **promb** | 蛋白质人源性评估工具包（OASis 继任者） | [GitHub](https://github.com/MSDLLCpapers/promb) |
| **TNP** | 可开发性的治疗性纳米抗体分析器 | [GitHub](https://github.com/oxpig/TNP) |

### **10.2 工具详情**

* **MMseqs2** - 多对多序列搜索
  * 超快速和敏感的蛋白质序列聚类
  * 用于具有相似度阈值的多样性过滤

* **AbNumber** - 抗体编号工具
  * 支持 IMGT、Chothia、Kabat 和其他编号方案
  * 验证纳米抗体序列结构

* **IgBLAST** - 免疫球蛋白 V(D)J 比对与注释
  * 为 VHH 序列提供 IMGT 对齐的 FR/CDR 区域
  * 作为基于 IgBLAST 的 VHH 天然性与人源框架启发式评分的后端

* **BioPhi** - 抗体设计平台
  * 全面的人源化和设计工具
  * OASis 人源性指标（现已被 promb 取代）

* **promb** - 蛋白质突变负担工具包
  * BioPhi 的 OASis 人源性指标的继任者
  * 基于与参考蛋白质组中最近肽段的平均突变计算人源性
  * 支持 Human OAS、Human SwissProt 和自定义参考数据库

* **TNP** - 治疗性纳米抗体分析器
  * 评估治疗候选物的可开发性属性
  * 分析 CDR 长度、表面斑块和电荷分布

---

## **11. 异步架构**

系统使用分层异步架构实现高吞吐量处理。

### **11.1 架构概述**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI 路由 (async)                          │
│  /validate, /diversity/*, /nativeness/*, /developability/*          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         服务层 (async)                               │
│  DiversityService, NativenessService, DevelopabilityService          │
│  └── 使用 asyncio.to_thread() 运行同步过滤器                          │
│  └── 为每种资源类型提供信号量控制                                      │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AsyncManager (单例)                             │
│  ├── 信号量：validation, tnp, mmseqs2, abnativ, promb               │
│  └── GPUScheduler：任务队列、负载均衡、健康检查                         │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         过滤器层（同步）                              │
│  DiversityFilter, NativenessFilter, DevelopabilityFilter             │
│  └── 纯计算，无异步感知                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### **11.2 基于信号量的并发控制**

每个资源密集型操作都有专用的信号量：

| 信号量 | 默认限制 | 控制对象 |
|--------|----------|----------|
| `validation_semaphore` | 10 | 整体流水线并发 |
| `tnp_semaphore` | 4 | TNP CLI 子进程调用 |
| `mmseqs2_semaphore` | 2 | MMseqs2 聚类（I/O 密集） |
| `abnativ_semaphore` | 4 | 基于 IgBLAST 的天然性评分任务 |
| `promb_semaphore` | 4 | promb 人源性评分 |

### **11.3 GPU 调度器**

对于 GPU 密集型任务（例如未来版本中的深度学习评分），GPU 调度器提供：

* **智能 GPU 选择：**
  * 避免重复使用上一个 GPU（用于负载分配）
  * 跟踪最近的 GPU 使用历史
  * 基于综合评分选择：`内存% * 0.5 + GPU利用率% * 0.5 + 负载 * 10`

* **实时监控：**
  * 内存使用（通过 nvidia-smi，系统范围）
  * GPU 利用率百分比
  * 每个 GPU 的活动任务数

* **过载检测：**
  * 如果内存% >= 85% 或 GPU利用率% >= 80%，GPU 标记为 `overloaded`
  * 过载的 GPU 被排除在任务分配之外

* **动态控制：** 通过 API 在运行时启用/禁用 GPU

**GPU 状态响应：**
```json
{
  "enabled": true,
  "available_gpus": 1,
  "last_used_gpu": 0,
  "recent_gpu_usage": [0, 0, 0],
  "gpus": {
    "0": {
      "status": "available",
      "memory_percent": 2.6,
      "gpu_util_percent": 0.0,
      "active_tasks": 0
    }
  }
}
```

```python
# 示例：运行 GPU 密集型任务
result = await gpu_scheduler.run_on_gpu(some_gpu_bound_function, sequence)
# gpu_index 会自动注入到函数中
```

### **11.4 Python 使用（异步）**

```python
import asyncio
from metanano.services import AsyncManager, DiversityService, NativenessService
from metanano.config import Config

async def main():
    config = Config()
    manager = AsyncManager(config.async_config, config.gpu_scheduler)
    await manager.initialize()
    
    diversity_svc = DiversityService(config.diversity, manager)
    nativeness_svc = NativenessService(config.nativeness, manager)
    
    # 异步验证
    result = await diversity_svc.analyze_async(sequence)
    scores = await nativeness_svc.compute_scores_async(sequence)
    
    await manager.shutdown()

asyncio.run(main())
```

---

## **12. 序列搜索使用指南**

本项目已新增异步序列搜索子系统，用于在内存索引中快速查找相似纳米抗体序列。

### **12.1 搜索能力概览**

- **两阶段粗过滤**：共享 k-mer 数量 + Jaccard 阈值筛选候选。
- **精细比对**：优先使用 `parasail`（SIMD 加速），不可用时回退到 BioPython。
- **异步任务模型**：提交搜索请求立即返回 `job_id`，通过轮询查询状态与结果。
- **内存索引**：支持通过 API 动态索引序列（v1 不落盘）。
- **确定性排序**：最终结果按 `identity` 降序排序；`identity` 相同按 `target_id` 升序稳定打破并列。
- **粗过滤并列处理**：Jaccard 相同的候选按索引目标序列 ID（`target_id`）升序确定顺序，再执行 `max_candidates` 截断。

### **12.2 搜索模块架构**

1. `IndexManager`：维护序列记录和 k-mer 倒排索引。
2. `SearchEngine`：编排粗过滤、精细比对、CDR 相似度计算。
3. `JobManager`：管理任务状态（`pending/running/completed/failed`）和 TTL 清理。
4. `SearchService`：异步提交与并发控制（`asyncio.Semaphore`）。
5. `search_routes`：提供 `/search/*` REST API。

### **12.3 搜索 API 路由**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/search` | POST | 提交异步搜索任务（返回 `job_id`，HTTP 202） |
| `/search/{job_id}` | GET | 获取任务状态与结果 |
| `/search/index` | POST | 向搜索索引添加序列（HTTP 201） |
| `/search/index/stats` | GET | 获取当前索引序列数量 |

### **12.4 快速调用示例（curl）**

1）索引参考序列：

```bash
curl -X POST http://localhost:5000/search/index \
  -H "Content-Type: application/json" \
  -d '{
    "id": "db_001",
    "sequence": "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
  }'
```

2）提交搜索任务：

```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{
    "sequences": [
      "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDLGWSFDYWGQGTLVTVSS"
    ],
    "include_alignment": true,
    "coarse_min_shared": 3,
    "coarse_jaccard": 0.3
  }'
```

预期返回：

```json
{
  "job_id": "<uuid>"
}
```

3）轮询任务结果：

```bash
curl http://localhost:5000/search/<job_id>
```

### **12.5 Python 调用示例**

```python
import asyncio
from metanano.config import SearchConfig
from metanano.services.search_service import SearchService
from metanano.utils.kmer import generate_kmers


async def main() -> None:
    service = SearchService(SearchConfig())

    ref = "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
    service.index_sequence("db_001", ref, {"CDR3": "RDYRFDMGFDY"}, generate_kmers(ref, k=5))

    job_id = await service.submit_search([ref])
    while True:
        job = await service.get_job_status(job_id)
        if job and job.status.value in {"completed", "failed"}:
            print(job.status.value, job.result, job.error)
            break
        await asyncio.sleep(0.1)


asyncio.run(main())
```

### **12.6 输入校验规则**

- 序列会自动转换为大写并移除空白。
- 仅允许氨基酸字符：`ACDEFGHIKLMNPQRSTVWY`。
- 搜索/索引接口的序列长度范围：`10-500`。

### **12.7 运维与故障排查**

- `422 Unprocessable Entity`：通常为字符非法或长度越界。
- `/search/{job_id}` 返回 `404`：任务不存在或已过期。
- 结果返回较慢：可关闭 `include_alignment` 或提高粗过滤阈值。
- 索引为内存态：服务重启后索引会清空。

## **12. 搜索性能基准测试**

使用来自 [PLAbDab](https://opig.stats.ox.ac.uk/webapps/plabdab/)（专利和文献抗体数据库）的真实抗体序列对序列搜索子系统进行基准测试。

### **12.1 数据集**

| 来源 | 序列数 | 描述 |
|------|--------|------|
| PLAbDab 配对数据 | 58,405 | 配对抗体条目中的唯一有效重链 |
| PLAbDab 非配对数据 | 369,718 | 非配对条目中的唯一有效重链（chain=H） |
| **合计** | **221,692** | **去重后的重链（50–500 AA，仅标准氨基酸）** |

### **12.2 Tier 1：K-mer 粗过滤 + 比对**

默认配置：`k=5`、`min_shared_kmers=3`、`jaccard_threshold=0.3`、`max_candidates=500`。

| N（序列数） | 索引构建 | 峰值 RSS | P50 延迟 | P95 延迟 | P99 延迟 | QPS |
|------------|---------|---------|---------|---------|---------|-----|
| 10,000 | 3.2s | 39 MB | 57 ms | 448 ms | 470 ms | 6.7 |
| 50,000 | 12.8s | 147 MB | 274 ms | 553 ms | 644 ms | 3.4 |
| 100,000 | 23.2s | 248 MB | 471 ms | 686 ms | 797 ms | 2.3 |
| 221,692 | 45.9s | 493 MB | 780 ms | 1,415 ms | 1,577 ms | 1.3 |

**阈值门控（来自 `harness.py`）：**

| 规模 | RSS 上限 | P99 上限 | 状态 |
|------|---------|---------|------|
| 10,000 | < 200 MB | < 200 ms | RSS ✓，P99 — 见下方说明 |
| 100,000 | < 500 MB | < 500 ms | RSS ✓，P99 ✓ |

> **关于 10k P99 的说明：** 真实抗体数据上的 470ms P99 超出了合成数据的 200ms 门控。真实抗体序列的同源性远高于合成随机序列，每次查询产生更多粗过滤候选项，导致比对阶段更长。100k 门控（P99 < 500ms）顺利通过。

**观察结果：**

- 内存线性增长，约每 1,000 条序列 2.2 MB
- P99 延迟超线性增长 — 由大量候选通过 Jaccard 阈值后的比对阶段驱动
- 真实抗体序列呈簇状分布（进化家族），因此候选数量高于合成数据

### **12.3 Tier 2：MinHash LSH 近似检索**

配置：`num_perm=256`、`lsh_threshold=0.2`、`jaccard_threshold=0.3`、`max_candidates=500`。  
召回率计算方式：`|精确集 ∩ LSH 集| / |精确集|`，其中"精确集"为阈值合格集合（Jaccard ≥ 0.3）。

| N（序列数） | 索引构建 | 平均召回率 | 精确查询 | LSH 查询 | 加速比 |
|------------|---------|----------|---------|---------|-------|
| 10,000 | 26s | **0.967** | 13.5 ms | 3.9 ms | 3.5× |
| 50,000 | 107s | **0.898** | 77.5 ms | 14.1 ms | 5.5× |

**门控：** 召回率 ≥ 0.80 — 所有测试规模均 **通过**。

**观察结果：**

- 真实数据上 LSH 召回率在所有测试规模均超过 0.89
- 查询加速比随索引规模增长（10k 时 3.5× → 50k 时 5.5×）
- LSH 索引构建是瓶颈（每条序列串行计算 MinHash）
- 生产环境 200k+ 规模建议使用并行 MinHash 构建

### **12.4 测试套件**

所有搜索测试在真实和合成数据上均通过：

```
87 passed, 0 failed (pytest metanano/tests/search/)
```

### **12.5 复现基准测试**

1. 下载 PLAbDab 数据：

```bash
wget -O /tmp/plabdab_paired.csv.gz \
  "https://opig.stats.ox.ac.uk/webapps/plabdab/static/downloads/paired_data.csv.gz"
wget -O /tmp/plabdab_unpaired.csv.gz \
  "https://opig.stats.ox.ac.uk/webapps/plabdab/static/downloads/unpaired_data.csv.gz"
```

2. 运行搜索测试：

```bash
cd NOVA-nanobody-filter
pip install datasketch
python -m pytest metanano/tests/search/ -v
```

3. 参见 [SEARCH_REAL_DATA_REPRO.md](SEARCH_REAL_DATA_REPRO.md) 了解真实数据复现脚本。
