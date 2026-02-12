# 搜索架构

序列搜索子系统如何检测重复和过于相似的纳米抗体提交。

> **主要目标**：给定一个查询纳米抗体，找出所有已索引序列中足够相似、可被视为重复或近重复的条目，即使这些纳米抗体共享高度保守的框架区。

---

## 目录

1. [为什么纳米抗体搜索很难](#1-为什么纳米抗体搜索很难)
2. [搜索流水线概览](#2-搜索流水线概览)
3. [阶段 1：粗过滤](#3-阶段-1粗过滤)
4. [阶段 2：精细比对](#4-阶段-2精细比对)
5. [阶段 3：CDR 比较](#5-阶段-3cdr-比较)
6. [检索策略](#6-检索策略)
7. [配置参考](#7-配置参考)
8. [面向纳米抗体重复检测的调参建议](#8-面向纳米抗体重复检测的调参建议)
9. [API 参考](#9-api-参考)
10. [性能特征](#10-性能特征)

---

## 1. 为什么纳米抗体搜索很难

纳米抗体（VHH 单域抗体）长度约为 110-130 个氨基酸。其中约 70-75% 是**框架区**（FR1-FR4），在同一物种内高度保守——即使是无关纳米抗体，序列一致性通常也超过 85-90%。

这为相似性搜索带来了一个根本性问题：

```
Nanobody A: FR1-CDR1-FR2-CDR2-FR3-CDR3(ARDLGTYYYYGMDV)-FR4
Nanobody B: FR1-CDR1-FR2-CDR2-FR3-CDR3(AKNQPWSSALDY)--FR4

Whole-sequence identity: ~87%  (looks similar!)
CDR3 identity:            0%  (completely different binding)
```

两个纳米抗体即使 **CDR3 完全不同**（因此抗原结合也不同），由于保守框架区占比很高，整体序列一致性依然可能超过 80%。

### 真正决定新颖性的因素

| 区域 | 序列占比 | 保守性 | 在新颖性中的作用 |
|--------|--------------|-------------|-----------------|
| FR1-FR4 | ~70-75% | >85-90% conserved | 低——结构支架 |
| CDR1 | ~5% | Moderate | 中等——微调结合 |
| CDR2 | ~10% | Moderate | 中等——参与 paratope |
| **CDR3** | **~10-15%** | **Highly variable** | **决定结合特异性的首要因素** |

CDR3 是 VDJ 重组的产物，也是变异性最高的区域。即便 CDR3 仅有 1-2 个氨基酸差异，也可能改变表位特异性。仅 CDR3 长度（通常 12-18 aa，中位数约 15）本身就是强信号——长度差异 ≥3 个残基几乎可以确定其结合几何构型不同。

### 这对搜索系统意味着什么

搜索流水线必须：
1. **不被框架区保守性误导**——整体序列高相似并不等于功能重复。
2. **将 CDR 级别相似性**与整体序列指标分开呈现。
3. **具备规模化能力**——竞赛数据库可增长到 100k+ 序列。

---

## 2. 搜索流水线概览

```
                          Query Sequence
                               │
                    ┌──────────▼──────────┐
                    │  Generate k-mers    │  k=5, set of unique 5-mers
                    │  Self-exclusion     │  exclude IDs with identical sequence
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │         Retrieval Strategy       │
              │                                  │
     ┌────────▼────────┐              ┌─────────▼─────────┐
     │  kmer_jaccard    │              │       lsh          │
     │  (exact)         │              │  (approximate)     │
     │                  │              │                    │
     │ Stage 1: shared  │              │ MinHash signature  │
     │   k-mer count    │              │ LSH bucket lookup  │
     │ Stage 2: Jaccard │              │ Re-rank by Jaccard │
     │ Stage 3: top-K   │              │ top-K              │
     └────────┬────────┘              └─────────┬─────────┘
              │                                  │
              └────────────────┬─────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Fine Alignment     │  Smith-Waterman (BLOSUM62)
                    │  (parallel batches) │  parasail SIMD / BioPython
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  CDR Comparison     │  Per-CDR similarity scores
                    │  (if CDRs available)│  CDR1, CDR2, CDR3
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Rank & Return      │  Sort by identity desc,
                    │                     │  then target_id asc
                    └─────────────────────┘
```

### 关键设计决策

- **双检索策略**：`kmer_jaccard`（精确，默认）与 `lsh`（近似，规模化更快）。两者都会产出候选列表，并进入同一比对流水线。
- **由粗到细**：粗过滤在毫秒级将 100k+ 序列收敛到 ≤500 个候选；精细比对仅对这些候选执行。
- **CDR 比较为附加信息**：不参与排序（排序依据为比对 identity），但提供判定真实新颖性所需的 CDR 级拆解。
- **确定性排序**：无论 Jaccard 还是 identity 出现并列，均按 `target_id` 升序打破并列。相同输入始终得到相同输出。

---

## 3. 阶段 1：粗过滤

粗过滤用于快速将全量索引收敛为小规模候选集。它基于 **k-mer 集合**（短子序列集合）工作，而非原始序列直接比对。

### k-mer 的工作方式

当序列 `EVQLVQS` 的 `k=5` 时，可生成：

```
{ EVQLV, VQLVQ, QLVQS }
```

如果两条序列共享大量 5-mers，它们很可能相似。其 **Jaccard 相似度**用于度量这一点：

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

### 三阶段流程（kmer_jaccard 策略）

**阶段 1 — 共享 k-mer 计数**：对每条已索引序列，借助倒排索引统计其与查询序列共享的 k-mer 数量。共享数小于 `min_shared_kmers` 的序列被丢弃。

**阶段 2 — Jaccard 阈值筛选**：对阶段 1 幸存项计算精确 Jaccard 相似度。低于 `jaccard_threshold` 的序列被丢弃。

**阶段 3 — Top-K 选择**：按 Jaccard 降序排序（并列按 ID 升序），保留前 `max_candidates`。

### 参数影响

| 参数 | 默认值 | 更低 → | 更高 → |
|-----------|---------|---------|----------|
| `k` | 5 | 每条序列 k-mer 更多、匹配更多、特异性更低 | k-mer 更少、特异性更高、可能漏掉远距离匹配 |
| `min_shared_kmers` | 3 | 更多候选通过阶段 1（更慢、召回更高） | 候选更少（更快、可能漏掉远距离匹配） |
| `jaccard_threshold` | 0.3 | 更多候选通过阶段 2 | 候选更少、仅保留更相似项 |
| `max_candidates` | 500 | 比对阶段更快 | 更多候选进入比对（更慢、召回更高） |

### 为什么默认 Jaccard 阈值是 0.3

对于纳米抗体，基于 5-mers 的 0.3 Jaccard 阈值是有意设为宽松的。由于框架区保守，即使无关纳米抗体也会共享大量 5-mers。设为 0.3 可确保：
- 所有功能相近序列都能被召回（避免假阴性）。
- 最终相似性判断由比对阶段（阶段 2）完成。
- 在 100k 索引规模下，每次查询通常有约 50-500 个候选存活。

若提高到 0.5+，将漏掉主要在 CDR3 上有差异的序列（CDR3 仅占总 k-mer 的一小部分）。

---

## 4. 阶段 2：精细比对

粗过滤输出的每个候选都会与查询序列执行成对序列比对。

### 算法

- **方法**：默认使用 Smith-Waterman（局部比对）。
- **评分矩阵**：BLOSUM62（蛋白序列标准配置）。
- **缺口罚分**：Open = 10（可配置），Extend = 1（固定）。
- **后端**：优先使用 parasail（SIMD 加速），并提供 BioPython 回退。

### 每个候选的输出

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `score` | int | 原始比对得分 |
| `identity` | float | 匹配位点比例（0.0-1.0） |
| `cigar` | string | 编码比对操作的 CIGAR 字符串 |
| `aligned_query` | string | 插入缺口后的查询序列（当 `include_alignment=true`） |
| `aligned_target` | string | 插入缺口后的目标序列（当 `include_alignment=true`） |
| `tier` | string | 展示用标签：exact (≥0.95), high (≥0.80), moderate (≥0.50), low (<0.50) |

### 并行化

候选会按每批 16 条切分，并使用线程池并行比对（最多 32 个工作线程）。这是最昂贵的阶段——在 221k 索引规模下，比对阶段主导 P99 延迟。

### identity 与 Jaccard 的区别

二者度量的是不同维度：

| 指标 | 度量内容 | 对框架区敏感性 |
|--------|-----------------|----------------------|
| **K-mer Jaccard** | 共享子序列（无序） | 高——框架区会抬高分数 |
| **Alignment identity** | 逐位点匹配（有序、允许缺口） | 高——框架区会抬高分数 |
| **CDR similarity** | 各 CDR 匹配（CDR1、CDR2、CDR3 分别计算） | **无**——排除框架区 |

Jaccard 与 alignment identity 都会受到框架区保守性的抬升。CDR 比较（阶段 3）提供不受框架区影响的信号。

---

## 5. 阶段 3：CDR 比较

若查询序列与目标序列均可获得 CDR 注释，系统会计算逐 CDR 的相似度分数。

### CDR 的获取方式

1. **来自索引**：若序列在索引时已附带 CDR 注释（`cdrs` 字典），则直接使用。
2. **来自提取**：否则在查询时使用 `abnumber`（IMGT 方案）提取 CDR1、CDR2、CDR3。
3. **缺失场景**：若提取失败（例如未安装 abnumber），则 CDR 相似度为 `null`。

### 相似度计算

对每个 CDR（CDR1、CDR2、CDR3）：

- **长度相同**：使用 Hamming 距离并归一化到 [0, 1]。
  ```
  similarity = 1.0 - (mismatches / length)
  ```
- **长度不同**：按位错配数 + 长度差，并按较长 CDR 归一化。
  ```
  distance = positional_mismatches + |len_query - len_target|
  similarity = 1.0 - (distance / max(len_query, len_target))
  ```

### CDR 相似度解读

| CDR3 相似度 | 解读 |
|----------------|----------------|
| 1.00 | CDR3 完全一致——几乎可确定为重复 |
| ≥0.85 | 非常相似——很可能同一表位、同一 clonotype |
| 0.70-0.85 | 相关克隆——可能结合同一表位但亲和力不同 |
| <0.70 | 明显不同——很可能为不同结合特异性 |

| CDR1+CDR2 相似度 | 解读 |
|---------------------|----------------|
| 两者均 ≥0.90 且 CDR3 ≥0.80 | 重复证据强 |
| 两者均 ≥0.90 且 CDR3 <0.70 | 同框架家族，但结合体不同 |

---

## 6. 检索策略

系统支持两种检索策略，通过 `coarse_filter.retrieval_strategy` 配置。

### `kmer_jaccard`（默认）

基于倒排索引执行精确 k-mer Jaccard 计算。结果确定性强；对于高于 Jaccard 阈值的序列，不会产生假阴性。

**适用场景**：数据库规模在 ~100k 以内，且精确召回优先。

### `lsh`（Locality-Sensitive Hashing）

使用 `datasketch` 库中的 MinHash 签名与 LSH 桶进行近似检索。

**工作机制**：
1. 每条已索引序列生成一个 MinHash 签名（其 k-mer 集合的紧凑 sketch）。
2. 通过 band/row 分区将签名插入 LSH 索引。
3. 查询时在 LSH 索引中查找查询序列的 MinHash 签名。
4. 使用精确 MinHash Jaccard 对候选重新排序。

**参数**：

| 参数 | 默认值 | 影响 |
|-----------|---------|--------|
| `num_perm` | 128 | 哈希置换次数。越高表示 Jaccard 估计越准确，但内存更高、构建更慢。128 适合筛选；高召回基准建议 256。 |
| `lsh_threshold` | 0.3 | LSH 桶匹配的最小估计 Jaccard。应设为 **不高于** `jaccard_threshold`，避免漏掉边界样本。 |
| `weights` | (0.5, 0.5) | 假阳性/假阴性权衡。(0.5, 0.5) 表示均衡；向 (0.3, 0.7) 偏移可降低假阴性，但候选数量会增多。 |

**适用场景**：数据库规模 >100k，查询速度优先于绝对召回。基准结果显示，在真实抗体数据上可获得 0.90-0.97 召回率与 3.5-5.5x 查询加速。

**权衡**：LSH 构建速度慢于纯 k-mer 索引（每条序列都要计算 MinHash）。在 221k 序列规模下，串行 LSH 构建需数分钟，而纯 k-mer 索引约 ~46s。

### 策略选择建议

| 场景 | 策略 | 原因 |
|----------|----------|--------|
| <100k 序列 | `kmer_jaccard` | 已足够快，且召回精确 |
| 100k-500k 序列 | 二者皆可 | kmer_jaccard 可用但 P99 增长；LSH 查询更快 |
| >500k 序列 | `lsh` | kmer_jaccard 粗过滤会成为瓶颈 |
| 召回率至关重要 | `kmer_jaccard` | 无假阴性 |
| 查询延迟至关重要 | `lsh` | 查询速度提升 3-5x |

---

## 7. 配置参考

所有参数位于 `metanano/config.py`。

### SearchConfig

```python
from metanano.config import SearchConfig

config = SearchConfig(
    k=5,                          # K-mer length (3-10, default 5)
    job_ttl_seconds=3600.0,       # Job retention time (seconds)
    max_concurrent_search=4,      # Max parallel search jobs

    coarse_filter=CoarseFilterConfig(
        min_shared_kmers=3,       # Stage 1 threshold
        jaccard_threshold=0.3,    # Stage 2 threshold
        max_candidates=500,       # Stage 3 cap
        retrieval_strategy="kmer_jaccard",  # or "lsh"
    ),

    lsh=LSHConfig(
        num_perm=128,             # MinHash permutations
        lsh_threshold=0.3,        # LSH bucket threshold
        weights=(0.5, 0.5),       # FP/FN balance
    ),

    fine_alignment=FineAlignmentConfig(
        gap_open=10,              # Alignment gap open penalty
    ),
)
```

### 校验规则

- `lsh.lsh_threshold` 必须 ≤ `coarse_filter.jaccard_threshold`（由模型校验器强制）。
- `k` 必须在 [1, 10] 区间内。对于纳米抗体推荐使用 5 或 6。

### 全量参数表

| 参数 | 路径 | 类型 | 默认值 | 范围 | 描述 |
|-----------|------|------|---------|-------|-------------|
| `k` | `search.k` | int | 5 | 1-10 | k-mer 长度 |
| `min_shared_kmers` | `search.coarse_filter.min_shared_kmers` | int | 3 | ≥1 | 通过阶段 1 所需的最小共享 k-mer 数 |
| `jaccard_threshold` | `search.coarse_filter.jaccard_threshold` | float | 0.3 | 0.0-1.0 | 通过阶段 2 所需的最小 Jaccard |
| `max_candidates` | `search.coarse_filter.max_candidates` | int | 500 | ≥1 | 粗过滤后保留的最大候选数 |
| `retrieval_strategy` | `search.coarse_filter.retrieval_strategy` | str | "kmer_jaccard" | kmer_jaccard, lsh | 检索方法 |
| `num_perm` | `search.lsh.num_perm` | int | 128 | ≥16 | MinHash 置换次数 |
| `lsh_threshold` | `search.lsh.lsh_threshold` | float | 0.3 | 0.0-1.0 | LSH 相似度阈值 |
| `weights` | `search.lsh.weights` | tuple | (0.5, 0.5) | — | LSH 假阳性/假阴性权重平衡 |
| `gap_open` | `search.fine_alignment.gap_open` | int | 10 | ≥0 | 比对 gap open 罚分 |
| `job_ttl_seconds` | `search.job_ttl_seconds` | float | 3600 | ≥1 | 异步任务 TTL |
| `max_concurrent_search` | `search.max_concurrent_search` | int | 4 | ≥1 | 并发搜索上限 |

---

## 8. 面向纳米抗体重复检测的调参建议

默认参数针对**通用相似性搜索**优化。若目标是**检测重复或过于相似的纳米抗体提交**，建议考虑如下调整。

### 推荐判定逻辑

```python
def is_duplicate(match):
    """
    Decide whether a search match represents a duplicate submission.
    Uses CDR-focused logic rather than whole-sequence identity alone.
    """
    identity = match.identity
    cdr_sim = match.cdr_similarity  # may be None

    # Tier 1: Whole-sequence near-identity — definitely a duplicate
    if identity >= 0.95:
        return True, "near-identical sequence"

    # Tier 2: CDR3-focused check (if CDRs available)
    if cdr_sim is not None:
        cdr3 = cdr_sim.get("CDR3", 0.0)

        # CDR3 identity >= 0.85 = same clonotype, likely same epitope
        if cdr3 >= 0.85:
            return True, f"CDR3 identity {cdr3:.0%} (same clonotype)"

        # CDR3 >= 0.80 with conserved CDR1+CDR2 = functional duplicate
        cdr1 = cdr_sim.get("CDR1", 0.0)
        cdr2 = cdr_sim.get("CDR2", 0.0)
        if cdr3 >= 0.80 and cdr1 >= 0.90 and cdr2 >= 0.90:
            return True, f"CDR3={cdr3:.0%} with conserved CDR1/CDR2"

    # Tier 3: High whole-sequence identity without CDR data
    if identity >= 0.90 and cdr_sim is None:
        return True, f"whole-sequence identity {identity:.0%} (no CDR data)"

    return False, "novel"
```

### 为什么不能只看整体序列一致性？

原因在于框架区保守性。看下面这个例子：

| 指标 | 数值 | 解读 |
|--------|-------|----------------|
| Whole-sequence identity | 88% | 看起来像重复 |
| CDR3 identity | 15% | 结合体完全不同 |
| CDR1 identity | 95% | 同一胚系家族 |
| CDR2 identity | 90% | 同一胚系家族 |

若仅使用整体序列一致性，会**错误地将其判为重复**。真正决定结合特异性的 CDR3 在该例中完全不同。

### 严格重复检测的参数调整

```python
# Strict: catch all potential duplicates (more false positives)
SearchConfig(
    coarse_filter=CoarseFilterConfig(
        min_shared_kmers=1,       # Very permissive Stage 1
        jaccard_threshold=0.2,    # Catch distant matches
        max_candidates=1000,      # More candidates for review
    ),
)

# Balanced (recommended for competition)
SearchConfig(
    coarse_filter=CoarseFilterConfig(
        min_shared_kmers=3,       # Default
        jaccard_threshold=0.3,    # Default
        max_candidates=500,       # Default
    ),
)

# Fast: large database, accept some false negatives
SearchConfig(
    coarse_filter=CoarseFilterConfig(
        min_shared_kmers=5,       # Stricter Stage 1
        jaccard_threshold=0.4,    # Stricter Stage 2
        max_candidates=200,       # Fewer alignment targets
        retrieval_strategy="lsh",
    ),
    lsh=LSHConfig(
        num_perm=128,
        lsh_threshold=0.3,
    ),
)
```

### 将 CDR3 长度作为快速预过滤

CDR3 长度差异是强信号。对于纳米抗体，若 CDR3 长度差异 ≥3 个残基，几乎可以确定其结合几何构型不同，无论序列相似度如何。可在完整搜索流水线前使用该规则进行快速预过滤。

---

## 9. API 参考

### 端点

| 端点 | 方法 | 描述 |
|----------|--------|-------------|
| `POST /search` | Submit | 提交异步搜索任务，返回 `job_id`（HTTP 202） |
| `GET /search/{job_id}` | Poll | 获取任务状态与结果 |
| `POST /search/index` | Index | 向搜索索引添加一条序列（HTTP 201） |
| `GET /search/index/stats` | Stats | 获取已索引序列数量 |

### 序列校验

所有输入序列均会校验：
- **字符**：仅允许标准氨基酸（`ACDEFGHIKLMNPQRSTVWY`）
- **长度**：10-500 个残基
- **规范化**：转为大写并移除空白

### 任务生命周期

```
POST /search → 202 { job_id }
                      │
                      ▼
               ┌─── pending ───┐
               │               │
               ▼               │ (semaphore wait)
            running            │
               │               │
        ┌──────┴──────┐       │
        ▼             ▼       │
   completed       failed     │
   (results)     (error msg)  │
        │             │       │
        └──────┬──────┘       │
               ▼              │
         TTL expiry ──────────┘
         (cleanup)
```

任务在创建后会保留 `job_ttl_seconds`（默认：1 小时），之后清理。

### 搜索请求

```json
{
  "sequences": ["EVQLVESGGGLVQPGG..."],
  "include_alignment": false,
  "coarse_min_shared": null,
  "coarse_jaccard": null
}
```

`coarse_min_shared` 与 `coarse_jaccard` 字段仅覆盖本次查询的服务端默认参数。

### 搜索结果

```json
{
  "job_id": "...",
  "status": "completed",
  "result": [{
    "query_sequence": "EVQLVESGGGLVQPGG...",
    "total_candidates": 47,
    "total_indexed": 10000,
    "elapsed_ms": 234.5,
    "matches": [{
      "target_id": "db_001",
      "target_sequence": "QVQLVQSGVEVKKPGA...",
      "score": 621,
      "identity": 0.8831,
      "tier": "high",
      "cigar": "...",
      "cdr_similarity": {
        "CDR1": 0.95,
        "CDR2": 0.88,
        "CDR3": 0.42
      }
    }]
  }]
}
```

---

## 10. 性能特征

基于来自 PLAbDab 的 221,692 条真实重链序列完成基准测试。

### Tier 1：K-mer 粗过滤 + 比对

| N | 构建 | 峰值 RSS | P50 | P95 | P99 |
|---|-------|----------|-----|-----|-----|
| 10k | 3.2s | 39 MB | 57 ms | 448 ms | 470 ms |
| 50k | 12.8s | 147 MB | 274 ms | 553 ms | 644 ms |
| 100k | 23.2s | 248 MB | 471 ms | 686 ms | 797 ms |
| 221k | 45.9s | 493 MB | 780 ms | 1,415 ms | 1,577 ms |

内存随规模线性增长（每 1,000 条序列约 2.2 MB）。延迟呈超线性增长，因为真实抗体序列按进化家族聚类分布，相比合成数据，每次查询会产生更多粗过滤候选。

### Tier 2：LSH 召回率

| N | 平均召回率 | LSH 查询 | 精确查询 | 加速比 |
|---|-----------|-----------|-------------|---------|
| 10k | 0.967 | 3.9 ms | 13.5 ms | 3.5x |
| 50k | 0.898 | 14.1 ms | 77.5 ms | 5.5x |

LSH 在所有测试规模下的召回率均超过 0.89，且加速比会随索引规模增长。

### 扩展规模建议

| 索引规模 | 策略 | 预期 P99 | 说明 |
|-----------|----------|-------------|-------|
| <10k | kmer_jaccard | <500 ms | 任何场景都足够快 |
| 10k-100k | kmer_jaccard | <800 ms | 默认配置表现良好 |
| 100k-500k | 推荐 lsh | <200 ms query | 构建更慢，但查询更快 |
| >500k | 必须 lsh | — | kmer_jaccard 的 P99 会过高 |
