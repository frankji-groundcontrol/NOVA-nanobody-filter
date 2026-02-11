# 搜索快速上手

本指南提供使用序列搜索功能的最快路径，适合本地调试与接口联调。

## 功能概览

- 内存序列索引（`/search/index`）
- 异步搜索任务提交（`/search` -> `job_id`）
- 轮询查询状态与结果（`/search/{job_id}`）
- 索引统计（`/search/index/stats`）

## 前置条件

1. 启动 API 服务：

```bash
python -m uvicorn metanano.app:app --reload --port 5000
```

2. 检查服务健康状态：

```bash
curl http://localhost:5000/health
```

## 1）索引参考序列

```bash
curl -X POST http://localhost:5000/search/index \
  -H "Content-Type: application/json" \
  -d '{
    "id": "db_001",
    "sequence": "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS",
    "cdrs": {"CDR3": "RDYRFDMGFDY"}
  }'
```

预期：HTTP `201`。

索引时提交的 `id` 会在后续 `result.matches` 中作为 `target_id` 返回。

## 2）提交搜索任务

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

预期响应：

```json
{
  "job_id": "<uuid>"
}
```

## 3）轮询任务结果

```bash
curl http://localhost:5000/search/<job_id>
```

常见状态：

- `pending`
- `running`
- `completed`（返回 `result`）
- `failed`（返回 `error`）

排序说明：

- 最终结果按 `identity` 降序排列。
- `identity` 并列时，按 `target_id` 升序稳定打破并列。
- 粗过滤中 Jaccard 并列时，先按索引目标序列 ID（`target_id`）升序确定顺序，再执行 `max_candidates` 截断。

示例：仅展示最终 `result.matches` 的并列排序（`identity` / `target_id`）：

```json
{
  "matches": [
    {"target_id": "a_target", "identity": 0.8},
    {"target_id": "z_target", "identity": 0.8}
  ]
}
```

该示例只说明最终匹配结果排序，不表示粗过滤阶段 Jaccard 并列时的截断示例。

## 4）查询索引数量

```bash
curl http://localhost:5000/search/index/stats
```

示例：

```json
{
  "total_sequences": 1
}
```

## 输入校验规则

- 仅允许氨基酸字符：`ACDEFGHIKLMNPQRSTVWY`
- 序列长度范围：`10` 到 `500`
- 序列会自动转为大写并移除空白

## 常见问题

- `422 Unprocessable Entity`：通常是字符非法或长度越界。
- `/search/{job_id}` 返回 `404`：任务 ID 不存在或已过期。
- 结果为空：可降低 `coarse_min_shared`、`coarse_jaccard` 阈值，或先补充索引数据。

## Python 调用示例

```python
import asyncio
from metanano.config import SearchConfig
from metanano.services.search_service import SearchService
from metanano.utils.kmer import generate_kmers


async def main() -> None:
    service = SearchService(SearchConfig())

    ref = "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
    service.index_sequence("db_001", ref, {"CDR3": "RDYRFDMGFDY"}, generate_kmers(ref, k=5))

    job_id = await service.submit_search([ref], include_alignment=False)
    while True:
        job = await service.get_job_status(job_id)
        if job and job.status.value in {"completed", "failed"}:
            print(job.status.value, job.result, job.error)
            break
        await asyncio.sleep(0.1)


asyncio.run(main())
```
