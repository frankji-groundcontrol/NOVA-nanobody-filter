# Reproduce Real-Data Search Test

This guide reproduces the end-to-end search validation using real VHH sequences from a public nanobody database (PLAbDab-nano).

## Goal

Verify that the search pipeline works with real nanobody data, not only local test fixtures.

The test covers:

- remote real-data download
- sequence cleaning and validation
- in-memory indexing via `SearchService`
- async search submit and polling
- match quality checks (identity and tier)

## Data Source

- PLAbDab-nano VHH download:
  `https://opig.stats.ox.ac.uk/webapps/plabdab-nano/static/downloads/vhh_sequences.csv.gz`

## Prerequisites

1. Run from project root:

```bash
cd /root/Projects/NOVA/NOVA-nanobody-filter
```

2. Use the same Python environment where project dependencies are installed.

## Run the Reproduction Script

```bash
python - <<'PY'
import asyncio
import csv
import gzip
import io
import re
import time
from urllib.request import urlopen

from metanano.config import SearchConfig
from metanano.services.search_service import SearchService
from metanano.utils.kmer import generate_kmers

URL = "https://opig.stats.ox.ac.uk/webapps/plabdab-nano/static/downloads/vhh_sequences.csv.gz"
AA = set("ACDEFGHIKLMNPQRSTVWY")


def find_sequence_column(fieldnames):
    candidates = [
        "sequence", "Sequence", "vhh_sequence", "vhh", "aa_sequence",
        "aa", "VHH sequence", "VHH_Sequence",
    ]
    lowered = {f.lower(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lowered:
            return lowered[c.lower()]
    for f in fieldnames:
        lf = f.lower()
        if "seq" in lf and "nt" not in lf and "nuc" not in lf:
            return f
    raise RuntimeError(f"No sequence-like column found. Columns: {fieldnames}")


def clean(seq: str) -> str:
    return re.sub(r"\s+", "", (seq or "").upper())


print("Downloading real VHH dataset from PLAbDab-nano...")
raw = urlopen(URL, timeout=60).read()
print(f"Downloaded bytes: {len(raw):,}")
text = gzip.decompress(raw).decode("utf-8", errors="replace")
reader = csv.DictReader(io.StringIO(text))

seq_col = find_sequence_column(reader.fieldnames or [])
print(f"Detected sequence column: {seq_col}")

real_sequences = []
for row in reader:
    s = clean(row.get(seq_col, ""))
    if not s:
        continue
    if set(s) - AA:
        continue
    if len(s) < 50 or len(s) > 220:
        continue
    real_sequences.append(s)
    if len(real_sequences) >= 600:
        break

if len(real_sequences) < 50:
    raise RuntimeError(f"Not enough valid real sequences extracted: {len(real_sequences)}")

print(f"Valid real sequences loaded: {len(real_sequences)}")

config = SearchConfig()
k = getattr(config, "k", 5)
svc = SearchService(config)

start_index = time.perf_counter()
for i, seq in enumerate(real_sequences):
    svc.index_sequence(
        seq_id=f"plabdab_{i}",
        sequence=seq,
        cdrs=None,
        kmers=generate_kmers(seq, k=k),
    )
index_ms = (time.perf_counter() - start_index) * 1000
print(f"Indexed: {svc._index_manager.size()} sequences in {index_ms:.1f} ms")

query = real_sequences[0]
mutated = query[:-2] + ("AA" if query[-2:] != "AA" else "VV")


async def run_search():
    job_id = await svc.submit_search([mutated], include_alignment=True)
    t0 = time.perf_counter()
    while True:
        job = await svc.get_job_status(job_id)
        if job and job.status.value in {"completed", "failed"}:
            elapsed = (time.perf_counter() - t0) * 1000
            return job, elapsed
        await asyncio.sleep(0.02)


job, elapsed_ms = asyncio.run(run_search())
print(f"Job status: {job.status.value}, latency: {elapsed_ms:.1f} ms")
if job.status.value != "completed":
    print(f"Error: {job.error}")
    raise SystemExit(1)

results = job.result or []
if not results:
    raise RuntimeError("No SearchResult payload returned")

r0 = results[0]
matches = r0.matches
print(f"Total candidates: {r0.total_candidates}, total indexed: {r0.total_indexed}, returned matches: {len(matches)}")
if not matches:
    raise RuntimeError("No matches found on real-data query")

print("Top 5 matches (real data):")
for m in matches[:5]:
    print(f"- id={m.target_id} identity={m.identity:.4f} tier={m.tier} score={m.score} cigar_len={len(m.cigar or '')}")

assert matches[0].identity >= 0.80, "Expected at least one high-similarity real-data hit"
print("REAL-DATA SEARCH TEST PASSED")
PY
```

## Expected Output (Example)

You should see output similar to:

```text
Downloading real VHH dataset from PLAbDab-nano...
Downloaded bytes: 334,071
Detected sequence column: sequence
Valid real sequences loaded: 600
Indexed: 600 sequences in 48.7 ms
Job status: completed, latency: 83.4 ms
Total candidates: 137, total indexed: 600, returned matches: 137
Top 5 matches (real data):
- id=plabdab_0 identity=0.9831 tier=exact score=621 cigar_len=6
...
REAL-DATA SEARCH TEST PASSED
```

Exact numbers will vary by environment and upstream dataset updates.

## Pass Criteria

- Job reaches `completed` status
- At least one match is returned
- Top match identity is at least `0.80`
- Final message prints: `REAL-DATA SEARCH TEST PASSED`

## Common Issues

- Network timeout downloading dataset:
  - rerun command, or increase URL timeout in script
- `No sequence-like column found`:
  - upstream schema changed; inspect CSV header and update column detection
- Very few valid sequences:
  - dataset format changed or filtering too strict; adjust length/character filters
- `SearchConfig` missing fields:
  - script already uses fallback (`getattr(config, "k", 5)`), keep this pattern
