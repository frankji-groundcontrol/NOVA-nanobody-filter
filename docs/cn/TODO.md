# NOVA 纳米抗体过滤器 - 任务清单

> 最后更新: 2025-12-17  
> 状态说明: ✅ 已完成 | 🚧 进行中 | ⏳ 待处理 | ❌ 阻塞

---

## 概述

本文档跟踪 NOVA 纳米抗体挑战赛提交过滤系统（MetaNano）的实施进度。该系统通过三个级联过滤器验证纳米抗体序列：多样性、天然性和可开发性。

---

## 工具集成工作流

对于每个外部工具，我们遵循系统化的三阶段方法：

1. **调研用法** - 阅读 GitHub/GitLab README，理解 CLI/API，记录输入/输出格式
2. **实现** - 根据发现的输入/输出模式实现钩子、控制器和路由
3. **测试** - 使用 curl 命令验证，与预期的 CLI 输出进行比较

---

## 0. 外部工具集成 🚧

### 0.1 TNP（治疗性纳米抗体分析器） ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 调研 | 阅读 TNP GitHub README | ✅ | [GitHub](https://github.com/oxpig/TNP) |
| 调研 | 记录 CLI 使用模式 | ✅ | `TNP --name <name> --output <dir> --seq <sequence>` |
| 调研 | 记录输出格式 | ✅ | JSON: `TNP_Results_SingleSeqEntry_<name>.json` |
| 调研 | 将输出字段映射到红区标准 | ✅ | L, L3, C, PSH, PPC, PNC, Flags |
| 实现 | 在 `utils/tnp_wrapper.py` 创建 TNP 封装 | ✅ | CLI 子进程封装，含 TNPResult 模型 |
| 实现 | 解析 JSON 输出到 Pydantic 模型 | ✅ | `TNPResult` 在 tnp_wrapper.py 中 |
| 实现 | 与可开发性过滤器集成 | ✅ | `developability.py` 使用 TNPWrapper |
| 测试 | 使用示例序列进行单元测试 | ✅ | Python 直接测试通过 |
| 测试 | Curl 测试 `/validate` 端点 | ✅ | API 服务器已测试（天然性阻断，但可开发性正常） |

**示例 CLI 命令：**
```bash
TNP --name my_sequence --output my_sequence_output --seq QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS
```

**示例输出：** `my_sequence_output/TNP_Results_SingleSeqEntry_my_sequence.json`
```json
{
  "my_sequence": {
    "name": "my_sequence",
    "Total CDR Length": 29,
    "CDR3 Length": 13,
    "CDR3 Compactness": 0.9288582368386492,
    "PSH": 88.7932,
    "PPC": 0.0505,
    "PNC": 0.3852,
    "Flags": {"L": "green", "L3": "green", "C": "green", "PSH": "green", "PPC": "green", "PNC": "green"}
  }
}
```

---

### 0.2 MMseqs2（序列聚类） ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 调研 | 阅读 MMseqs2 GitHub README | ✅ | [GitHub](https://github.com/soedinglab/MMseqs2) |
| 调研 | 记录聚类 CLI 用法 | ✅ | `mmseqs easy-cluster` 命令 |
| 调研 | 记录相似度阈值参数 | ✅ | `--min-seq-id 0.98` |
| 调研 | 记录输出格式（聚类 TSV） | ✅ | 代表序列和成员序列（TSV） |
| 实现 | 在 `utils/mmseqs2_wrapper.py` 创建 MMseqs2 封装 | ✅ | CLI 子进程封装 |
| 实现 | 解析聚类输出到 Python 字典 | ✅ | 聚类 ID → 成员序列 |
| 实现 | 与多样性过滤器集成 | ✅ | `diversity.py` 使用 MMseqs2Wrapper |
| 测试 | 使用示例批次进行单元测试 | ✅ | `test_mmseqs2.py` - 11 个测试通过 |
| 测试 | 使用批次 Curl 测试 `/validate` | ✅ | API 集成已验证 |

**预期 CLI 模式：**
```bash
mmseqs easy-cluster input.fasta output tmp --min-seq-id 0.98
```

---

### 0.3 abnumber（IMGT 编号） ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 调研 | 阅读 abnumber GitHub README | ✅ | [GitHub](https://github.com/prihoda/AbNumber) |
| 调研 | 记录 Python API 用法 | ✅ | `Chain` 类和 IMGT 方案 |
| 调研 | 记录 CDR 提取方法 | ✅ | `chain.cdr1_seq`, `chain.cdr2_seq`, `chain.cdr3_seq` |
| 调研 | 记录编号失败处理 | ✅ | `ChainParseError` 异常 |
| 实现 | 在 `utils/cdr_utils.py` 创建 abnumber 封装 | ✅ | `extract_cdrs()`, `count_cdr_mutations()` |
| 实现 | 实现 CDR 提取 | ✅ | 返回包含 cdr1, cdr2, cdr3 的 dict |
| 实现 | 实现突变计数 | ✅ | 与参考序列比较或启发式方法 |
| 实现 | 与天然性过滤器集成 | ✅ | `nativeness.py` 使用 cdr_utils |
| 测试 | 使用有效/无效序列进行单元测试 | ✅ | `test_abnumber.py` - 15 个测试通过 |
| 测试 | Curl 测试 `/validate` 端点 | ✅ | IMGT 拒绝已验证 |

**预期 Python API：**
```python
from abnumber import Chain
chain = Chain(sequence, scheme='imgt')
cdr1 = chain.cdr1_seq
cdr2 = chain.cdr2_seq
cdr3 = chain.cdr3_seq
```

---

### 0.4 AbnatiV v2（天然性评分） ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 调研 | 阅读 AbnatiV GitLab README | ✅ | [GitLab](https://gitlab.developers.cam.ac.uk/ch/sormanni/abnativ) |
| 调研 | 记录 Python API 用法 | ✅ | `abnativ_scoring()` 来自 `abnativ.model.scoring_functions` |
| 调研 | 记录输出字段 | ✅ | AbNatiV 分数 (0-1), CDR 分数, Framework 分数 |
| 调研 | 记录批处理方式 | ✅ | BioPython SeqRecord 列表, batch_size 参数 |
| 实现 | 创建 AbnatiV 封装 | ✅ | 集成在 nativeness.py 中 |
| 实现 | 解析评分到结果 | ✅ | 包含 AbNatiV, CDR-1, CDR-2, CDR-3 的 DataFrame |
| 实现 | 与天然性过滤器集成 | ✅ | `nativeness.py`（当模型可用时） |
| 测试 | 使用示例序列进行单元测试 | ✅ | `test_abnativ.py` - 12 个测试通过 |
| 测试 | 模型下载 | ✅ | `abnativ init` 已完成 (VHH, VHH2, VH, VH2, VL2 等) |

**预期 Python API：**
```python
from abnativ import predict_nanobody
result = predict_nanobody(sequence)
nativeness = result['nativeness_score']
humanness = result['humanness_score']
```

---

### 0.5 promb（OASis 人源性 - 可选） ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 调研 | 阅读 promb GitHub README | ✅ | [GitHub](https://github.com/MSDLLCpapers/promb) |
| 调研 | 记录 Python API 用法 | ✅ | `init_db()`, `run_promb()`, DB 方法 |
| 调研 | 记录参考数据库 | ✅ | "human-oas", "human-swissprot" |
| 调研 | 记录输出格式 | ✅ | Content (0-1), 平均突变 |
| 实现 | 创建 promb 集成 | ✅ | 直接 API 用于 nativeness |
| 实现 | 作为可选交叉检查集成 | ✅ | `nativeness.py` 可以使用 promb |
| 测试 | 使用示例序列进行单元测试 | ✅ | `test_promb.py` - 16 个测试通过 |
| 测试 | 启用 promb 时 Curl 测试 `/validate` | ✅ | API 集成已验证 |

**预期 Python API：**
```python
from promb import compute_humanness
score = compute_humanness(sequence, reference='human_oas')
```

---

### 0.6 datasketch（MinHash 相似度） ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 调研 | 阅读 datasketch GitHub README | ✅ | [GitHub](https://github.com/ekzhu/datasketch) |
| 调研 | 记录 WeightedMinHash 用法 | ✅ | 用于 Jaccard 相似度估计 |
| 调研 | 记录 LSH 快速查找 | ✅ | `MinHashLSH` 用于阈值查询 |
| 调研 | 记录 k-mer 权重策略 | ✅ | k=5，按出现次数加权 |
| 实现 | 在 `utils/similarity.py` 创建 MinHash 封装 | ✅ | `weighted_minhash()`, `weighted_jaccard()` |
| 实现 | 实现 k-mer 索引构建器 | ✅ | `utils/kmer.py`: `generate_kmers()`, `build_kmer_index()` |
| 实现 | 与多样性过滤器集成 | ✅ | `diversity.py` 使用相似度函数 |
| 测试 | 使用相似序列进行单元测试 | ✅ | `test_datasketch.py` - 18 个测试通过 |
| 测试 | Curl 测试 `/validate` 端点 | ✅ | 相似度拒绝已验证 |

**预期 Python API：**
```python
from datasketch import MinHash, MinHashLSH
mh = MinHash(num_perm=128)
for kmer in kmers:
    mh.update(kmer.encode('utf8'))
```

---

### 0.7 异步/信号量并发管理 ✅

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 设计 | 定义异步并发策略 | ✅ | 基于信号量的速率限制 |
| 设计 | 识别并发瓶颈 | ✅ | TNP, MMseqs2, AbnatiV, promb |
| 实现 | 在 `config.py` 添加 `AsyncConfig` | ✅ | 8 个可配置参数 |
| 实现 | `max_concurrent_validations` (默认: 10) | ✅ | 全局验证信号量 |
| 实现 | `max_concurrent_tnp` (默认: 4) | ✅ | TNP 子进程限制 |
| 实现 | `max_concurrent_mmseqs2` (默认: 2) | ✅ | MMseqs2 聚类限制 |
| 实现 | `max_concurrent_abnativ` (默认: 4) | ✅ | AbnatiV 评分限制（GPU 感知） |
| 实现 | `max_concurrent_promb` (默认: 4) | ✅ | promb 计算限制 |
| 实现 | `batch_size` (默认: 50) | ✅ | 异步批处理大小 |
| 实现 | `task_timeout` (默认: 300s) | ✅ | 单任务超时 |
| 实现 | `queue_size` (默认: 1000) | ✅ | 任务队列容量 |
| 实现 | 将所有服务转换为异步 | ✅ | 过滤器、验证器、封装器 |
| 实现 | GPU 调度器 (`gpu_scheduler.py`) | ✅ | 带负载均衡的内存调度器 |
| 实现 | 异步服务层 (`services/`) | ✅ | DiversityService, NativenessService, DevelopabilityService |
| 实现 | 独立服务路由 | ✅ | `/diversity/*`, `/nativeness/*`, `/developability/*`, `/services/*` |
| 实现 | 异步流水线 (`validate_async`) | ✅ | 带信号量的并发验证 |
| 测试 | 验证信号量限制 | ⏳ | 并发请求测试 |

**异步配置参数：**
```python
from metanano.config import Config

config = Config()
config.async_config.max_concurrent_validations  # 10
config.async_config.max_concurrent_tnp          # 4
config.async_config.max_concurrent_mmseqs2      # 2
config.async_config.max_concurrent_abnativ      # 4
config.async_config.max_concurrent_promb        # 4
config.async_config.batch_size                  # 50
config.async_config.task_timeout                # 300.0
config.async_config.queue_size                  # 1000
```

**信号量使用模式：**
```python
import asyncio
from metanano.config import Config

config = Config()
tnp_semaphore = asyncio.Semaphore(config.async_config.max_concurrent_tnp)

async def run_tnp_async(sequence: str):
    async with tnp_semaphore:
        # 在线程池中运行 TNP 以避免阻塞
        return await asyncio.to_thread(run_tnp_sync, sequence)
```

**GPU 调度器配置：**
```python
from metanano.config import Config

config = Config()
gpu_cfg = config.async_config.gpu_scheduler
gpu_cfg.enabled                      # True（启用 GPU 调度）
gpu_cfg.auto_detect                  # True（自动检测 GPU）
gpu_cfg.scheduling_strategy          # "least_loaded" | "round_robin" | "memory_aware"
gpu_cfg.default_max_concurrent_per_gpu  # 2
gpu_cfg.queue_max_size               # 500
gpu_cfg.task_timeout                 # 600.0s
gpu_cfg.health_check_interval        # 30.0s
gpu_cfg.memory_threshold_percent     # 90.0%
```

**GPU 调度器使用：**
```python
from metanano.utils.gpu_scheduler import get_gpu_scheduler

scheduler = get_gpu_scheduler(config.async_config.gpu_scheduler)
await scheduler.initialize()

# 方式 1：手动获取/释放
gpu_index = await scheduler.acquire_gpu(task_id="scoring_001")
try:
    result = await score_on_gpu(sequence, gpu_index)
finally:
    scheduler.release_gpu(gpu_index, task_id="scoring_001")

# 方式 2：自动上下文管理（推荐）
result = await scheduler.run_on_gpu(score_function, sequence)

# 检查状态
status = scheduler.get_status()
# {"enabled": True, "total_gpus": 2, "available_gpus": 1, "gpus": {...}}
```

---

## 1. 基础设施搭建

### 1.1 安装与环境 ✅

| 任务 | 状态 | 负责人 | 备注 |
|------|------|--------|------|
| 创建 conda 环境文件（完整版） | ✅ | - | `install/environment.yml` |
| 创建 conda 环境文件（精简版） | ✅ | - | `install/environment-minimal.yml` |
| 创建 pip 依赖文件（完整版） | ✅ | - | `install/requirements.txt` |
| 创建 pip 依赖文件（精简版） | ✅ | - | `install/requirements-minimal.txt` |
| 创建安装脚本 | ✅ | - | `install/install.sh`，支持 mamba/uv |
| 编写安装文档 | ✅ | - | 在 README.md 中 |

---

## 2. 核心模块 (metanano/)

### 2.1 项目结构 ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 metanano 包 | ✅ | P0 | `metanano/__init__.py` |
| 设置 `app.py` 入口点 | ✅ | P0 | FastAPI 应用 |
| 创建 `config.py` 配置模块 | ✅ | P0 | 所有配置的 Pydantic 模型 |
| 创建 `pipeline.py` 编排器 | ✅ | P0 | ValidationPipeline 类 |

### 2.2 过滤器模块 (`metanano/filters/`) ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `filters/__init__.py` | ✅ | P0 | 模块初始化 |
| 实现 `diversity.py` | ✅ | P0 | MMseqs2 + k-mer 聚类 |
| 实现 `nativeness.py` | ✅ | P0 | abnumber + AbnatiV v2 集成 |
| 实现 `developability.py` | ✅ | P0 | TNP 分析器集成 |

### 2.3 验证器模块 (`metanano/validators/`) ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `validators/__init__.py` | ✅ | P0 | 模块初始化 |
| 实现 `diversity_validator.py` | ✅ | P0 | 批次 + 历史比较 |
| 实现 `nativeness_validator.py` | ✅ | P0 | IMGT 编号 + 评分 |
| 实现 `developability_validator.py` | ✅ | P0 | 红区标准验证 |

### 2.4 模型模块 (`metanano/models/`) ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `models/__init__.py` | ✅ | P0 | 模块初始化 |
| 实现 `sequence.py` | ✅ | P0 | 带验证的序列数据模型 |
| 实现 `validation_result.py` | ✅ | P0 | 结构化验证响应模型 |

### 2.5 工具模块 (`metanano/utils/`) ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `utils/__init__.py` | ✅ | P0 | 模块初始化 |
| 实现 `similarity.py` | ✅ | P0 | 加权 MinHash + k-mer 工具 |
| 实现 `kmer.py` | ✅ | P0 | K-mer 索引生成（k=5,6） |
| 实现 `cdr_utils.py` | ✅ | P0 | CDR 提取和突变计数 |
| 实现 `mmseqs2_wrapper.py` | ✅ | P0 | MMseqs2 命令行封装 |

### 2.6 路由模块 (`metanano/routes/`) ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `routes/__init__.py` | ✅ | P0 | 模块初始化 |
| 实现 `submission_routes.py` | ✅ | P0 | POST /submit 端点 |
| 实现 `validation_routes.py` | ✅ | P0 | POST /validate, /validate/batch 端点 |
| 实现 `health_routes.py` | ✅ | P0 | GET /health 端点 |
| 实现 `diversity_routes.py` | ✅ | P1 | 多样性服务端点 |
| 实现 `nativeness_routes.py` | ✅ | P1 | 天然性服务端点 |
| 实现 `developability_routes.py` | ✅ | P1 | 可开发性服务端点 |
| 实现 `service_routes.py` | ✅ | P1 | GPU/信号量状态端点 |

### 2.7 服务模块 (`metanano/services/`) ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `services/__init__.py` | ✅ | P1 | 模块初始化 |
| 实现 `async_manager.py` | ✅ | P1 | 集中信号量管理 |
| 实现 `diversity_service.py` | ✅ | P1 | 异步多样性过滤器服务 |
| 实现 `nativeness_service.py` | ✅ | P1 | 异步天然性过滤器服务 |
| 实现 `developability_service.py` | ✅ | P1 | 异步可开发性过滤器服务 |

---

## 3. 过滤器实现细化

### 3.1 多样性过滤器 🚧

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| MMseqs2 聚类（相似度 ≥ 0.98） | ✅ | P0 | 基础实现完成 |
| CDR 突变计数（合计 ≥ 2） | ✅ | P0 | 使用 abnumber |
| CDR3 突变检查（≥ 1） | ✅ | P0 | 已实现 |
| K-mer 索引构建器 | ✅ | P0 | k=5 或 k=6 可配置 |
| 方案 A：加权 MinHash（Jaccard < 0.9） | ✅ | P1 | 使用 datasketch |
| 方案 B：排行榜前 50 名对比 | ✅ | P0 | 首选策略 |
| 历史序列数据库集成 | ⏳ | P1 | 需要数据库设置 |

### 3.2 天然性过滤器 🚧

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| abnumber IMGT 编号集成 | ✅ | P0 | Chain 类封装 |
| AbnatiV v2 天然性评分（≥ 0.80） | ✅ | P0 | predict_nanobody 封装 |
| AbnatiV v2 人源性评分（≥ 0.75） | ✅ | P0 | 已实现 |
| promb OASis 集成（可选） | ✅ | P2 | 通过 promb.enabled 配置 |
| 异步批处理（信号量） | ✅ | P1 | config.py 中的 AsyncConfig |
| GPU 加速（可用时） | ⏳ | P2 | CUDA 感知并发限制 |

### 3.3 可开发性过滤器 🚧

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| TNP 分析器集成 | ✅ | P0 | profile_nanobody 封装 |
| 总 CDR 长度检查（L < 20 或 L > 39） | ✅ | P0 | 红区标准 |
| CDR3 长度检查（L3 < 5 或 L3 > 23） | ✅ | P0 | 红区标准 |
| CDR3 紧凑度（C < 0.56 或 C > 1.61） | ✅ | P0 | 红区标准 |
| 表面疏水性斑块（PSH 范围） | ✅ | P0 | PSH < 73.4 或 PSH > 155.47 |
| 正电荷斑块（PPC > 1.18） | ✅ | P0 | 红区标准 |
| 负电荷斑块（PNC > 1.88） | ✅ | P0 | 红区标准 |

---

## 4. 测试

### 4.1 单元测试 (`metanano/tests/`) ⏳

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 `tests/__init__.py` | ✅ | P1 | 模块初始化 |
| 实现 `test_diversity.py` | ⏳ | P1 | 多样性过滤器测试 |
| 实现 `test_nativeness.py` | ⏳ | P1 | 天然性过滤器测试 |
| 实现 `test_developability.py` | ⏳ | P1 | 可开发性过滤器测试 |
| 实现 `test_submission.py` | ⏳ | P1 | 提交路由测试 |
| 实现 `test_validation.py` | ⏳ | P1 | 验证流水线测试 |
| 实现 `test_utils.py` | ⏳ | P1 | 工具函数测试 |

### 4.2 集成测试 ⏳

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 端到端流水线测试 | ⏳ | P1 | 完整验证流程 |
| API 端点集成测试 | ⏳ | P1 | HTTP 请求/响应验证 |
| 性能基准测试 | ⏳ | P2 | 批处理吞吐量 |

---

## 5. 文档

### 5.1 代码文档 ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 添加模块级文档字符串（双语） | ✅ | P1 | 英文 + 中文 |
| 添加函数文档字符串 | ✅ | P1 | 参数、返回值、示例 |
| 添加 Pydantic 字段描述 | ✅ | P1 | OpenAPI 可见性 |
| 创建 API 使用示例 | ✅ | P2 | curl 命令、Python 代码片段 |

### 5.2 项目文档 ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 英文 README.md | ✅ | P0 | `docs/en/README.md` |
| 中文 README.md | ✅ | P0 | `docs/cn/README.md` |
| 创建 TODO.md（英文） | ✅ | P0 | `docs/en/TODO.md` |
| 创建 TODO.md（中文） | ✅ | P0 | 本文件 |
| 创建 BUGS.md | ⏳ | P1 | 问题跟踪 |

---

## 6. 部署与运维

### 6.1 容器化 ⏳

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 创建 Dockerfile | ⏳ | P1 | 多阶段构建 |
| 创建 docker-compose.yml | ⏳ | P1 | 本地开发环境 |
| 创建 .env.example | ⏳ | P1 | 环境变量模板 |
| 容器 GPU 支持 | ⏳ | P2 | CUDA 运行时 |

### 6.2 CI/CD ⏳

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 设置 GitHub Actions | ⏳ | P2 | 自动化测试 |
| 代码检查工作流（ruff/black） | ⏳ | P2 | 代码质量 |
| 类型检查工作流（mypy） | ⏳ | P2 | 类型安全 |

---

## 7. 数据库集成 ⏳

### 7.1 数据持久化 ⏳

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 设计数据库模式 | ⏳ | P1 | 提交、结果、用户 |
| 实现提交存储 | ⏳ | P1 | 保存验证后的序列 |
| 历史序列检索 | ⏳ | P1 | 用于多样性比较 |
| 排行榜前 N 名查询 | ⏳ | P1 | 方案 B 比较 |

---

## 8. 未来增强

### 8.1 性能优化 ✅

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| 异步批处理（信号量） | ✅ | P1 | 带限制的并发验证 |
| 异步服务（所有过滤器/验证器） | ✅ | P1 | `services/` 模块带异步方法 |
| 异步流水线 (validate_async) | ✅ | P1 | 支持同步和异步 |
| 独立服务路由 | ✅ | P1 | 每个过滤器的 API 端点 |
| K-mer 索引 Redis 缓存 | ⏳ | P3 | 减少计算量 |
| GPU 加速相似度搜索 | ⏳ | P3 | FAISS 集成 |

### 8.2 功能扩展 ⏳

| 任务 | 状态 | 优先级 | 备注 |
|------|------|--------|------|
| Web UI 仪表板 | ⏳ | P3 | 结果可视化 |
| 批量上传支持 | ⏳ | P3 | CSV/FASTA 文件处理 |
| Webhook 通知 | ⏳ | P3 | 异步结果推送 |

---

## 优先级定义

| 优先级 | 描述 |
|--------|------|
| P0 | 关键 - MVP 必需 |
| P1 | 高 - 生产就绪所需 |
| P2 | 中 - 锦上添花 |
| P3 | 低 - 未来增强 |

---

## 实现摘要

### 已完成 ✅
- `metanano/` 下的完整项目结构
- 所有三个过滤器已实现（多样性、天然性、可开发性）
- 所有验证器已实现
- 所有带 Pydantic 验证的数据模型
- 所有 API 路由（submit、validate、health）
- 所有工具函数（k-mer、相似度、CDR、MMseqs2）
- 完整的双语文档
- TNP 工具调研（CLI 模式、输出格式已记录）

### 已完成 ✅
- 外部工具集成遵循三阶段工作流：
  - **TNP**: 调研 ✅ → 实现 ✅ → 测试 ✅ (12 个测试)
  - **MMseqs2**: 调研 ✅ → 实现 ✅ → 测试 ✅ (11 个测试)
  - **abnumber**: 调研 ✅ → 实现 ✅ → 测试 ✅ (15 个测试)
  - **AbnatiV v2**: 调研 ✅ → 实现 ✅ → 测试 ✅ (12 个测试)
  - **promb**: 调研 ✅ → 实现 ✅ → 测试 ✅ (16 个测试)
  - **datasketch**: 调研 ✅ → 实现 ✅ → 测试 ✅ (18 个测试)
- **总计：84 个测试通过** 在 `metanano/tests/tools/`
- **异步/信号量并发**: `AsyncConfig` 已添加到 `config.py`，包含 8 个超参数：
  - `max_concurrent_validations`, `max_concurrent_tnp`, `max_concurrent_mmseqs2`
  - `max_concurrent_abnativ`, `max_concurrent_promb`
  - `batch_size`, `task_timeout`, `queue_size`
- **GPU 调度器**: `utils/gpu_scheduler.py` 中的内存调度器，包含：
  - 实时 GPU 使用跟踪（队列 + 活动任务）
  - 负载均衡策略：`round_robin`（轮询）、`least_loaded`（最少负载）、`memory_aware`（内存感知）
  - GPU 注册和动态启用/禁用
  - 内存阈值监控和健康检查

### 进行中 🚧
- 历史序列数据库集成

### 待处理 ⏳
- 单元测试和集成测试
- Docker 容器化
- CI/CD 流水线
- GPU 加速优化

### 新增路由 ✅
- `/diversity/analyze` - 完整多样性分析
- `/diversity/batch-check` - MMseqs2 批次多样性
- `/diversity/cdr-mutations` - CDR 突变检查
- `/nativeness/analyze` - 完整天然性分析
- `/nativeness/imgt-number` - IMGT 编号
- `/nativeness/scores` - 天然性/人源性分数
- `/developability/analyze` - 完整可开发性分析
- `/developability/tnp-profile` - TNP 分析
- `/developability/analyze-batch` - 批量分析
- `/services/status` - 服务管理器状态
- `/services/gpu` - GPU 调度器状态
- `/services/gpu/control` - GPU 启用/禁用
- `/validate/batch` - 批量验证

---

## 备注

- 所有过滤器阈值可通过 `metanano/config.py` 配置
- 过滤器按顺序应用：多样性 → 天然性 → 可开发性
- 过滤器失败时提前终止以优化性能
- 所有文档字符串和注释为双语（英文 + 中文）
- FastAPI 在 `/docs` 提供自动 OpenAPI 文档
- **工具集成工作流**: 调研 → 实现 → 测试（使用 curl 验证）
- **异步并发**: 所有服务使用 `asyncio.Semaphore` 进行速率限制
- **信号量配置**: `config.async_config.*` 控制并发任务限制
- **GPU 调度器**: `config.async_config.gpu_scheduler.*` 用于 GPU 密集型任务管理
- **调度策略**: `least_loaded`（默认）、`round_robin`、`memory_aware`
