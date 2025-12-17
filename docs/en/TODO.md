# NOVA Nanobody Filter - TODO List

> Last Updated: 2025-12-17  
> Status Legend: ✅ Done | 🚧 In Progress | ⏳ Pending | ❌ Blocked

---

## Overview

This document tracks the implementation progress for the NOVA Nanobody Challenge Submission Filter System (MetaNano). The system validates nanobody sequences through three cascading filters: Diversity, Nativeness, and Developability.

---

## Tool Integration Workflow

For each external tool, we follow a systematic 3-phase approach:

1. **Investigate Usage** - Read GitHub/GitLab README, understand CLI/API, document input/output formats
2. **Implementation** - Implement hooks, controllers, and routes based on discovered I/O patterns
3. **Test** - Verify with curl commands and compare against expected CLI outputs

---

## 0. External Tool Integration 🚧

### 0.1 TNP (Therapeutic Nanobody Profiler) ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Investigate | Read TNP GitHub README | ✅ | [GitHub](https://github.com/oxpig/TNP) |
| Investigate | Document CLI usage pattern | ✅ | `TNP --name <name> --output <dir> --seq <sequence>` |
| Investigate | Document output format | ✅ | JSON: `TNP_Results_SingleSeqEntry_<name>.json` |
| Investigate | Map output fields to Red Region criteria | ✅ | L, L3, C, PSH, PPC, PNC, Flags |
| Implement | Create TNP wrapper in `utils/tnp_wrapper.py` | ✅ | CLI subprocess wrapper with TNPResult model |
| Implement | Parse JSON output to Pydantic model | ✅ | `TNPResult` in tnp_wrapper.py |
| Implement | Integrate with developability filter | ✅ | `developability.py` uses TNPWrapper |
| Test | Unit test with sample sequence | ✅ | Python direct test passed |
| Test | Curl test `/validate` endpoint | ✅ | API server tested (nativeness blocks, but developability works) |

**Sample CLI Command:**
```bash
TNP --name my_sequence --output my_sequence_output --seq QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS
```

**Sample Output:** `my_sequence_output/TNP_Results_SingleSeqEntry_my_sequence.json`
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

### 0.2 MMseqs2 (Sequence Clustering) ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Investigate | Read MMseqs2 GitHub README | ✅ | [GitHub](https://github.com/soedinglab/MMseqs2) |
| Investigate | Document CLI usage for clustering | ✅ | `mmseqs easy-cluster` command |
| Investigate | Document identity threshold parameter | ✅ | `--min-seq-id 0.98` |
| Investigate | Document output format (cluster TSV) | ✅ | Representative and member sequences (TSV) |
| Implement | Create MMseqs2 wrapper in `utils/mmseqs2_wrapper.py` | ✅ | CLI subprocess wrapper |
| Implement | Parse cluster output to Python dict | ✅ | Cluster ID → member sequences |
| Implement | Integrate with diversity filter | ✅ | `diversity.py` uses MMseqs2Wrapper |
| Test | Unit test with sample batch | ✅ | `test_mmseqs2.py` - 11 tests passed |
| Test | Curl test `/validate` with batch | ✅ | API integration verified |

**CLI Pattern:**
```bash
mmseqs easy-cluster input.fasta output tmp --min-seq-id 0.98
```

**Output Format (TSV):**
```
representative_seq	member_seq
seq_1	seq_1
seq_2	seq_2
seq_2	seq_0
```

---

### 0.3 abnumber (IMGT Numbering) ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Investigate | Read abnumber GitHub README | ✅ | [GitHub](https://github.com/prihoda/AbNumber) |
| Investigate | Document Python API usage | ✅ | `Chain` class and IMGT scheme |
| Investigate | Document CDR extraction methods | ✅ | `chain.cdr1_seq`, `chain.cdr2_seq`, `chain.cdr3_seq` |
| Investigate | Document numbering failure handling | ✅ | `ChainParseError` exception |
| Implement | Create abnumber wrapper in `utils/cdr_utils.py` | ✅ | `extract_cdrs()`, `count_cdr_mutations()` |
| Implement | Implement CDR extraction | ✅ | Returns dict with cdr1, cdr2, cdr3 |
| Implement | Implement mutation counting | ✅ | Compare against reference or heuristic |
| Implement | Integrate with nativeness filter | ✅ | `nativeness.py` uses cdr_utils |
| Test | Unit test with valid/invalid sequences | ✅ | `test_abnumber.py` - 15 tests passed |
| Test | Curl test `/validate` endpoint | ✅ | IMGT rejection verified |

**Python API:**
```python
from abnumber import Chain
chain = Chain(sequence, scheme='imgt')
cdr1 = chain.cdr1_seq  # GYTFTNYY
cdr2 = chain.cdr2_seq  # INPSNGGT
cdr3 = chain.cdr3_seq  # ARRDYRFDMGFDY
chain_type = chain.chain_type  # 'H' for heavy chain
```

---

### 0.4 AbnatiV v2 (Nativeness Scoring) ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Investigate | Read AbnatiV GitLab README | ✅ | [GitLab](https://gitlab.developers.cam.ac.uk/ch/sormanni/abnativ) |
| Investigate | Document Python API usage | ✅ | `abnativ_scoring()` from `abnativ.model.scoring_functions` |
| Investigate | Document output fields | ✅ | AbNatiV score (0-1), CDR scores, Framework score |
| Investigate | Document batch processing | ✅ | BioPython SeqRecord list, batch_size param |
| Implement | Create AbnatiV wrapper | ✅ | Integration ready in nativeness.py |
| Implement | Parse scores to result | ✅ | DataFrame with AbNatiV, CDR-1, CDR-2, CDR-3 |
| Implement | Integrate with nativeness filter | ✅ | `nativeness.py` (when models available) |
| Test | Unit test with sample sequences | ✅ | `test_abnativ.py` - 12 tests passed |
| Test | Model download | ✅ | `abnativ init` completed (VHH, VHH2, VH, VH2, VL2, etc.) |

**Python API:**
```python
from abnativ.model.scoring_functions import abnativ_scoring
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq

record = SeqRecord(Seq(sequence), id="vhh_seq")
df_scores, df_profiles = abnativ_scoring(
    model_type='VHH',  # or VHH2 for v2
    seq_records=[record],
    mean_score_only=True,
    do_align=True,
    is_VHH=True,
    verbose=False
)
# df_scores columns: ID, AbNatiV, CDR-1, CDR-2, CDR-3, Framework
# Threshold: 0.8 separates native from non-native
```

---

### 0.5 promb (OASis Humanness - Optional) ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Investigate | Read promb GitHub README | ✅ | [GitHub](https://github.com/MSDLLCpapers/promb) |
| Investigate | Document Python API usage | ✅ | `init_db()`, `run_promb()`, DB methods |
| Investigate | Document reference databases | ✅ | "human-oas", "human-swissprot" |
| Investigate | Document output format | ✅ | Content (0-1), Average mutations |
| Implement | Create promb integration | ✅ | Direct API usage in nativeness |
| Implement | Integrate as optional cross-check | ✅ | `nativeness.py` can use promb |
| Test | Unit test with sample sequences | ✅ | `test_promb.py` - 16 tests passed |
| Test | Curl test `/validate` with promb enabled | ✅ | API integration verified |

**Python API:**
```python
import promb

db = promb.init_db("human-oas", verbose=False)
peptides = db.chop_seq_peptides(sequence)
content = sum(db.contains(p) for p in peptides) / len(peptides)  # 0.71
avg_mutations = db.compute_average_mutations(sequence)  # 0.47
```

---

### 0.6 datasketch (MinHash Similarity) ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Investigate | Read datasketch GitHub README | ✅ | [GitHub](https://github.com/ekzhu/datasketch) |
| Investigate | Document WeightedMinHash usage | ✅ | For Jaccard similarity estimation |
| Investigate | Document LSH for fast lookup | ✅ | `MinHashLSH` for threshold queries |
| Investigate | Document k-mer weighting strategy | ✅ | k=5, weighted by occurrence count |
| Implement | Create MinHash wrapper in `utils/similarity.py` | ✅ | `weighted_minhash()`, `weighted_jaccard()` |
| Implement | Implement k-mer index builder | ✅ | `utils/kmer.py`: `generate_kmers()`, `build_kmer_index()` |
| Implement | Integrate with diversity filter | ✅ | `diversity.py` uses similarity functions |
| Test | Unit test with similar sequences | ✅ | `test_datasketch.py` - 18 tests passed |
| Test | Curl test `/validate` endpoint | ✅ | Similarity rejection verified |

**Python API:**
```python
from datasketch import MinHash

mh = MinHash(num_perm=128)
for kmer in kmers:
    mh.update(kmer.encode('utf8'))

# Similarity estimation
similarity = mh1.jaccard(mh2)  # 1.0 for identical, 0.0 for completely different
```

---

### 0.7 Async/Semaphore Concurrency Management ✅

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| Design | Define async concurrency strategy | ✅ | Semaphore-based rate limiting |
| Design | Identify concurrency bottlenecks | ✅ | TNP, MMseqs2, AbnatiV, promb |
| Implement | Add `AsyncConfig` to `config.py` | ✅ | 8 configurable parameters |
| Implement | `max_concurrent_validations` (default: 10) | ✅ | Global validation semaphore |
| Implement | `max_concurrent_tnp` (default: 4) | ✅ | TNP subprocess limit |
| Implement | `max_concurrent_mmseqs2` (default: 2) | ✅ | MMseqs2 clustering limit |
| Implement | `max_concurrent_abnativ` (default: 4) | ✅ | AbnatiV scoring limit (GPU-aware) |
| Implement | `max_concurrent_promb` (default: 4) | ✅ | promb calculation limit |
| Implement | `batch_size` (default: 50) | ✅ | Async batch processing size |
| Implement | `task_timeout` (default: 300s) | ✅ | Per-task timeout |
| Implement | `queue_size` (default: 1000) | ✅ | Task queue capacity |
| Implement | Convert all services to async | ✅ | Filters, validators, wrappers |
| Implement | GPU scheduler (`gpu_scheduler.py`) | ✅ | In-memory scheduler with load balancing |
| Implement | Async service layer (`services/`) | ✅ | DiversityService, NativenessService, DevelopabilityService |
| Implement | Individual service routes | ✅ | `/diversity/*`, `/nativeness/*`, `/developability/*`, `/services/*` |
| Implement | Async pipeline (`validate_async`) | ✅ | Concurrent validation with semaphores |
| Test | Verify semaphore limiting | ⏳ | Concurrent request tests |

**Async Config Parameters:**
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

**Semaphore Usage Pattern:**
```python
import asyncio
from metanano.config import Config

config = Config()
tnp_semaphore = asyncio.Semaphore(config.async_config.max_concurrent_tnp)

async def run_tnp_async(sequence: str):
    async with tnp_semaphore:
        # Run TNP in thread pool to avoid blocking
        return await asyncio.to_thread(run_tnp_sync, sequence)
```

**GPU Scheduler Configuration:**
```python
from metanano.config import Config

config = Config()
gpu_cfg = config.async_config.gpu_scheduler
gpu_cfg.enabled                      # True (enable GPU scheduling)
gpu_cfg.auto_detect                  # True (auto-detect GPUs)
gpu_cfg.scheduling_strategy          # "least_loaded" | "round_robin" | "memory_aware"
gpu_cfg.default_max_concurrent_per_gpu  # 2
gpu_cfg.queue_max_size               # 500
gpu_cfg.task_timeout                 # 600.0s
gpu_cfg.health_check_interval        # 30.0s
gpu_cfg.memory_threshold_percent     # 90.0%
```

**GPU Scheduler Usage:**
```python
from metanano.utils.gpu_scheduler import get_gpu_scheduler

scheduler = get_gpu_scheduler(config.async_config.gpu_scheduler)
await scheduler.initialize()

# Option 1: Manual acquire/release
gpu_index = await scheduler.acquire_gpu(task_id="scoring_001")
try:
    result = await score_on_gpu(sequence, gpu_index)
finally:
    scheduler.release_gpu(gpu_index, task_id="scoring_001")

# Option 2: Automatic with context (recommended)
result = await scheduler.run_on_gpu(score_function, sequence)

# Check status
status = scheduler.get_status()
# {"enabled": True, "total_gpus": 2, "available_gpus": 1, "gpus": {...}}
```

---

## 1. Infrastructure Setup

### 1.1 Installation & Environment ✅

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Create conda environment file (full) | ✅ | - | `install/environment.yml` |
| Create conda environment file (minimal) | ✅ | - | `install/environment-minimal.yml` |
| Create pip requirements (full) | ✅ | - | `install/requirements.txt` |
| Create pip requirements (minimal) | ✅ | - | `install/requirements-minimal.txt` |
| Create installation script | ✅ | - | `install/install.sh` with mamba/uv support |
| Document installation process | ✅ | - | In README.md |

---

## 2. Core Modules (metanano/)

### 2.1 Project Structure ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create metanano package | ✅ | P0 | `metanano/__init__.py` |
| Set up `app.py` entry point | ✅ | P0 | FastAPI application |
| Create `config.py` configuration module | ✅ | P0 | Pydantic models for all configs |
| Create `pipeline.py` orchestrator | ✅ | P0 | ValidationPipeline class |

### 2.2 Filters Module (`metanano/filters/`) ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `filters/__init__.py` | ✅ | P0 | Module initialization |
| Implement `diversity.py` | ✅ | P0 | MMseqs2 + k-mer clustering |
| Implement `nativeness.py` | ✅ | P0 | abnumber + AbnatiV v2 integration |
| Implement `developability.py` | ✅ | P0 | TNP profiler integration |

### 2.3 Validators Module (`metanano/validators/`) ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `validators/__init__.py` | ✅ | P0 | Module initialization |
| Implement `diversity_validator.py` | ✅ | P0 | Batch + historical comparison |
| Implement `nativeness_validator.py` | ✅ | P0 | IMGT numbering + scoring |
| Implement `developability_validator.py` | ✅ | P0 | Red Region criteria validation |

### 2.4 Models Module (`metanano/models/`) ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `models/__init__.py` | ✅ | P0 | Module initialization |
| Implement `sequence.py` | ✅ | P0 | Sequence data model with validation |
| Implement `validation_result.py` | ✅ | P0 | Structured validation response model |

### 2.5 Utilities Module (`metanano/utils/`) ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `utils/__init__.py` | ✅ | P0 | Module initialization |
| Implement `similarity.py` | ✅ | P0 | Weighted MinHash + k-mer utilities |
| Implement `kmer.py` | ✅ | P0 | K-mer index generation (k=5,6) |
| Implement `cdr_utils.py` | ✅ | P0 | CDR extraction and mutation counting |
| Implement `mmseqs2_wrapper.py` | ✅ | P0 | CLI wrapper for MMseqs2 |

### 2.6 Routes Module (`metanano/routes/`) ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `routes/__init__.py` | ✅ | P0 | Module initialization |
| Implement `submission_routes.py` | ✅ | P0 | POST /submit endpoint |
| Implement `validation_routes.py` | ✅ | P0 | POST /validate, /validate/batch endpoints |
| Implement `health_routes.py` | ✅ | P0 | GET /health endpoint |
| Implement `diversity_routes.py` | ✅ | P1 | Diversity service endpoints |
| Implement `nativeness_routes.py` | ✅ | P1 | Nativeness service endpoints |
| Implement `developability_routes.py` | ✅ | P1 | Developability service endpoints |
| Implement `service_routes.py` | ✅ | P1 | GPU/semaphore status endpoints |

### 2.7 Services Module (`metanano/services/`) ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `services/__init__.py` | ✅ | P1 | Module initialization |
| Implement `async_manager.py` | ✅ | P1 | Centralized semaphore management |
| Implement `diversity_service.py` | ✅ | P1 | Async diversity filter service |
| Implement `nativeness_service.py` | ✅ | P1 | Async nativeness filter service |
| Implement `developability_service.py` | ✅ | P1 | Async developability filter service |

---

## 3. Filter Implementation Refinements

### 3.1 Diversity Filter 🚧

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| MMseqs2 clustering (identity ≥ 0.98) | ✅ | P0 | Basic implementation done |
| CDR mutation counting (combined ≥ 2) | ✅ | P0 | Using abnumber |
| CDR3 mutation check (≥ 1) | ✅ | P0 | Implemented |
| K-mer index builder | ✅ | P0 | k=5 or k=6 configurable |
| Plan A: Weighted MinHash (Jaccard < 0.9) | ✅ | P1 | Using datasketch |
| Plan B: Top 50 leaderboard comparison | ✅ | P0 | Preferred strategy |
| Historical sequence database integration | ⏳ | P1 | Needs database setup |

### 3.2 Nativeness Filter 🚧

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| abnumber IMGT numbering integration | ✅ | P0 | Chain class wrapper |
| AbnatiV v2 nativeness scoring (≥ 0.80) | ✅ | P0 | predict_nanobody wrapper |
| AbnatiV v2 humanness scoring (≥ 0.75) | ✅ | P0 | Implemented |
| promb OASis integration (optional) | ✅ | P2 | Configurable via promb.enabled |
| Async batch processing with semaphores | ✅ | P1 | AsyncConfig in config.py |
| GPU acceleration (when available) | ⏳ | P2 | CUDA-aware concurrency limits |

### 3.3 Developability Filter 🚧

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| TNP Profiler integration | ✅ | P0 | profile_nanobody wrapper |
| Total CDR length check (L < 20 OR L > 39) | ✅ | P0 | Red Region criteria |
| CDR3 length check (L3 < 5 OR L3 > 23) | ✅ | P0 | Red Region criteria |
| CDR3 compactness (C < 0.56 OR C > 1.61) | ✅ | P0 | Red Region criteria |
| Surface hydrophobic patches (PSH range) | ✅ | P0 | PSH < 73.4 OR PSH > 155.47 |
| Positive charge patches (PPC > 1.18) | ✅ | P0 | Red Region criteria |
| Negative charge patches (PNC > 1.88) | ✅ | P0 | Red Region criteria |

---

## 4. Testing

### 4.1 Unit Tests (`metanano/tests/`) ⏳

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create `tests/__init__.py` | ✅ | P1 | Module initialization |
| Implement `test_diversity.py` | ⏳ | P1 | Diversity filter tests |
| Implement `test_nativeness.py` | ⏳ | P1 | Nativeness filter tests |
| Implement `test_developability.py` | ⏳ | P1 | Developability filter tests |
| Implement `test_submission.py` | ⏳ | P1 | Submission route tests |
| Implement `test_validation.py` | ⏳ | P1 | Validation pipeline tests |
| Implement `test_utils.py` | ⏳ | P1 | Utility function tests |

### 4.2 Integration Tests ⏳

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| End-to-end pipeline test | ⏳ | P1 | Full validation flow |
| API endpoint integration tests | ⏳ | P1 | HTTP request/response validation |
| Performance benchmarking | ⏳ | P2 | Batch processing throughput |

---

## 5. Documentation

### 5.1 Code Documentation ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Add module-level docstrings (bilingual) | ✅ | P1 | English + Chinese |
| Add function docstrings | ✅ | P1 | Parameters, returns, examples |
| Add Pydantic field descriptions | ✅ | P1 | OpenAPI visibility |
| Create API usage examples | ✅ | P2 | curl commands, Python snippets |

### 5.2 Project Documentation ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| English README.md | ✅ | P0 | `docs/en/README.md` |
| Chinese README.md | ✅ | P0 | `docs/cn/README.md` |
| Create TODO.md (English) | ✅ | P0 | This file |
| Create TODO.md (Chinese) | ✅ | P0 | `docs/cn/TODO.md` |
| Create BUGS.md | ⏳ | P1 | Bug tracking |

---

## 6. Deployment & DevOps

### 6.1 Containerization ⏳

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Create Dockerfile | ⏳ | P1 | Multi-stage build |
| Create docker-compose.yml | ⏳ | P1 | Local development |
| Create .env.example | ⏳ | P1 | Environment template |
| GPU support in container | ⏳ | P2 | CUDA runtime |

### 6.2 CI/CD ⏳

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Set up GitHub Actions | ⏳ | P2 | Automated testing |
| Linting workflow (ruff/black) | ⏳ | P2 | Code quality |
| Type checking workflow (mypy) | ⏳ | P2 | Type safety |

---

## 7. Database Integration ⏳

### 7.1 Data Persistence ⏳

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Design database schema | ⏳ | P1 | Submissions, results, users |
| Implement submission storage | ⏳ | P1 | Save validated sequences |
| Historical sequence retrieval | ⏳ | P1 | For diversity comparison |
| Leaderboard top-N query | ⏳ | P1 | Plan B comparison |

---

## 8. Future Enhancements

### 8.1 Performance Optimizations ✅

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Async batch processing with semaphores | ✅ | P1 | Concurrent validation with limits |
| Async services (all filters/validators) | ✅ | P1 | `services/` module with async methods |
| Async pipeline (validate_async) | ✅ | P1 | Supports both sync and async |
| Individual service routes | ✅ | P1 | Per-filter API endpoints |
| Redis caching for k-mer indices | ⏳ | P3 | Reduce computation |
| GPU-accelerated similarity search | ⏳ | P3 | FAISS integration |

### 8.2 Feature Extensions ⏳

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Web UI dashboard | ⏳ | P3 | Visualization of results |
| Batch upload support | ⏳ | P3 | CSV/FASTA file processing |
| Webhook notifications | ⏳ | P3 | Async result delivery |

---

## Priority Definitions

| Priority | Description |
|----------|-------------|
| P0 | Critical - Must have for MVP |
| P1 | High - Important for production readiness |
| P2 | Medium - Nice to have |
| P3 | Low - Future enhancement |

---

## Implementation Summary

### Completed ✅
- Full project structure under `metanano/`
- All three filters implemented (diversity, nativeness, developability)
- All validators implemented
- All data models with Pydantic validation
- All API routes (submit, validate, health)
- All utility functions (k-mer, similarity, CDR, MMseqs2)
- Comprehensive bilingual documentation
- TNP tool investigation (CLI pattern, output format documented)

### Completed ✅
- External tool integration following 3-phase workflow:
  - **TNP**: Investigation ✅ → Implementation ✅ → Testing ✅ (12 tests)
  - **MMseqs2**: Investigation ✅ → Implementation ✅ → Testing ✅ (11 tests)
  - **abnumber**: Investigation ✅ → Implementation ✅ → Testing ✅ (15 tests)
  - **AbnatiV v2**: Investigation ✅ → Implementation ✅ → Testing ✅ (12 tests)
  - **promb**: Investigation ✅ → Implementation ✅ → Testing ✅ (16 tests)
  - **datasketch**: Investigation ✅ → Implementation ✅ → Testing ✅ (18 tests)
- **Total: 84 tests passed** in `metanano/tests/tools/`
- **Async/Semaphore Concurrency**: `AsyncConfig` added to `config.py` with 8 hyperparameters:
  - `max_concurrent_validations`, `max_concurrent_tnp`, `max_concurrent_mmseqs2`
  - `max_concurrent_abnativ`, `max_concurrent_promb`
  - `batch_size`, `task_timeout`, `queue_size`
- **GPU Scheduler**: In-memory scheduler in `utils/gpu_scheduler.py` with:
  - Real-time GPU usage tracking (queue + active tasks)
  - Load-balancing strategies: `round_robin`, `least_loaded`, `memory_aware`
  - GPU registration and dynamic enable/disable
  - Memory threshold monitoring and health checks

### In Progress 🚧
- Database integration for historical sequences

### Pending ⏳
- Unit and integration tests
- Docker containerization
- CI/CD pipeline
- GPU acceleration optimizations

### New Routes Added ✅
- `/diversity/analyze` - Full diversity analysis
- `/diversity/batch-check` - MMseqs2 batch diversity
- `/diversity/cdr-mutations` - CDR mutation check
- `/nativeness/analyze` - Full nativeness analysis
- `/nativeness/imgt-number` - IMGT numbering
- `/nativeness/scores` - Nativeness/humanness scores
- `/developability/analyze` - Full developability analysis
- `/developability/tnp-profile` - TNP profiling
- `/developability/analyze-batch` - Batch analysis
- `/services/status` - Service manager status
- `/services/gpu` - GPU scheduler status
- `/services/gpu/control` - GPU enable/disable
- `/validate/batch` - Batch validation

---

## Notes

- All filter thresholds are configurable via `metanano/config.py`
- Filters are applied in sequence: Diversity → Nativeness → Developability
- Early termination on filter failure to optimize performance
- All docstrings and comments are bilingual (English + Chinese)
- FastAPI provides automatic OpenAPI documentation at `/docs`
- **Tool Integration Workflow**: Investigate → Implement → Test (with curl verification)
- **Async Concurrency**: All services use `asyncio.Semaphore` for rate limiting
- **Semaphore Config**: `config.async_config.*` controls concurrent task limits
- **GPU Scheduler**: `config.async_config.gpu_scheduler.*` for GPU-bound task management
- **Scheduling Strategies**: `least_loaded` (default), `round_robin`, `memory_aware`
