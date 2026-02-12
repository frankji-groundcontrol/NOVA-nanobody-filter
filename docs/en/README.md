# NOVA Nanobody Challenge - Submission Filter System

Implementation plan for a modular nanobody challenge submission system in Python. The goal is to build a clean, modular application that can scale well while keeping things logically separated.

## Related Docs

- [Search Quickstart](SEARCH_QUICKSTART.md) - One-page guide for indexing, submitting, and polling search jobs
- [中文搜索快速上手](../cn/SEARCH_QUICKSTART.md) - Chinese search quickstart
- [Search Performance Benchmarks](#12-search-performance-benchmarks) - Tier 1 and Tier 2 search benchmark results on real data
- [Search Architecture](SEARCH_ARCHITECTURE.md) - How sequence search works, all parameters, and nanobody duplicate detection tuning

### Search Ordering Note

- Search result ranking is deterministic: primary sort is alignment identity (descending), tie-break is `target_id` (ascending).
- Coarse-filter candidate ties at equal Jaccard are deterministically resolved by indexed target sequence ID (`target_id`) before `max_candidates` truncation.

---

## **1. Functionalities**

### **1.1 Diversity Filter - Creativity Enforcement**

* **Purpose:** Ensures that nanobody sequences submitted by the miners are diverse, preventing the submission of very similar sequences.

#### **1.1.1 Diversity Within Submission Batch**

| Parameter | Threshold | Description |
|-----------|-----------|-------------|
| `global_cluster_identity` | >= 0.98 | MMseqs2 clustering to eliminate internal near-duplicates |
| `cdrs_combined_mutations` | >= 2 | Minimum mutations across all CDRs combined |
| `cdr3_mutations` | >= 1 | Minimum mutations in CDR3 region |

* **Core Operations:**
  * **MMseqs2 clustering:** Identify and remove sequences that share >= 98% similarity globally.
  * **Mutation checks:** Enforce at least 2 mutations across all CDRs combined (`cdrs_combined_mutations >= 2`), and at least 1 mutation in CDR3 (`cdr3_mutations >= 1`).

#### **1.1.2 Diversity Against Previous Submissions**

* **K-mer Index:** Build a k-mer index (k=5 or k=6) for current filtered sequences.

* **Comparison Strategies:**

  | Plan | Strategy | Threshold |
  |------|----------|-----------|
  | **Plan A (Baseline)** | Weighted MinHash against all historical submissions | Jaccard similarity < 0.9 |
  | **Plan B (Preferred)** | Compare only against top 50 leaderboard sequences | `current_top_n = 50` |

  * **Plan B Rationale:** Encourages optimization and novelty by focusing comparison on top-performing sequences.

* **Post-Comparison:** Combine matched hits and re-run internal batch filter to enforce novelty post-reuse.

---

### **1.2 Nativeness Filter - Nanobody Validity**

* **Purpose:** Ensure the submitted sequence is a valid nanobody (VHH) and can be humanized properly.

#### **1.2.1 Scoring Thresholds**

| Metric | Threshold | Tool |
|--------|-----------|------|
| IMGT Numbering | Successfully numbered | abnumber |
| Nativeness Score | >= 0.80 | AbnatiV v2 |
| Humanness Score | >= 0.75 | AbnatiV v2 |

* **Core Operations:**
  * **abnumber:** Keep only sequences successfully numbered under IMGT schema.
  * **AbnatiV v2:** 
    * Nativeness threshold: `nativeness_score >= 0.80`
    * Humanness threshold: `humanness_score >= 0.75`
  * **Optional Cross-Check:** Validate humanness with [promb](https://github.com/MSDLLCpapers/promb) (OASis score) for additional verification.

---

### **1.3 Developability Filter - Therapeutic Readiness**

* **Purpose:** Ensure the sequence is viable as a therapeutic nanobody.

* **Application Order:** Apply TNP (Therapeutic Nanobody Profiler) after passing diversity and nativeness filters.

#### **1.3.1 Red Region Criteria (July 2025)**

**REJECT** sequences if ANY of the following Red Region criteria are triggered:

| Property | Parameter | Valid Range | Red Region (REJECT if) |
|----------|-----------|-------------|------------------------|
| Total CDR Length | L | 20 ≤ L ≤ 39 | L < 20 OR L > 39 |
| CDR3 Length | L3 | 5 ≤ L3 ≤ 23 | L3 < 5 OR L3 > 23 |
| CDR3 Compactness | C | 0.56 ≤ C ≤ 1.61 | C < 0.56 OR C > 1.61 |
| Surface Hydrophobic Patches | PSH | 73.4 ≤ PSH ≤ 155.47 | PSH < 73.4 OR PSH > 155.47 |
| Positive Charge Patches | PPC | PPC ≤ 1.18 | PPC > 1.18 |
| Negative Charge Patches | PNC | PNC ≤ 1.88 | PNC > 1.88 |

* **Core Operations:**
  * **TNP Profiling:** Evaluate the sequence's developability based on CDR length, surface hydrophobicity, charge patches, and compactness.
  * **Property validation:** If ANY property falls into the Red Region, the sequence is **rejected/dumped**.
  * **Pass condition:** Sequence passes only if ALL properties are within their valid ranges.

---

### **1.4 Sequence Validation Pipeline**

* **Purpose:** Integrate all checks and apply them in the correct sequence for efficient validation.
* **Core Operations:**
  * Chain filters in order: **Diversity → Nativeness → Developability**
  * Early termination: Stop processing if any filter fails
  * Provide detailed feedback and return the validation status for each submission

---

## **2. File Structure**

### **Root Project Structure**

```
NOVA-nanobody-filter/
├── README.md                   # Project overview (links to docs)
├── LICENSE                     # License file
├── docs/                       # Documentation
│   ├── en/
│   │   ├── README.md           # English documentation
│   │   ├── TODO.md             # English task list
│   │   └── BUGS.md             # English bug tracking
│   └── cn/
│       ├── README.md           # Chinese documentation
│       ├── TODO.md             # Chinese task list
│       └── BUGS.md             # Chinese bug tracking
├── install/                    # Installation scripts and configs
│   ├── install.sh              # Main installation script
│   ├── environment.yml         # Full conda environment
│   ├── environment-minimal.yml # Minimal conda environment
│   ├── requirements.txt        # Full pip dependencies
│   └── requirements-minimal.txt # Minimal pip dependencies
└── metanano/                   # Main application package
    ├── __init__.py             # Package initialization, exports Config & ValidationPipeline
    ├── app.py                  # FastAPI application entry point
    ├── config.py               # Pydantic configuration models
    ├── pipeline.py             # Validation pipeline orchestrator
    ├── filters/                # Filter implementations (synchronous)
    │   ├── __init__.py
    │   ├── diversity.py        # Diversity filter (MMseqs2, k-mer, mutations)
    │   ├── nativeness.py       # Nativeness filter (abnumber, AbnatiV)
    │   └── developability.py   # Developability filter (TNP, Red Region)
    ├── services/               # Async service layer (wraps filters)
    │   ├── __init__.py
    │   ├── async_manager.py    # Centralized async manager with semaphores
    │   ├── diversity_service.py    # Async diversity operations
    │   ├── nativeness_service.py   # Async nativeness operations (GPU-aware)
    │   └── developability_service.py # Async developability operations
    ├── validators/             # Validator orchestrators
    │   ├── __init__.py
    │   ├── diversity_validator.py
    │   ├── nativeness_validator.py
    │   └── developability_validator.py
    ├── models/                 # Pydantic data models
    │   ├── __init__.py
    │   ├── sequence.py         # Sequence and batch models
    │   └── validation_result.py # Response models
    ├── routes/                 # FastAPI route definitions
    │   ├── __init__.py
    │   ├── submission_routes.py    # POST /submit
    │   ├── validation_routes.py    # POST /validate, /validate/batch
    │   ├── health_routes.py        # GET /health
    │   ├── diversity_routes.py     # POST /diversity/*
    │   ├── nativeness_routes.py    # POST /nativeness/*
    │   ├── developability_routes.py # POST /developability/*
    │   └── service_routes.py       # GET/POST /services/*
    ├── utils/                  # Utility functions
    │   ├── __init__.py
    │   ├── cdr_utils.py        # CDR extraction and mutation counting (abnumber)
    │   ├── kmer.py             # K-mer generation and indexing
    │   ├── similarity.py       # Jaccard, MinHash similarity (datasketch)
    │   ├── mmseqs2_wrapper.py  # MMseqs2 CLI wrapper
    │   ├── tnp_wrapper.py      # TNP CLI wrapper
    │   └── gpu_scheduler.py    # In-memory GPU task scheduler
    └── tests/                  # Test suite
        ├── __init__.py
        ├── test_diversity.py
        ├── test_nativeness.py
        ├── test_developability.py
        ├── test_submission.py
        ├── test_validation.py
        ├── test_utils.py
        ├── tools/              # External tool integration tests (84 tests)
        │   ├── __init__.py
        │   ├── conftest.py     # Shared fixtures and test data
        │   ├── test_tnp.py     # TNP wrapper tests (12 tests)
        │   ├── test_mmseqs2.py # MMseqs2 wrapper tests (11 tests)
        │   ├── test_abnumber.py # abnumber/CDR extraction tests (15 tests)
        │   ├── test_abnativ.py  # AbnatiV v2 scoring tests (12 tests)
        │   ├── test_promb.py    # promb/OASis humanness tests (16 tests)
        │   └── test_datasketch.py # datasketch/MinHash tests (18 tests)
        └── routes/             # API route integration tests (58 tests)
            ├── __init__.py
            ├── conftest.py     # Shared fixtures (base_url, sequences, payloads)
            ├── test_health_routes.py      # Health check tests (4 tests)
            ├── test_validation_routes.py  # Validation pipeline tests (11 tests)
            ├── test_service_routes.py     # Service/GPU status tests (10 tests)
            ├── test_diversity_routes.py   # Diversity service tests (11 tests)
            ├── test_nativeness_routes.py  # Nativeness service tests (11 tests)
            └── test_developability_routes.py # Developability tests (11 tests)
```

### **Module Descriptions**

| Module | Purpose |
|--------|---------|
| `metanano/` | Main application package containing all filter logic and API |
| `metanano/filters/` | Core filtering logic (synchronous, diversity, nativeness, developability) |
| `metanano/services/` | Async service layer wrapping filters with semaphores and GPU scheduling |
| `metanano/validators/` | Orchestrators that apply filters and produce results |
| `metanano/models/` | Pydantic models for requests, responses, and validation |
| `metanano/routes/` | FastAPI route handlers for HTTP endpoints |
| `metanano/utils/` | Helper functions (k-mer, similarity, CDR extraction, MMseqs2, TNP, GPU scheduler) |
| `metanano/tests/` | Unit and integration tests |
| `metanano/tests/tools/` | External tool integration tests (84 tests total) |
| `metanano/tests/routes/` | API route integration tests (58 tests total) |

---

## **3. Routes (API Definitions)**

### **3.1 /submit** (POST)

**Purpose:** Handle nanobody sequence submissions.

**Input:**

* `sequence` (str): The amino acid sequence of the nanobody.
* `user_id` (str): The ID of the submitting user.

**Output:**

* `status` (str): "Success" or "Error".
* `message` (str): If there was an error, provides a description (e.g., "Sequence too similar to prior submissions").

**Implementation:** `metanano/routes/submission_routes.py`

```python
@router.post("")
async def submit_sequence(submission: SequenceSubmission) -> SubmissionResponse:
    result = pipeline.validate(submission.sequence)
    
    if result.validation_status == "Failed":
        return SubmissionResponse(status="Error", message=f"Validation failed: {result.failed_filters}")
    
    # Save valid sequence to database
    return SubmissionResponse(status="Success", message="Sequence submitted successfully!")
```

### **3.2 /validate** (POST)

**Purpose:** Validate a nanobody sequence against the filters.

**Input:**

* `sequence` (str): The sequence of the nanobody to be validated.

**Output:**

* `validation_status` (str): The status of the validation (e.g., "Passed", "Failed").
* `failed_filters` (list): List of filters the sequence failed (e.g., ["Diversity", "Nativeness"]).
* `details` (object): Detailed scores and metrics from each filter.

**Implementation:** `metanano/routes/validation_routes.py`

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

**Purpose:** Health check endpoint for monitoring.

**Output:**

* `status` (str): "healthy"
* `service` (str): "MetaNano"
* `message` (str): Status message

**Implementation:** `metanano/routes/health_routes.py`

### **3.4 /diversity/** (Service Routes)

**Purpose:** Direct access to diversity filter operations.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/diversity/analyze` | POST | Analyze sequence diversity |
| `/diversity/batch-check` | POST | Check batch diversity via MMseqs2 |
| `/diversity/cdr-mutations` | POST | Check CDR mutation requirements |

**Implementation:** `metanano/routes/diversity_routes.py`

### **3.5 /nativeness/** (Service Routes)

**Purpose:** Direct access to nativeness filter operations.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/nativeness/analyze` | POST | Full nativeness analysis |
| `/nativeness/imgt-number` | POST | IMGT numbering only |
| `/nativeness/scores` | POST | Compute nativeness/humanness scores |

**Implementation:** `metanano/routes/nativeness_routes.py`

### **3.6 /developability/** (Service Routes)

**Purpose:** Direct access to developability filter operations.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/developability/analyze` | POST | Full developability analysis |
| `/developability/tnp-profile` | POST | TNP profiling only |
| `/developability/analyze-batch` | POST | Batch developability analysis |

**Implementation:** `metanano/routes/developability_routes.py`

### **3.7 /services/** (Management Routes)

**Purpose:** Service management and GPU scheduler control.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/services/status` | GET | Get async manager and service status |
| `/services/gpu` | GET | Get GPU scheduler status (queue, utilization) |
| `/services/gpu/control` | POST | Enable/disable GPUs dynamically |

**Implementation:** `metanano/routes/service_routes.py`

---

## **4. Workflow for Validation**

### **4.1 Validation Steps:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT SEQUENCE                                │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: DIVERSITY FILTER                                           │
│  ├── MMseqs2 clustering (global_cluster_identity >= 0.98)           │
│  ├── CDR mutation check (cdrs_combined >= 2, cdr3 >= 1)             │
│  └── Historical comparison (Plan A or Plan B)                       │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                          PASS?  │
                     ┌───────────┴───────────┐
                     │ NO                    │ YES
                     ▼                       ▼
              ┌──────────────┐    ┌─────────────────────────────────────┐
              │ REJECT       │    │  STEP 2: NATIVENESS FILTER          │
              │ (Diversity)  │    │  ├── abnumber IMGT numbering        │
              └──────────────┘    │  ├── Nativeness score >= 0.80       │
                                  │  └── Humanness score >= 0.75        │
                                  └─────────────────────────────────────┘
                                                   │
                                            PASS?  │
                                       ┌───────────┴───────────┐
                                       │ NO                    │ YES
                                       ▼                       ▼
                                ┌──────────────┐    ┌─────────────────────────────────────┐
                                │ REJECT       │    │  STEP 3: DEVELOPABILITY FILTER      │
                                │ (Nativeness) │    │  ├── TNP Profiler                   │
                                └──────────────┘    │  └── Red Region criteria check      │
                                                    └─────────────────────────────────────┘
                                                                     │
                                                              PASS?  │
                                                         ┌───────────┴───────────┐
                                                         │ NO                    │ YES
                                                         ▼                       ▼
                                                  ┌──────────────┐    ┌──────────────┐
                                                  │ REJECT       │    │ ACCEPT       │
                                                  │(Developability│    │ SEQUENCE     │
                                                  └──────────────┘    └──────────────┘
```

1. **Diversity Validation:**
   * The sequence is checked for diversity within the batch (MMseqs2, mutations in CDRs).
   * It is then compared against historical submissions using the Weighted MinHash.
   * **Plan B (Preferred):** Compare only against top 50 leaderboard sequences.
   * If any step fails, validation stops and feedback is returned.

2. **Nativeness Validation:**
   * Sequence is numbered using the **abnumber** tool under IMGT schema.
   * The nativeness score is calculated using **AbnatiV v2** (threshold: >= 0.80).
   * The humanness score is calculated (threshold: >= 0.75).
   * Optional: Cross-check with **promb** (OASis humanness score).

3. **Developability Validation:**
   * The sequence is checked against the **TNP** (Therapeutic Nanobody Profiler).
   * If ANY property falls into the **Red Region**, the sequence is **rejected**.
   * Only sequences with ALL properties within valid ranges pass this filter.

### **4.2 Output:**

* If the sequence passes all filters, it is marked as valid.
* If it fails, the specific filter(s) failed will be included in the feedback message along with the actual scores/values.

---

## **5. Configuration Parameters**

All configuration is managed through Pydantic models in `metanano/config.py`.

### **5.1 Diversity Filter Config**

```python
from metanano.config import Config

config = Config()

# Access diversity settings
config.diversity.mmseqs2.global_cluster_identity  # 0.98
config.diversity.mutations.cdrs_combined_min      # 2
config.diversity.mutations.cdr3_min               # 1
config.diversity.kmer_index.k                     # 5
config.diversity.comparison.strategy              # "plan_b"
config.diversity.comparison.plan_b.current_top_n  # 50
```

### **5.2 Nativeness Filter Config**

```python
config.nativeness.abnumber.scheme                    # "imgt"
config.nativeness.abnativ_v2.nativeness_threshold    # 0.80
config.nativeness.abnativ_v2.humanness_threshold     # 0.75
config.nativeness.promb.enabled                      # False
```

### **5.3 Developability Filter Config (Red Region - July 2025)**

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

### **5.4 Async Concurrency Config**

```python
# Semaphore limits for concurrent operations
config.async_config.max_concurrent_validations  # 10 (overall pipeline)
config.async_config.max_concurrent_tnp          # 4  (TNP CLI calls)
config.async_config.max_concurrent_mmseqs2      # 2  (MMseqs2 clustering)
config.async_config.max_concurrent_abnativ      # 4  (AbnatiV scoring)
config.async_config.max_concurrent_promb        # 4  (promb humanness)

# Batch processing settings
config.async_config.batch_size                  # 50 (sequences per batch)
config.async_config.task_timeout                # 300.0 (seconds)
config.async_config.queue_size                  # 1000 (max pending tasks)
```

### **5.5 GPU Scheduler Config**

```python
# GPU scheduler settings
config.gpu_scheduler.enabled                    # True
config.gpu_scheduler.auto_detect                # True (auto-detect GPUs)
config.gpu_scheduler.scheduling_strategy        # "least_loaded"
config.gpu_scheduler.default_max_concurrent_per_gpu  # 2
config.gpu_scheduler.queue_max_size             # 500
config.gpu_scheduler.task_timeout               # 600.0 (seconds)
config.gpu_scheduler.health_check_interval      # 30.0 (seconds)
config.gpu_scheduler.memory_threshold_percent   # 85.0 (overloaded if >=)
config.gpu_scheduler.gpu_util_threshold_percent # 80.0 (overloaded if >=)

# Manual GPU registration (overrides auto-detect)
config.gpu_scheduler.gpus = [
    GPUConfig(index=0, max_concurrent_tasks=2, enabled=True),
    GPUConfig(index=1, max_concurrent_tasks=4, memory_limit_gb=8.0),
]
```

**Overload Thresholds:**

| Threshold | Default | Description |
|-----------|---------|-------------|
| `memory_threshold_percent` | 85% | GPU marked overloaded if memory% >= threshold |
| `gpu_util_threshold_percent` | 80% | GPU marked overloaded if GPU utilization% >= threshold |

**Scheduling Strategies:**

| Strategy | Description |
|----------|-------------|
| `round_robin` | Rotate through GPUs (avoids last used GPU) |
| `least_loaded` | Choose GPU with lowest combined score (memory% + util% + load) |
| `memory_aware` | Choose GPU with most available memory |

---

## **6. Examples**

### **6.1 Sequence Submission:**

```bash
curl -X POST http://localhost:5000/submit \
-H "Content-Type: application/json" \
-d '{"sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS", "user_id": "12345"}'
```

**Expected Output:**

```json
{
  "status": "Success",
  "message": "Sequence submitted successfully!"
}
```

### **6.2 Sequence Validation:**

```bash
curl -X POST http://localhost:5000/validate \
-H "Content-Type: application/json" \
-d '{"sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS"}'
```

**Expected Output (Passed):**

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

**Expected Output (Failed - Developability Red Region):**

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
        "total_cdr_length (18) outside valid range [20, 39]",
        "cdr3_length (4) outside valid range [5, 23]",
        "positive_charge_patches (1.25) > threshold (1.18)",
        "negative_charge_patches (1.95) > threshold (1.88)"
      ],
      "reason": "total_cdr_length (18) outside valid range [20, 39]; cdr3_length (4) outside valid range [5, 23]; positive_charge_patches (1.25) > threshold (1.18); negative_charge_patches (1.95) > threshold (1.88)"
    }
  }
}
```

### **6.3 Health Check:**

```bash
curl http://localhost:5000/health
```

**Expected Output:**

```json
{
  "status": "healthy",
  "service": "MetaNano",
  "message": "Service is running."
}
```

### **6.4 Python Usage:**

```python
from metanano import Config, ValidationPipeline

# Create pipeline with default config
config = Config()
pipeline = ValidationPipeline(config)

# Validate a sequence
result = pipeline.validate("EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSS")

print(f"Status: {result.validation_status}")
print(f"Failed Filters: {result.failed_filters}")
print(f"Details: {result.details}")
```

---

## **7. Dependencies**

| Package | Purpose | Repository |
|---------|---------|------------|
| `mmseqs2` | Sequence clustering for diversity filter | [GitHub](https://github.com/soedinglab/MMseqs2) |
| `abnumber` | IMGT numbering for nanobody sequences | [GitHub](https://github.com/prihoda/AbNumber) |
| `abnativ` | Nativeness and humanness scoring (AbnatiV v2) | [GitLab](https://gitlab.developers.cam.ac.uk/ch/sormanni/abnativ) |
| `promb` | Optional humanness cross-validation (OASis score) | [GitHub](https://github.com/MSDLLCpapers/promb) |
| `tnp` | Therapeutic Nanobody Profiler for developability | [GitHub](https://github.com/oxpig/TNP) |
| `datasketch` | Weighted MinHash for similarity calculations | [GitHub](https://github.com/ekzhu/datasketch) |
| `fastapi` | Web framework for API endpoints | [GitHub](https://github.com/tiangolo/fastapi) |
| `pydantic` | Data validation and settings management | [GitHub](https://github.com/pydantic/pydantic) |

---

## **8. Installation**

### **8.1 Quick Start**

```bash
# Clone the repository
git clone <repository-url>
cd NOVA-nanobody-filter

# Run installation script (recommended)
chmod +x install/install.sh
./install/install.sh --minimal

# Activate environment
conda activate metanano

# Run the application
cd metanano
python -m uvicorn metanano.app:app --reload --port 5000
```

**Note:** Always run the server from the project root directory (`NOVA-nanobody-filter/`), not from inside the `metanano/` directory.

### **8.2 Run Tests**

```bash
# Activate environment
conda activate metanano

# Run all tool tests (84 tests)
python -m pytest metanano/tests/tools/ -v

# Run specific tool tests
python -m pytest metanano/tests/tools/test_tnp.py -v       # TNP (12 tests)
python -m pytest metanano/tests/tools/test_mmseqs2.py -v   # MMseqs2 (11 tests)
python -m pytest metanano/tests/tools/test_abnumber.py -v  # abnumber (15 tests)
python -m pytest metanano/tests/tools/test_abnativ.py -v   # AbnatiV v2 (12 tests)
python -m pytest metanano/tests/tools/test_promb.py -v     # promb (16 tests)
python -m pytest metanano/tests/tools/test_datasketch.py -v # datasketch (18 tests)
```

**Note:** For AbnatiV v2 tests, you need to download the models first:

```bash
abnativ init
```

This downloads pre-trained models (~5.8GB) from Zenodo to `~/.abnativ/models/pretrained_models/`.

### **8.3 Run Route Tests**

Route tests require a running server. Start the server first, then run tests:

```bash
# Terminal 1: Start the server
conda activate metanano
python -m uvicorn metanano.app:app --host 0.0.0.0 --port 5000

# Terminal 2: Run route tests (58 tests)
conda activate metanano
python -m pytest metanano/tests/routes/ -v

# Run specific route tests
python -m pytest metanano/tests/routes/test_health_routes.py -v       # Health (4 tests)
python -m pytest metanano/tests/routes/test_validation_routes.py -v   # Validation (11 tests)
python -m pytest metanano/tests/routes/test_service_routes.py -v      # Service/GPU (10 tests)
python -m pytest metanano/tests/routes/test_diversity_routes.py -v    # Diversity (11 tests)
python -m pytest metanano/tests/routes/test_nativeness_routes.py -v   # Nativeness (11 tests)
python -m pytest metanano/tests/routes/test_developability_routes.py -v # Developability (11 tests)
```

**Note:** Route tests automatically skip if the server is not running.

| Test Category | Tests | Description |
|---------------|-------|-------------|
| Health | 4 | Health check endpoint validation |
| Validation | 11 | Single and batch validation pipeline |
| Service/GPU | 10 | Async manager and GPU scheduler status/control |
| Diversity | 11 | Diversity analysis, batch check, CDR mutations |
| Nativeness | 11 | Nativeness analysis, IMGT numbering, scores |
| Developability | 11 | Developability analysis, TNP profile, batch |
| **Total** | **58** | All route tests |

### **8.4 Docker (Coming Soon)**

```bash
docker-compose up -d
```

---

## **9. External Tool Integration**

All external tools have been integrated with Python wrappers and comprehensive tests.

### **9.1 Test Summary**

| Category | Tests | Location | Purpose |
|----------|-------|----------|---------|
| **Tool Tests** | 84 | `tests/tools/` | External tool integration |
| **Route Tests** | 58 | `tests/routes/` | API endpoint integration |
| **Total** | **142** | | All tests passing |

### **9.2 Tool Test Details**

| Tool | Tests | Wrapper/Module | Purpose |
|------|-------|----------------|---------|
| **TNP** | 12 | `utils/tnp_wrapper.py` | Developability profiling (CLI wrapper) |
| **MMseqs2** | 11 | `utils/mmseqs2_wrapper.py` | Sequence clustering (CLI wrapper) |
| **abnumber** | 15 | `utils/cdr_utils.py` | IMGT numbering and CDR extraction |
| **AbnatiV v2** | 12 | `filters/nativeness.py` | Nativeness/humanness scoring |
| **promb** | 16 | `filters/nativeness.py` | OASis humanness scoring |
| **datasketch** | 18 | `utils/similarity.py` | Weighted MinHash similarity |
| **Total** | **84** | | All tool tests passing |

### **9.3 Tool Availability Check**

The system gracefully handles missing tools:

```python
from metanano.utils import TNPWrapper, MMseqs2Wrapper

# Check if TNP is available
tnp = TNPWrapper()
if tnp.is_available():
    result = tnp.profile_nanobody(sequence)

# Check if MMseqs2 is available
mmseqs2 = MMseqs2Wrapper()
if mmseqs2.is_available():
    clusters = mmseqs2.cluster(sequences)
```

---

## **10. References**

* NOVA Nanobody Challenge Submission Filters Specification (July 2025)

### **10.1 Tool Repositories**

| Tool | Description | Repository |
|------|-------------|------------|
| **MMseqs2** | Ultra-fast sequence clustering and searching | [GitHub](https://github.com/soedinglab/MMseqs2) |
| **AbNumber** | Antibody numbering using IMGT, Chothia, Kabat schemes | [GitHub](https://github.com/prihoda/AbNumber) |
| **AbnatiV** | Antibody nativeness validation (v2) | [GitLab](https://gitlab.developers.cam.ac.uk/ch/sormanni/abnativ) |
| **BioPhi** | Antibody design and humanization platform | [GitHub](https://github.com/Merck/BioPhi) |
| **promb** | Protein humanness evaluation toolkit (OASis successor) | [GitHub](https://github.com/MSDLLCpapers/promb) |
| **TNP** | Therapeutic Nanobody Profiler for developability | [GitHub](https://github.com/oxpig/TNP) |

### **10.2 Tool Details**

* **MMseqs2** - Many-against-Many sequence searching
  * Ultra-fast and sensitive protein sequence clustering
  * Used for diversity filtering with identity thresholds

* **AbNumber** - Antibody numbering tool
  * Supports IMGT, Chothia, Kabat, and other numbering schemes
  * Validates nanobody sequence structure

* **AbnatiV v2** - Antibody nativeness validation
  * Evaluates whether sequences belong to natural antibody families
  * Provides nativeness and humanness scores

* **BioPhi** - Antibody design platform
  * Comprehensive humanization and design tools
  * OASis humanness metric (now superseded by promb)

* **promb** - Protein mutation burden toolkit
  * Successor to BioPhi's OASis humanness metric
  * Computes humanness based on average mutations to nearest peptide in reference proteome
  * Supports Human OAS, Human SwissProt, and custom reference databases

* **TNP** - Therapeutic Nanobody Profiler
  * Evaluates developability properties for therapeutic candidates
  * Analyzes CDR lengths, surface patches, and charge distribution

---

## **11. Async Architecture**

The system uses a layered async architecture for high-throughput processing.

### **11.1 Architecture Overview**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Routes (async)                        │
│  /validate, /diversity/*, /nativeness/*, /developability/*          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Service Layer (async)                           │
│  DiversityService, NativenessService, DevelopabilityService          │
│  └── Uses asyncio.to_thread() to run sync filters                   │
│  └── Semaphore control for each resource type                       │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AsyncManager (singleton)                        │
│  ├── Semaphores: validation, tnp, mmseqs2, abnativ, promb           │
│  └── GPUScheduler: task queue, load balancing, health checks        │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Filter Layer (synchronous)                      │
│  DiversityFilter, NativenessFilter, DevelopabilityFilter             │
│  └── Pure computation, no async awareness                           │
└─────────────────────────────────────────────────────────────────────┘
```

### **11.2 Semaphore-Based Concurrency**

Each resource-intensive operation has a dedicated semaphore:

| Semaphore | Default Limit | Controls |
|-----------|---------------|----------|
| `validation_semaphore` | 10 | Overall pipeline concurrency |
| `tnp_semaphore` | 4 | TNP CLI subprocess calls |
| `mmseqs2_semaphore` | 2 | MMseqs2 clustering (I/O heavy) |
| `abnativ_semaphore` | 4 | AbnatiV model inference |
| `promb_semaphore` | 4 | promb humanness scoring |

### **11.3 GPU Scheduler**

For GPU-bound tasks (e.g., AbnatiV scoring), the GPU scheduler provides:

* **Smart GPU Selection:**
  * Avoids re-using the last GPU (for load distribution)
  * Tracks recent GPU usage history
  * Selects based on combined score: `memory% * 0.5 + gpu_util% * 0.5 + load * 10`

* **Real-time Monitoring:**
  * Memory usage (via nvidia-smi, system-wide)
  * GPU utilization percentage
  * Active task count per GPU

* **Overload Detection:**
  * GPU marked as `overloaded` if memory% >= 85% OR gpu_util% >= 80%
  * Overloaded GPUs are excluded from task assignment

* **Dynamic Control:** Enable/disable GPUs at runtime via API

**GPU Status Response:**
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
# Example: Running a GPU-bound task
result = await gpu_scheduler.run_on_gpu(compute_abnativ_score, sequence)
# gpu_index is automatically injected into the function
```

### **11.4 Python Usage (Async)**

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
    
    # Async validation
    result = await diversity_svc.analyze_async(sequence)
    scores = await nativeness_svc.compute_scores_async(sequence)
    
    await manager.shutdown()

asyncio.run(main())
```

## **12. Search Performance Benchmarks**

Benchmark results for the sequence search subsystem using real antibody sequences from [PLAbDab](https://opig.stats.ox.ac.uk/webapps/plabdab/) (Patent and Literature Antibody Database).

### **12.1 Dataset**

| Source | Sequences | Description |
|--------|-----------|-------------|
| PLAbDab paired | 58,405 | Unique valid heavy chains from paired antibody entries |
| PLAbDab unpaired | 369,718 | Unique valid heavy chains (chain=H) from unpaired entries |
| **Combined** | **221,692** | **Deduplicated heavy chains (50–500 AA, standard amino acids only)** |

### **12.2 Tier 1: K-mer Coarse Filter + Alignment**

Default configuration: `k=5`, `min_shared_kmers=3`, `jaccard_threshold=0.3`, `max_candidates=500`.

| N (sequences) | Index Build | Peak RSS | P50 Latency | P95 Latency | P99 Latency | QPS |
|---------------|-------------|----------|-------------|-------------|-------------|-----|
| 10,000 | 3.2s | 39 MB | 57 ms | 448 ms | 470 ms | 6.7 |
| 50,000 | 12.8s | 147 MB | 274 ms | 553 ms | 644 ms | 3.4 |
| 100,000 | 23.2s | 248 MB | 471 ms | 686 ms | 797 ms | 2.3 |
| 221,692 | 45.9s | 493 MB | 780 ms | 1,415 ms | 1,577 ms | 1.3 |

**Gate thresholds (from `harness.py`):**

| Scale | RSS Limit | P99 Limit | Status |
|-------|-----------|-----------|--------|
| 10,000 | < 200 MB | < 200 ms | RSS ✓, P99 — see note below |
| 100,000 | < 500 MB | < 500 ms | RSS ✓, P99 ✓ |

> **Note on P99 at 10k:** The 470ms P99 on real antibody data exceeds the 200ms synthetic-data gate. Real antibody sequences are far more homologous than synthetic random sequences, producing more coarse-filter candidates per query and therefore longer alignment phases. The 100k gate (P99 < 500ms) passes cleanly.

**Observations:**

- Memory scales linearly at ~2.2 MB per 1,000 sequences
- P99 latency scales superlinearly — driven by the alignment phase when many candidates pass the Jaccard threshold
- Real antibody sequences are clustered (evolutionary families), so candidate counts are higher than synthetic data

### **12.3 Tier 2: MinHash LSH Approximate Retrieval**

Configuration: `num_perm=256`, `lsh_threshold=0.2`, `jaccard_threshold=0.3`, `max_candidates=500`.  
Recall is measured as: `|exact ∩ LSH| / |exact|` where "exact" is the threshold-qualified set (Jaccard ≥ 0.3).

| N (sequences) | Index Build | Avg Recall | Exact Query | LSH Query | Speedup |
|---------------|-------------|------------|-------------|-----------|---------|
| 10,000 | 26s | **0.967** | 13.5 ms | 3.9 ms | 3.5× |
| 50,000 | 107s | **0.898** | 77.5 ms | 14.1 ms | 5.5× |

**Gate:** Recall ≥ 0.80 — **PASS** at both scales.

**Observations:**

- LSH recall exceeds 0.89 on real data at all tested scales
- Query-time speedup grows with index size (3.5× at 10k → 5.5× at 50k)
- LSH index build is the bottleneck (serial MinHash computation per sequence)
- For production use at 200k+, parallel MinHash build is recommended

### **12.4 Test Suite**

All search tests pass with real and synthetic data:

```
87 passed, 0 failed (pytest metanano/tests/search/)
```

### **12.5 Reproducing Benchmarks**

1. Download PLAbDab data:

```bash
wget -O /tmp/plabdab_paired.csv.gz \
  "https://opig.stats.ox.ac.uk/webapps/plabdab/static/downloads/paired_data.csv.gz"
wget -O /tmp/plabdab_unpaired.csv.gz \
  "https://opig.stats.ox.ac.uk/webapps/plabdab/static/downloads/unpaired_data.csv.gz"
```

2. Run search tests:

```bash
cd NOVA-nanobody-filter
pip install datasketch
python -m pytest metanano/tests/search/ -v
```

3. See [SEARCH_REAL_DATA_REPRO.md](SEARCH_REAL_DATA_REPRO.md) for the real-data reproduction script.
