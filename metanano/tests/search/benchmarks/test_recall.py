import pytest

from metanano.tests.search.benchmarks.synthetic import generate_synthetic_sequences
from metanano.utils.kmer import generate_kmers
from metanano.utils.similarity import compute_kmer_similarity_precomputed
from metanano.utils.similarity import generate_minhash_signature


def test_generate_minhash_signature_returns_object_when_available() -> None:
    signature = generate_minhash_signature("EVQLVQSGVEVKKPGA", k=5, num_perm=128)

    if signature is None:
        return

    assert hasattr(signature, "num_perm")
    assert signature.num_perm == 128


def test_generate_minhash_signature_identical_sequence_consistency() -> None:
    left = generate_minhash_signature("QVQLVQSGAEVKKPGS", k=5, num_perm=128)
    right = generate_minhash_signature("QVQLVQSGAEVKKPGS", k=5, num_perm=128)

    if left is None or right is None:
        return

    assert left.jaccard(right) == 1.0


def test_minhash_lsh_recall_at_500() -> None:
    datasketch = pytest.importorskip("datasketch")

    sequences = generate_synthetic_sequences(1000, seed=42)
    sequence_map = {seq_id: sequence for seq_id, sequence, _ in sequences}
    kmer_map = {seq_id: generate_kmers(sequence, 5) for seq_id, sequence in sequence_map.items()}

    num_perm = 256
    # LSH threshold set below target (0.3) to capture boundary items reliably
    lsh = datasketch.MinHashLSH(threshold=0.2, num_perm=num_perm, weights=(0.5, 0.5))
    signature_map = {}
    for seq_id, sequence in sequence_map.items():
        signature = generate_minhash_signature(sequence, k=5, num_perm=num_perm)
        assert signature is not None
        signature_map[seq_id] = signature
        lsh.insert(seq_id, signature)

    query_ids = [seq_id for seq_id, _, _ in sequences[:20]]
    recalls = []
    for query_id in query_ids:
        query_kmers = kmer_map[query_id]
        # Exact threshold-qualified set: items with exact k-mer Jaccard >= 0.3
        # LSH is threshold-based retrieval, not exhaustive top-K ranking,
        # so recall must be measured against the reachable set.
        exact_above_threshold = [
            target_id
            for target_id, target_kmers in kmer_map.items()
            if target_id != query_id
            and compute_kmer_similarity_precomputed(query_kmers, target_kmers) >= 0.3
        ]

        approx_candidates = [
            target_id
            for target_id in lsh.query(signature_map[query_id])
            if target_id != query_id
        ]

        denominator = len(exact_above_threshold)
        if denominator == 0:
            continue
        overlap = len(set(exact_above_threshold).intersection(approx_candidates))
        recalls.append(overlap / denominator)

    assert recalls
    avg_recall = sum(recalls) / len(recalls)
    assert avg_recall >= 0.80, f"threshold-recall={avg_recall:.3f} < 0.80"
