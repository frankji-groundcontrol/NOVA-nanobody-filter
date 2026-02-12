import random
import statistics
import time
import tracemalloc
from dataclasses import dataclass
from typing import Sequence

from metanano.config import SearchConfig
from metanano.search.index_manager import IndexManager
from metanano.search.search_engine import SearchEngine
from metanano.tests.search.benchmarks.synthetic import generate_synthetic_sequences
from metanano.utils.alignment import AlignmentEngine
from metanano.utils.kmer import generate_kmers


TIER1_GATE_THRESHOLDS = {
    10_000: {"rss_mb": 200.0, "p99_query_ms": 200.0},
    100_000: {"rss_mb": 500.0, "p99_query_ms": 500.0},
}


@dataclass
class BenchmarkResult:
    n_indexed: int
    rss_mb: float
    index_build_seconds: float
    p50_query_ms: float
    p99_query_ms: float
    queries_per_second: float


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = int(round((len(values) - 1) * percentile))
    ordered = sorted(values)
    return ordered[max(0, min(rank, len(ordered) - 1))]


def _select_query_sequences(
    synthetic: Sequence[tuple[str, str, object | None]],
    query_count: int,
    seed: int,
) -> list[str]:
    rng = random.Random(seed)
    selected = rng.sample(synthetic, query_count)
    return [sequence for _, sequence, _ in selected]


def run_benchmark(n: int, n_queries: int = 100, seed: int = 42) -> BenchmarkResult:
    if n <= 0:
        raise ValueError("n must be positive")

    config = SearchConfig()
    index_manager = IndexManager(config)
    alignment_engine = AlignmentEngine(config.fine_alignment)
    search_engine = SearchEngine(config, index_manager, alignment_engine)
    synthetic = generate_synthetic_sequences(n=n, seed=seed)

    tracemalloc.start()
    build_started = time.perf_counter()
    for seq_id, sequence, cdrs in synthetic:
        kmers = generate_kmers(sequence, k=config.k)
        index_manager.add_sequence(seq_id, sequence, cdrs, kmers)
    index_build_seconds = time.perf_counter() - build_started

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    query_count = min(max(1, n_queries), len(synthetic))
    query_sequences = _select_query_sequences(synthetic, query_count, seed)

    query_latencies_ms: list[float] = []
    query_started = time.perf_counter()
    for query in query_sequences:
        one_started = time.perf_counter()
        search_engine.search(query, include_alignment=False)
        query_latencies_ms.append((time.perf_counter() - one_started) * 1000.0)
    total_query_seconds = max(1e-9, time.perf_counter() - query_started)

    p50 = statistics.median(query_latencies_ms)
    p99 = _percentile(query_latencies_ms, 0.99)
    qps = query_count / total_query_seconds

    return BenchmarkResult(
        n_indexed=len(synthetic),
        rss_mb=peak / (1024.0 * 1024.0),
        index_build_seconds=index_build_seconds,
        p50_query_ms=p50,
        p99_query_ms=p99,
        queries_per_second=qps,
    )


def evaluate_tier1_gate(results_by_size: dict[int, BenchmarkResult]) -> dict[int, bool]:
    outcomes: dict[int, bool] = {}
    for size, limits in TIER1_GATE_THRESHOLDS.items():
        result = results_by_size[size]
        outcomes[size] = (
            result.rss_mb < limits["rss_mb"]
            and result.p99_query_ms < limits["p99_query_ms"]
        )
    return outcomes
