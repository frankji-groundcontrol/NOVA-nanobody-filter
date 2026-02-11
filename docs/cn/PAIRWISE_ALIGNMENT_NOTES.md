# 成对比对方案说明（当前实现与更快选项）

本文档说明项目当前使用的成对比对后端，以及可选的更快方案。

## 1. 当前实现（已在项目中启用）

当前搜索链路使用 `AlignmentEngine`：

- 主后端：`parasail`（CPU SIMD）
- 回退后端：`Bio.Align.PairwiseAligner`（BioPython）
- 默认方法：`local`（Smith-Waterman，局部比对）
- 可选方法：`global`（Needleman-Wunsch，全局比对）
- 评分矩阵：`BLOSUM62`

代码位置：

- `metanano/utils/alignment.py`
- `metanano/search/search_engine.py`

### 为什么当前方案可接受

- `parasail` 成熟稳定，CPU 场景下速度和可维护性平衡较好。
- 现有业务链路已完成集成和测试，风险最低。
- 在无 GPU 依赖的部署环境中，迁移成本最小。

## 2. 是否有更快选择（在线调研结论）

有，但取决于硬件和目标场景。

### 2.1 CUDASW++4.0（GPU，蛋白数据库搜索）

- 仓库：`https://github.com/asbschmidt/CUDASW4`
- 特点：GPU 加速 Smith-Waterman，面向蛋白数据库搜索。
- 支持矩阵：支持 `blosum62` 等 BLOSUM 系列。
- 适用：有现代 NVIDIA GPU（Ampere/Ada/Hopper）且吞吐要求高。
- 注意：工程接入复杂度高于当前 CPU 方案。

### 2.2 Accelign（GPU，新方案）

- 仓库：`https://github.com/fkallen/Accelign`
- 特点：支持 local/global/semiglobal，支持蛋白字母表与替换矩阵。
- 适用：追求更高吞吐并愿意承担新库评估成本。
- 注意：相对较新，建议先做稳定性与可重复性验证。

### 2.3 ksw2（CPU SIMD）

- 仓库：`https://github.com/lh3/ksw2`
- 特点：在某些模式下速度优秀。
- 注意：并非当前链路的直接替代（其能力重点与本项目默认 local SW 路径并不完全一致）。

## 3. 推荐策略

### CPU-only 环境

继续使用当前方案：`parasail` + BioPython fallback。

### GPU 可用且要提吞吐

按优先级评估：

1. 先评估 `CUDASW++4.0`
2. 再对比 `Accelign`

并在真实 VHH 数据上做基准测试（延迟、吞吐、结果一致性）。

## 4. 最小基准建议（迁移前必做）

至少对以下指标做 A/B：

- 单查询延迟（P50/P95）
- 批量吞吐（queries/s）
- Top-K 一致性（identity/tier 排序差异）
- 资源成本（CPU/GPU 占用与部署复杂度）

## 5. 结论

当前实现对现阶段是合理选择。若后续出现明显吞吐瓶颈，再引入 GPU 路线会更稳妥。
