# NOVA Nanobody Filter

A high-performance nanobody sequence validation system for the NOVA Nanobody Challenge. This modular Python application provides comprehensive filtering for therapeutic nanobody candidates.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MPL--2.0-orange.svg)](LICENSE)

**Developed by [MetaNova Labs](https://www.metanova-labs.ai) and [Yalotein Biotech](https://yalotein.com)**

## Overview

The system validates nanobody sequences through a three-stage pipeline:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  1. Diversity   │ -> │  2. Nativeness  │ -> │ 3. Developability│
│     Filter      │    │     Filter      │    │     Filter      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
     MMseqs2              AbnatiV v2              TNP Profiler
     CDR mutations        IMGT numbering          Red region check
     K-mer similarity     Humanness score         Surface patches
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Diversity Filter** | MMseqs2 clustering, CDR mutation checks, historical similarity |
| **Nativeness Filter** | IMGT numbering, nativeness/humanness scoring (AbnatiV v2) |
| **Developability Filter** | TNP profiling, red region validation, charge patch analysis |
| **Async Architecture** | Semaphore-controlled concurrency, GPU scheduler |
| **REST API** | FastAPI endpoints with OpenAPI documentation |

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/NOVA-nanobody-filter.git
cd NOVA-nanobody-filter

# Create and activate conda environment
conda create -n metanano python=3.12 -y
conda activate metanano

# Install dependencies
pip install -r install/requirements.txt

# Install external tools (MMseqs2, TNP, AbnatiV, etc.)
bash install/install.sh
```

### Run the Server

```bash
# Start the FastAPI server
python -m uvicorn metanano.app:app --reload --port 5000
```

Visit http://localhost:5000/docs for interactive API documentation.

### Basic Usage

**Validate a sequence via API:**

```bash
curl -X POST http://localhost:5000/validate \
  -H "Content-Type: application/json" \
  -d '{"sequence": "QVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCARDLILGNFDYWGQGTLVTVSS"}'
```

**Python usage:**

```python
from metanano.pipeline import ValidationPipeline
from metanano.config import Config

config = Config()
pipeline = ValidationPipeline(config)

result = pipeline.validate(sequence)
print(f"Passed: {result.passed}")
print(f"Diversity: {result.diversity_passed}")
print(f"Nativeness: {result.nativeness_passed}")
print(f"Developability: {result.developability_passed}")
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/validate` | POST | Validate single sequence |
| `/validate/batch` | POST | Validate multiple sequences |
| `/diversity/analyze` | POST | Diversity analysis |
| `/nativeness/analyze` | POST | Nativeness scoring |
| `/developability/analyze` | POST | Developability profiling |
| `/services/gpu` | GET | GPU scheduler status |

## Sequence Search Guide

The project now includes an async sequence-search subsystem designed for fast retrieval of similar nanobody candidates.

### What it does

- Uses a **two-stage coarse filter** (shared k-mers + Jaccard) to quickly narrow candidates.
- Runs **fine alignment** with `parasail` (SIMD) and BioPython fallback.
- Supports **async job execution**: submit once, poll by `job_id`.
- Exposes indexing and search routes through `/search/*`.

### Search architecture (high level)

1. **IndexManager** stores in-memory sequence records and k-mer inverted index.
2. **SearchEngine** orchestrates coarse filter + fine alignment + CDR comparison.
3. **JobManager** tracks async lifecycle: `pending -> running -> completed/failed`.
4. **SearchService** runs searches in background tasks with semaphore concurrency control.
5. **Search routes** expose HTTP endpoints for indexing, submit, and status polling.

### Search API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Submit async search job, returns `job_id` (HTTP 202) |
| `/search/{job_id}` | GET | Get job status and result payload |
| `/search/index` | POST | Index a sequence into in-memory search database (HTTP 201) |
| `/search/index/stats` | GET | Return current indexed sequence count |

### Quick API walkthrough

1) **Index a reference sequence**

```bash
curl -X POST http://localhost:5000/search/index \
  -H "Content-Type: application/json" \
  -d '{
    "id": "db_001",
    "sequence": "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
  }'
```

2) **Submit a search job**

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

3) **Poll for completion**

```bash
curl http://localhost:5000/search/<job_id>
```

Example status payload (completed):

```json
{
  "job_id": "<uuid>",
  "status": "completed",
  "created_at": 1739170000.123,
  "completed_at": 1739170000.845,
  "result": [
    {
      "query_sequence": "...",
      "matches": [
        {
          "target_id": "db_001",
          "identity": 0.93,
          "tier": "high"
        }
      ]
    }
  ],
  "error": null
}
```

### Python usage example

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

### Input validation rules (search routes)

- Sequences are uppercased and whitespace-normalized.
- Valid amino acids only: `ACDEFGHIKLMNPQRSTVWY`.
- Accepted length range on search/index endpoints: `10-500`.

### Operational notes

- Search index is **in-memory only** (no disk persistence in v1).
- Restarting the service clears indexed sequences.
- Use `/search/index/stats` to monitor current index size.

### Troubleshooting

- `422 Unprocessable Entity`: invalid sequence characters or length.
- `404` on `/search/{job_id}`: job expired/not found.
- Slow search results: reduce `include_alignment`, tighten coarse filter thresholds.

## Filter Thresholds

### Diversity (MMseqs2 + CDR)
- Global cluster identity: ≥ 98%
- CDR combined mutations: ≥ 2
- CDR3 mutations: ≥ 1

### Nativeness (AbnatiV v2)
- Nativeness score: ≥ 0.80
- Humanness score: ≥ 0.75
- IMGT numbering: required

### Developability (TNP Red Regions)
| Property | Valid Range |
|----------|-------------|
| Total CDR Length | 20 - 39 |
| CDR3 Length | 5 - 23 |
| CDR3 Compactness | 0.56 - 1.61 |
| Surface Hydrophobic Patches | 73.4 - 155.47 |
| Positive Charge Patches | ≤ 1.18 |
| Negative Charge Patches | ≤ 1.88 |

## External Tools

| Tool | Purpose | Repository |
|------|---------|------------|
| MMseqs2 | Sequence clustering | [GitHub](https://github.com/soedinglab/MMseqs2) |
| AbNumber | IMGT numbering | [GitHub](https://github.com/prihoda/AbNumber) |
| AbnatiV v2 | Nativeness scoring | [GitLab](https://gitlab.developers.cam.ac.uk/ch/sormanni/abnativ) |
| promb | Humanness scoring | [GitHub](https://github.com/MSDLLCpapers/promb) |
| TNP | Developability profiling | [GitHub](https://github.com/oxpig/TNP) |

## Documentation

- [English Documentation](docs/en/README.md) - Full technical documentation
- [Search Quickstart](docs/en/SEARCH_QUICKSTART.md) - Fast start for indexing and async search
- [Real-Data Search Repro](docs/en/SEARCH_REAL_DATA_REPRO.md) - Reproduce E2E search test with public VHH dataset
- [真实数据搜索复现](docs/cn/SEARCH_REAL_DATA_REPRO.md) - 使用公开 VHH 数据集复现实验
- [中文文档](docs/cn/README.md) - 完整技术文档
- [搜索快速上手](docs/cn/SEARCH_QUICKSTART.md) - 索引与异步搜索快速指南
- [TODO / Development Plan](docs/en/TODO.md) - Implementation status

## Project Structure

```
NOVA-nanobody-filter/
├── metanano/
│   ├── app.py              # FastAPI application
│   ├── config.py           # Configuration
│   ├── pipeline.py         # Validation pipeline
│   ├── filters/            # Sync filter implementations
│   ├── services/           # Async service wrappers
│   ├── routes/             # API route handlers
│   └── utils/              # Utilities (GPU scheduler, wrappers)
├── docs/
│   ├── en/                 # English docs
│   └── cn/                 # Chinese docs
├── install/                # Installation scripts
└── requirements.txt
```

## License

This project is licensed under the Mozilla Public License Version 2.0 (MPL-2.0) - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please read the documentation and submit pull requests for any improvements.

---

*Built for the NOVA Nanobody Challenge by MetaNova Labs and Yalotein Biotech*
