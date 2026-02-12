import pytest

from metanano.config import CoarseFilterConfig, LSHConfig, SearchConfig
from metanano.search.index_manager import IndexManager
from metanano.search.search_engine import SearchEngine, SearchResult
from metanano.tests.search.benchmarks.synthetic import generate_synthetic_sequences
from metanano.utils.alignment import AlignmentEngine
from metanano.utils.kmer import generate_kmers


def _build_index(config: SearchConfig, n: int = 1000) -> tuple[IndexManager, dict[str, str]]:
    manager = IndexManager(config)
    sequence_map: dict[str, str] = {}
    for seq_id, sequence, cdrs in generate_synthetic_sequences(n, seed=42):
        sequence_map[seq_id] = sequence
        manager.add_sequence(seq_id, sequence, cdrs, generate_kmers(sequence, config.k))
    return manager, sequence_map


def test_tier2_recall_gate_recall_at_500() -> None:
    pytest.importorskip("datasketch")

    base_coarse = CoarseFilterConfig(
        min_shared_kmers=1,
        jaccard_threshold=0.3,
        max_candidates=500,
    )
    tuned_lsh = LSHConfig(num_perm=256, lsh_threshold=0.2)
    exact_config = SearchConfig(coarse_filter=base_coarse)
    lsh_config = SearchConfig(
        coarse_filter=base_coarse.model_copy(update={"retrieval_strategy": "lsh"}),
        lsh=tuned_lsh,
    )

    exact_index, sequence_map = _build_index(exact_config)
    lsh_index, _ = _build_index(lsh_config)

    query_ids = list(sequence_map.keys())[:50]
    recalls: list[float] = []
    for query_id in query_ids:
        query_kmers = generate_kmers(sequence_map[query_id], exact_config.k)
        exact_top = exact_index.coarse_filter(
            query_kmers=query_kmers,
            min_shared=1,
            jaccard_threshold=0.3,
            max_candidates=500,
            exclude_ids={query_id},
        )
        lsh_top = lsh_index.lsh_query(
            query_kmers=query_kmers,
            max_candidates=500,
            exclude_ids={query_id},
        )

        denominator = len(exact_top)
        if denominator == 0:
            continue
        overlap = len(set(exact_top).intersection(lsh_top))
        recalls.append(overlap / denominator)

    assert recalls
    avg_recall = sum(recalls) / len(recalls)
    assert avg_recall >= 0.80, f"threshold-recall={avg_recall:.3f} < 0.80"


def test_tier2_kmer_strategy_search_result_valid() -> None:
    kmer_config = SearchConfig()
    kmer_index, sequence_map = _build_index(kmer_config, n=200)

    query = next(iter(sequence_map.values()))
    kmer_engine = SearchEngine(kmer_config, kmer_index, AlignmentEngine(kmer_config.fine_alignment))
    kmer_result = kmer_engine.search(query)

    assert isinstance(kmer_result, SearchResult)
    assert kmer_result.total_indexed == 200


def test_tier2_lsh_strategy_search_result_valid() -> None:
    pytest.importorskip("datasketch")

    lsh_config = SearchConfig(
        coarse_filter=CoarseFilterConfig(retrieval_strategy="lsh"),
    )

    lsh_index, sequence_map = _build_index(lsh_config, n=200)

    query = next(iter(sequence_map.values()))
    lsh_engine = SearchEngine(lsh_config, lsh_index, AlignmentEngine(lsh_config.fine_alignment))
    lsh_result = lsh_engine.search(query)

    assert isinstance(lsh_result, SearchResult)
    assert lsh_result.total_indexed == 200
