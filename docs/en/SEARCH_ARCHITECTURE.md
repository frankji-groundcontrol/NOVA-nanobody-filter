# Search Architecture

How the sequence search subsystem detects duplicate and too-similar nanobody submissions.

> **Primary goal**: Given a query nanobody, find all indexed sequences that are similar enough to be considered duplicates or near-duplicates, even when nanobodies share highly conserved framework regions.

---

## Table of Contents

1. [Why Nanobody Search Is Hard](#1-why-nanobody-search-is-hard)
2. [Search Pipeline Overview](#2-search-pipeline-overview)
3. [Stage 1: Coarse Filter](#3-stage-1-coarse-filter)
4. [Stage 2: Fine Alignment](#4-stage-2-fine-alignment)
5. [Stage 3: CDR Comparison](#5-stage-3-cdr-comparison)
6. [Retrieval Strategies](#6-retrieval-strategies)
7. [Configuration Reference](#7-configuration-reference)
8. [Tuning for Nanobody Duplicate Detection](#8-tuning-for-nanobody-duplicate-detection)
9. [API Reference](#9-api-reference)
10. [Performance Characteristics](#10-performance-characteristics)

---

## 1. Why Nanobody Search Is Hard

Nanobodies (VHH single-domain antibodies) are ~110-130 amino acids long. About 70-75% of that length is **framework regions** (FR1-FR4) that are highly conserved within a species — often >85-90% identical across unrelated nanobodies.

This creates a fundamental problem for similarity search:

```
Nanobody A: FR1-CDR1-FR2-CDR2-FR3-CDR3(ARDLGTYYYYGMDV)-FR4
Nanobody B: FR1-CDR1-FR2-CDR2-FR3-CDR3(AKNQPWSSALDY)--FR4

Whole-sequence identity: ~87%  (looks similar!)
CDR3 identity:            0%  (completely different binding)
```

Two nanobodies with **completely different CDR3s** — and therefore different antigen binding — can still show >80% whole-sequence identity because the conserved framework dominates the score.

### What Actually Determines Novelty

| Region | % of Sequence | Conservation | Role in Novelty |
|--------|--------------|-------------|-----------------|
| FR1-FR4 | ~70-75% | >85-90% conserved | Low — structural scaffold |
| CDR1 | ~5% | Moderate | Moderate — fine-tunes binding |
| CDR2 | ~10% | Moderate | Moderate — contributes to paratope |
| **CDR3** | **~10-15%** | **Highly variable** | **Primary determinant of binding specificity** |

CDR3 is the product of VDJ recombination and is the most variable region. Even 1-2 amino acid differences in CDR3 can change epitope specificity. CDR3 length alone (typically 12-18 aa, median ~15) is a strong signal — a length difference of ≥3 residues almost certainly means different binding geometry.

### What This Means for the Search System

The search pipeline must:
1. **Not be fooled by framework conservation** — high whole-sequence similarity does not mean functional duplication.
2. **Surface CDR-level similarity** separately from whole-sequence metrics.
3. **Operate at scale** — competition databases can grow to 100k+ sequences.

---

## 2. Search Pipeline Overview

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

### Key Design Decisions

- **Two retrieval strategies**: `kmer_jaccard` (exact, default) and `lsh` (approximate, faster at scale). Both produce a candidate list that enters the same alignment pipeline.
- **Coarse-to-fine**: The coarse filter narrows 100k+ sequences to ≤500 candidates in milliseconds. Fine alignment runs only on those candidates.
- **CDR comparison is additive**: It does not affect ranking (which is by alignment identity), but provides the CDR-level breakdown needed to judge true novelty.
- **Deterministic ordering**: Ties in Jaccard or identity are always broken by `target_id` ascending. Same input always produces same output.

---

## 3. Stage 1: Coarse Filter

The coarse filter rapidly narrows the full index to a small candidate set. It operates on **k-mer sets** (sets of short subsequences), not on raw sequences.

### How K-mers Work

A k-mer of length `k=5` for sequence `EVQLVQS` produces:

```
{ EVQLV, VQLVQ, QLVQS }
```

Two sequences sharing many 5-mers are likely similar. The **Jaccard similarity** of their k-mer sets measures this:

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

### The Three Stages (kmer_jaccard strategy)

**Stage 1 — Shared k-mer count**: For each indexed sequence, count how many k-mers it shares with the query using the inverted index. Discard sequences with fewer than `min_shared_kmers` shared k-mers.

**Stage 2 — Jaccard threshold**: For survivors, compute exact Jaccard similarity. Discard sequences below `jaccard_threshold`.

**Stage 3 — Top-K selection**: Sort survivors by Jaccard descending (ties broken by ID ascending), keep top `max_candidates`.

### Parameter Effects

| Parameter | Default | Lower → | Higher → |
|-----------|---------|---------|----------|
| `k` | 5 | More k-mers per sequence, more matches, less specific | Fewer k-mers, more specific, may miss distant matches |
| `min_shared_kmers` | 3 | More candidates survive Stage 1 (slower, better recall) | Fewer candidates (faster, may miss distant matches) |
| `jaccard_threshold` | 0.3 | More candidates survive Stage 2 | Fewer, more similar candidates only |
| `max_candidates` | 500 | Faster alignment phase | More candidates enter alignment (slower, better recall) |

### Why the Default Jaccard Threshold Is 0.3

For nanobodies, a Jaccard threshold of 0.3 on 5-mers is intentionally permissive. Because framework regions are conserved, even unrelated nanobodies share many 5-mers. A threshold of 0.3 ensures that:
- All functionally similar sequences are captured (no false negatives).
- The alignment phase (Stage 2) makes the final similarity judgment.
- Roughly 50-500 candidates survive per query at 100k index size.

Raising this to 0.5+ would miss sequences that differ primarily in CDR3 (which contributes a small fraction of total k-mers).

---

## 4. Stage 2: Fine Alignment

Every candidate from the coarse filter is aligned against the query using pairwise sequence alignment.

### Algorithm

- **Method**: Smith-Waterman (local alignment) by default.
- **Scoring matrix**: BLOSUM62 (standard for protein sequences).
- **Gap penalties**: Open = 10 (configurable), Extend = 1 (fixed).
- **Backend**: parasail (SIMD-accelerated, preferred) with BioPython fallback.

### Output Per Candidate

| Field | Type | Description |
|-------|------|-------------|
| `score` | int | Raw alignment score |
| `identity` | float | Fraction of matching positions (0.0-1.0) |
| `cigar` | string | CIGAR string encoding alignment operations |
| `aligned_query` | string | Query with gaps inserted (if `include_alignment=true`) |
| `aligned_target` | string | Target with gaps inserted (if `include_alignment=true`) |
| `tier` | string | Cosmetic label: exact (≥0.95), high (≥0.80), moderate (≥0.50), low (<0.50) |

### Parallelism

Candidates are split into batches of 16 and aligned in parallel using a thread pool (up to 32 workers). This is the most expensive phase — at 221k indexed sequences, alignment dominates P99 latency.

### Identity vs. Jaccard

These measure different things:

| Metric | What It Measures | Framework Sensitivity |
|--------|-----------------|----------------------|
| **K-mer Jaccard** | Shared subsequences (unordered) | High — frameworks inflate score |
| **Alignment identity** | Position-by-position match (ordered, gapped) | High — frameworks inflate score |
| **CDR similarity** | Per-CDR match (CDR1, CDR2, CDR3 separately) | **None** — framework excluded |

Both Jaccard and alignment identity are inflated by framework conservation. CDR comparison (Stage 3) provides the framework-free signal.

---

## 5. Stage 3: CDR Comparison

If CDR annotations are available for both query and target, the system computes per-CDR similarity scores.

### How CDRs Are Obtained

1. **From index**: If the sequence was indexed with CDR annotations (`cdrs` dict), those are used.
2. **From extraction**: Otherwise, `abnumber` (IMGT scheme) extracts CDR1, CDR2, CDR3 at query time.
3. **Absent**: If extraction fails (e.g., abnumber not installed), CDR similarity is `null`.

### Similarity Calculation

For each CDR (CDR1, CDR2, CDR3):

- **Equal length**: Hamming distance normalized to [0, 1].
  ```
  similarity = 1.0 - (mismatches / length)
  ```
- **Unequal length**: Position-wise mismatches plus length delta, normalized by the longer CDR.
  ```
  distance = positional_mismatches + |len_query - len_target|
  similarity = 1.0 - (distance / max(len_query, len_target))
  ```

### Interpreting CDR Similarity

| CDR3 Similarity | Interpretation |
|----------------|----------------|
| 1.00 | Identical CDR3 — almost certainly a duplicate |
| ≥0.85 | Very similar — likely same epitope, same clonotype |
| 0.70-0.85 | Related clones — may bind same epitope with different affinity |
| <0.70 | Distinct — different binding specificity likely |

| CDR1+CDR2 Similarity | Interpretation |
|---------------------|----------------|
| Both ≥0.90 with CDR3 ≥0.80 | Strong evidence of duplication |
| Both ≥0.90 with CDR3 <0.70 | Framework family match, distinct binder |

---

## 6. Retrieval Strategies

The system supports two retrieval strategies, configured via `coarse_filter.retrieval_strategy`.

### `kmer_jaccard` (Default)

Exact k-mer Jaccard computation using an inverted index. Deterministic, no false negatives for sequences above the Jaccard threshold.

**Best for**: Databases up to ~100k sequences where exact recall matters.

### `lsh` (Locality-Sensitive Hashing)

Approximate retrieval using MinHash signatures and LSH buckets from the `datasketch` library.

**How it works**:
1. Each indexed sequence gets a MinHash signature (a compact sketch of its k-mer set).
2. Signatures are inserted into an LSH index with band/row partitioning.
3. At query time, the query's MinHash signature is looked up in the LSH index.
4. Candidates are re-ranked by exact MinHash Jaccard.

**Parameters**:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `num_perm` | 128 | Number of hash permutations. Higher = more accurate Jaccard estimation, more memory, slower build. 128 is good for screening; 256 for high-recall benchmarks. |
| `lsh_threshold` | 0.3 | Minimum estimated Jaccard for LSH bucket match. Set **at or below** `jaccard_threshold` to avoid missing boundary items. |
| `weights` | (0.5, 0.5) | Balance between false positive and false negative rates. (0.5, 0.5) = balanced. Shift toward (0.3, 0.7) to reduce false negatives at the cost of more candidates. |

**Best for**: Databases >100k sequences where query speed matters more than perfect recall. Benchmark shows 0.90-0.97 recall on real antibody data with 3.5-5.5x query speedup.

**Trade-off**: LSH build is slower than k-mer indexing (MinHash computation per sequence). At 221k sequences, serial LSH build takes several minutes vs ~46s for k-mer-only indexing.

### Choosing a Strategy

| Scenario | Strategy | Reason |
|----------|----------|--------|
| <100k sequences | `kmer_jaccard` | Fast enough, exact recall |
| 100k-500k sequences | Either | kmer_jaccard works but P99 grows; LSH gives faster queries |
| >500k sequences | `lsh` | kmer_jaccard coarse filter becomes the bottleneck |
| Recall is critical | `kmer_jaccard` | No false negatives |
| Query latency is critical | `lsh` | 3-5x faster queries |

---

## 7. Configuration Reference

All parameters live in `metanano/config.py`.

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

### Validation Rules

- `lsh.lsh_threshold` must be ≤ `coarse_filter.jaccard_threshold` (enforced by model validator).
- `k` must be in [1, 10]. Values of 5 or 6 are recommended for nanobodies.

### Full Parameter Table

| Parameter | Path | Type | Default | Range | Description |
|-----------|------|------|---------|-------|-------------|
| `k` | `search.k` | int | 5 | 1-10 | K-mer length |
| `min_shared_kmers` | `search.coarse_filter.min_shared_kmers` | int | 3 | ≥1 | Minimum shared k-mers to pass Stage 1 |
| `jaccard_threshold` | `search.coarse_filter.jaccard_threshold` | float | 0.3 | 0.0-1.0 | Minimum Jaccard to pass Stage 2 |
| `max_candidates` | `search.coarse_filter.max_candidates` | int | 500 | ≥1 | Maximum candidates after coarse filter |
| `retrieval_strategy` | `search.coarse_filter.retrieval_strategy` | str | "kmer_jaccard" | kmer_jaccard, lsh | Retrieval method |
| `num_perm` | `search.lsh.num_perm` | int | 128 | ≥16 | MinHash permutation count |
| `lsh_threshold` | `search.lsh.lsh_threshold` | float | 0.3 | 0.0-1.0 | LSH similarity threshold |
| `weights` | `search.lsh.weights` | tuple | (0.5, 0.5) | — | LSH FP/FN weight balance |
| `gap_open` | `search.fine_alignment.gap_open` | int | 10 | ≥0 | Alignment gap open penalty |
| `job_ttl_seconds` | `search.job_ttl_seconds` | float | 3600 | ≥1 | Async job TTL |
| `max_concurrent_search` | `search.max_concurrent_search` | int | 4 | ≥1 | Concurrent search limit |

---

## 8. Tuning for Nanobody Duplicate Detection

The default parameters are tuned for **general-purpose similarity search**. For the specific task of **detecting duplicate or too-similar nanobody submissions**, consider the following adjustments.

### Recommended Decision Logic

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

### Why Not Just Use Whole-Sequence Identity?

Because of framework conservation. Consider two nanobodies:

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Whole-sequence identity | 88% | Looks like a duplicate |
| CDR3 identity | 15% | Completely different binder |
| CDR1 identity | 95% | Same germline family |
| CDR2 identity | 90% | Same germline family |

Using whole-sequence identity alone would **incorrectly flag this as a duplicate**. The CDR3 — which determines binding specificity — is completely different.

### Parameter Adjustments for Strict Duplicate Detection

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

### CDR3 Length as a Fast Pre-filter

CDR3 length difference is a strong signal. Nanobodies with CDR3 length differences of ≥3 residues almost certainly have different binding geometry, regardless of sequence similarity. This can be used as a fast pre-filter before running the full search pipeline.

---

## 9. API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /search` | Submit | Submit async search job, returns `job_id` (HTTP 202) |
| `GET /search/{job_id}` | Poll | Get job status and results |
| `POST /search/index` | Index | Add one sequence to the search index (HTTP 201) |
| `GET /search/index/stats` | Stats | Get indexed sequence count |

### Sequence Validation

All sequences are validated on input:
- **Characters**: Only standard amino acids (`ACDEFGHIKLMNPQRSTVWY`)
- **Length**: 10-500 residues
- **Normalization**: Uppercased, whitespace stripped

### Job Lifecycle

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

Jobs are retained for `job_ttl_seconds` (default: 1 hour) after creation, then cleaned up.

### Search Request

```json
{
  "sequences": ["EVQLVESGGGLVQPGG..."],
  "include_alignment": false,
  "coarse_min_shared": null,
  "coarse_jaccard": null
}
```

The `coarse_min_shared` and `coarse_jaccard` fields override the server-side defaults for this query only.

### Search Result

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

## 10. Performance Characteristics

Benchmarked on 221,692 real heavy-chain sequences from PLAbDab.

### Tier 1: K-mer Coarse Filter + Alignment

| N | Build | Peak RSS | P50 | P95 | P99 |
|---|-------|----------|-----|-----|-----|
| 10k | 3.2s | 39 MB | 57 ms | 448 ms | 470 ms |
| 50k | 12.8s | 147 MB | 274 ms | 553 ms | 644 ms |
| 100k | 23.2s | 248 MB | 471 ms | 686 ms | 797 ms |
| 221k | 45.9s | 493 MB | 780 ms | 1,415 ms | 1,577 ms |

Memory scales linearly (~2.2 MB per 1,000 sequences). Latency scales superlinearly because real antibody sequences are clustered into evolutionary families, producing more coarse-filter candidates per query than synthetic data.

### Tier 2: LSH Recall

| N | Avg Recall | LSH Query | Exact Query | Speedup |
|---|-----------|-----------|-------------|---------|
| 10k | 0.967 | 3.9 ms | 13.5 ms | 3.5x |
| 50k | 0.898 | 14.1 ms | 77.5 ms | 5.5x |

LSH recall exceeds 0.89 at all tested scales. Speedup grows with index size.

### Scaling Guidance

| Index Size | Strategy | Expected P99 | Notes |
|-----------|----------|-------------|-------|
| <10k | kmer_jaccard | <500 ms | Fast enough for any use |
| 10k-100k | kmer_jaccard | <800 ms | Default config works well |
| 100k-500k | lsh recommended | <200 ms query | Build is slower, queries are faster |
| >500k | lsh required | — | kmer_jaccard P99 becomes too high |
