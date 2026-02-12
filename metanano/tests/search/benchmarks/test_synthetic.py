from metanano.tests.search.benchmarks.harness import _select_query_sequences, run_benchmark
from metanano.tests.search.benchmarks.synthetic import generate_synthetic_sequences


def test_generate_synthetic_sequences_reproducible() -> None:
    left = generate_synthetic_sequences(100, seed=42)
    right = generate_synthetic_sequences(100, seed=42)

    assert len(left) == 100
    assert left == right


def test_generate_synthetic_sequences_valid_amino_acids() -> None:
    valid = set("ACDEFGHIKLMNPQRSTVWY")
    generated = generate_synthetic_sequences(50, seed=7)

    assert generated
    for _, sequence, _ in generated:
        assert set(sequence).issubset(valid)


def test_run_benchmark_returns_positive_metrics() -> None:
    result = run_benchmark(n=100, n_queries=5, seed=42)

    assert result.n_indexed == 100
    assert result.rss_mb > 0.0
    assert result.index_build_seconds > 0.0
    assert result.p50_query_ms > 0.0
    assert result.p99_query_ms > 0.0
    assert result.queries_per_second > 0.0


def test_select_query_sequences_is_seeded_and_bounded() -> None:
    synthetic = [(f"id_{idx}", f"SEQ_{idx}", None) for idx in range(30)]
    left = _select_query_sequences(synthetic, query_count=8, seed=123)
    right = _select_query_sequences(synthetic, query_count=8, seed=123)

    assert left == right
    assert len(left) == 8
    assert all(seq.startswith("SEQ_") for seq in left)
