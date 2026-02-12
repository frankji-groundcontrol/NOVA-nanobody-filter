from metanano.tests.search.benchmarks.harness import BenchmarkResult, evaluate_tier1_gate


def test_evaluate_tier1_gate_passes_for_threshold_compliant_results() -> None:
    gate = evaluate_tier1_gate(
        {
            10_000: BenchmarkResult(
                n_indexed=10_000,
                rss_mb=150.0,
                index_build_seconds=1.0,
                p50_query_ms=80.0,
                p99_query_ms=150.0,
                queries_per_second=50.0,
            ),
            100_000: BenchmarkResult(
                n_indexed=100_000,
                rss_mb=450.0,
                index_build_seconds=8.0,
                p50_query_ms=200.0,
                p99_query_ms=450.0,
                queries_per_second=20.0,
            ),
        }
    )

    assert gate[10_000] is True
    assert gate[100_000] is True


def test_evaluate_tier1_gate_fails_when_thresholds_exceeded() -> None:
    gate = evaluate_tier1_gate(
        {
            10_000: BenchmarkResult(
                n_indexed=10_000,
                rss_mb=300.0,
                index_build_seconds=1.0,
                p50_query_ms=80.0,
                p99_query_ms=250.0,
                queries_per_second=50.0,
            ),
            100_000: BenchmarkResult(
                n_indexed=100_000,
                rss_mb=600.0,
                index_build_seconds=8.0,
                p50_query_ms=200.0,
                p99_query_ms=550.0,
                queries_per_second=20.0,
            ),
        }
    )

    assert gate[10_000] is False
    assert gate[100_000] is False
