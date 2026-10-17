# NOVA Nanobody Filter

A high-performance nanobody sequence validation system for the NOVA Nanobody Challenge. This modular Python application provides comprehensive filtering for therapeutic nanobody candidates.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MPL--2.0-orange.svg)](LICENSE)

**Developed by [MetaNova Labs](https://www.metanova-labs.ai) and [Yalotein Biotech](https://yalotein.com)**

## Overview

The system validates nanobody sequences through three cascading filters:

```
Diversity → Nativeness → Developability → Passed
MMseqs2     IgBlast       TNP Red Regions + A3D mean/peak caps
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Diversity Filter** | MMseqs2 clustering, CDR mutation checks, historical similarity |
| **Nativeness Filter** | IMGT numbering, nativeness/humanness scoring |
| **Developability Filter** | TNP Red Regions and registered Aggrescan3D Rust mean/peak caps using the same model |
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

# Install external tools (MMseqs2, TNP, etc.)
bash install/install.sh

# Build the developability aggregation subfilter (requires Rust, Git, a C compiler and Make)
sh install/install-aggrescan3d.sh
export PATH="$PWD/.tools/bin:$PATH"
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
print(result.validation_status)
print(result.failed_filters)
print(result.details.get("developability", {}).get("aggrescan3d"))
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/validate` | POST | Validate single sequence |
| `/validate/batch` | POST | Validate multiple sequences |
| `/diversity/analyze` | POST | Diversity analysis |
| `/nativeness/analyze` | POST | Nativeness scoring |
| `/developability/analyze` | POST | Combined TNP and Aggrescan3D developability filtering |
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

### Nativeness (IgBlast)
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

### Aggrescan3D (whole VHH)

Within Developability, both inclusive caps must pass: `a3d_average <= -0.68002724866200` and `a3d_maximum <= 1.58023066762925`. This subfilter is enabled by default under `config.developability.aggrescan3d`. It requires the default scale, 10 Å radius and pinned FreeSASA 2.0.1 static method. Missing or incompatible scores fail Developability with an explicit error. See the [filter policy and configuration](docs/usage/aggrescan3d-rust.md).

## External Tools

| Tool | Purpose | Repository |
|------|---------|------------|
| MMseqs2 | Sequence clustering | [GitHub](https://github.com/soedinglab/MMseqs2) |
| AbNumber | IMGT numbering | [GitHub](https://github.com/prihoda/AbNumber) |
| IgBlast | Nativeness/humanness scoring | [NCBI](https://ftp.ncbi.nih.gov/blast/executables/igblast/release/) |
| promb | Humanness scoring | [GitHub](https://github.com/MSDLLCpapers/promb) |
| TNP | Developability profiling | [GitHub](https://github.com/oxpig/TNP) |
| Aggrescan3D Rust | Static whole-VHH aggregation filter using TNP's existing model | [Native scorer](tools/aggrescan3d-rs/README.md) |

Aggrescan3D method: Zambrano et al. (2015), *AGGRESCAN3D (A3D): server for prediction of aggregation properties of protein structures*, [doi:10.1093/nar/gkv359](https://doi.org/10.1093/nar/gkv359). See the [installation, filter policy, reusable functions and citation guide](docs/usage/aggrescan3d-rust.md).

## Documentation

- [Documentation Index](docs/README.md) - Technical guides, usage, dated changes, plans and verified lessons
- [Aggrescan3D Rust Integration](docs/usage/aggrescan3d-rust.md) - Registered filter, whole-VHH/region metrics, reusable functions, provenance and paper citation
- [Development Plans](docs/plans/README.md) - Current integration scope and durable verification state
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
