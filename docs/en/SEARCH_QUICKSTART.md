# Search Quickstart

This guide shows the fastest path to use the sequence search feature in NOVA Nanobody Filter.

## What You Get

- In-memory sequence indexing (`/search/index`)
- Async search jobs (`/search` -> `job_id`)
- Polling-based status/results (`/search/{job_id}`)
- Index metrics (`/search/index/stats`)

## Prerequisites

1. Start the API server:

```bash
python -m uvicorn metanano.app:app --reload --port 5000
```

2. Confirm service health:

```bash
curl http://localhost:5000/health
```

## 1) Index a Reference Sequence

```bash
curl -X POST http://localhost:5000/search/index \
  -H "Content-Type: application/json" \
  -d '{
    "id": "db_001",
    "sequence": "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS",
    "cdrs": {"CDR3": "RDYRFDMGFDY"}
  }'
```

Expected: HTTP `201`.

The indexed `id` is returned later as `target_id` in `result.matches`.

## 2) Submit a Search Job

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

Expected response:

```json
{
  "job_id": "<uuid>"
}
```

## 3) Poll for Results

```bash
curl http://localhost:5000/search/<job_id>
```

Typical status progression:

- `pending`
- `running`
- `completed` (contains `result`)
- `failed` (contains `error`)

Ranking note:

- Final results are sorted by `identity` descending.
- Ties are resolved deterministically by `target_id` ascending.
- Coarse-filter Jaccard ties are deterministically resolved by indexed target sequence ID (`target_id`) before `max_candidates` truncation.

Example: final `result.matches` tie ordering (`identity` / `target_id`):

```json
{
  "matches": [
    {"target_id": "a_target", "identity": 0.8},
    {"target_id": "z_target", "identity": 0.8}
  ]
}
```

This example shows final match ordering only; it does not illustrate coarse Jaccard tie truncation.

## 4) Check Index Size

```bash
curl http://localhost:5000/search/index/stats
```

Example:

```json
{
  "total_sequences": 1
}
```

## Request Rules

- Valid amino acids only: `ACDEFGHIKLMNPQRSTVWY`
- Sequence length: `10` to `500`
- Sequences are normalized to uppercase with whitespace removed

## Troubleshooting

- `422 Unprocessable Entity`: Invalid sequence format or length.
- `404` on `/search/{job_id}`: Unknown/expired job ID.
- Empty matches: loosen coarse thresholds (`coarse_min_shared`, `coarse_jaccard`) or index more relevant sequences.

## Python Example

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
