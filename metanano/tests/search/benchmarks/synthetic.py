import random
from typing import Dict, List, Optional, Tuple

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"

AA_WEIGHTS = [
    8.2,
    5.5,
    6.1,
    6.8,
    3.9,
    7.1,
    2.2,
    5.8,
    5.9,
    9.6,
    2.4,
    4.3,
    4.7,
    3.9,
    5.1,
    6.9,
    5.9,
    1.4,
    3.2,
    6.6,
]


def _sample_sequence(rng: random.Random, length: int) -> str:
    return "".join(rng.choices(AMINO_ACIDS, weights=AA_WEIGHTS, k=length))


def _mutate_sequence(rng: random.Random, sequence: str, mutation_rate: float) -> str:
    letters = list(sequence)
    for idx, original in enumerate(letters):
        if rng.random() < mutation_rate:
            replacement = original
            while replacement == original:
                replacement = rng.choices(AMINO_ACIDS, weights=AA_WEIGHTS, k=1)[0]
            letters[idx] = replacement
    return "".join(letters)


def generate_synthetic_sequences(
    n: int,
    seed: int,
    avg_length: int = 120,
    similarity_clusters: int = 10,
) -> List[Tuple[str, str, Optional[Dict[str, str]]]]:
    if n <= 0:
        return []

    rng = random.Random(seed)
    cluster_count = max(1, min(similarity_clusters, n))
    bases: List[str] = []

    for _ in range(cluster_count):
        length = max(50, min(200, avg_length + rng.randint(-10, 10)))
        bases.append(_sample_sequence(rng, length))

    generated: List[Tuple[str, str, Optional[Dict[str, str]]]] = []
    for idx in range(n):
        base = bases[idx % cluster_count]
        mutation_rate = rng.uniform(0.05, 0.15)
        sequence = _mutate_sequence(rng, base, mutation_rate)
        generated.append((f"seq_{idx:07d}", sequence, None))

    return generated
