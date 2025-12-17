"""
References / 参考:
    - docs/en/README.md: Section 1.1.2 - K-mer Index
    - docs/cn/README.md: 第1.1.2节 - K-mer 索引

File / 文件:
    - metanano/utils/kmer.py

Overview / 概述:
    K-mer generation and indexing utilities for sequence comparison.
    用于序列比较的 K-mer 生成和索引工具。

Consumers / 调用方:
    - metanano/utils/__init__.py
    - metanano/utils/similarity.py
"""

from typing import Dict, List, Set


def generate_kmers(sequence: str, k: int = 5) -> Set[str]:
    """
    Generate all k-mers from a sequence.
    从序列生成所有 k-mer。

    Args / 参数:
        sequence (str): The amino acid sequence.
            氨基酸序列。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。

    Returns / 返回:
        Set[str]: Set of unique k-mers.
            唯一 k-mer 的集合。

    Example / 示例:
        >>> kmers = generate_kmers("EVQLV", k=3)
        >>> print(kmers)
        {"EVQ", "VQL", "QLV"}

    Consumers / 调用方:
        - metanano/utils/similarity.py: compute_kmer_similarity
        - metanano/filters/diversity.py
    """
    if len(sequence) < k:
        return set()

    return {sequence[i : i + k] for i in range(len(sequence) - k + 1)}


def generate_kmers_with_counts(sequence: str, k: int = 5) -> Dict[str, int]:
    """
    Generate k-mers with their occurrence counts.
    生成 k-mer 及其出现次数。

    Args / 参数:
        sequence (str): The amino acid sequence.
            氨基酸序列。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。

    Returns / 返回:
        Dict[str, int]: Dictionary mapping k-mers to counts.
            k-mer 到计数的字典映射。

    Consumers / 调用方:
        - metanano/utils/similarity.py: weighted_minhash
    """
    if len(sequence) < k:
        return {}

    counts: Dict[str, int] = {}
    for i in range(len(sequence) - k + 1):
        kmer = sequence[i : i + k]
        counts[kmer] = counts.get(kmer, 0) + 1
    return counts


def build_kmer_index(sequences: List[str], k: int = 5) -> Dict[str, Set[int]]:
    """
    Build an inverted index mapping k-mers to sequence indices.
    构建将 k-mer 映射到序列索引的倒排索引。

    Args / 参数:
        sequences (List[str]): List of sequences to index.
            要索引的序列列表。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。

    Returns / 返回:
        Dict[str, Set[int]]: Mapping from k-mer to set of sequence indices.
            从 k-mer 到序列索引集合的映射。

    Example / 示例:
        >>> index = build_kmer_index(["EVQLV", "QVQLV"], k=3)
        >>> print(index["VQL"])
        {0, 1}

    Consumers / 调用方:
        - metanano/filters/diversity.py: Historical comparison
    """
    index: Dict[str, Set[int]] = {}

    for seq_idx, sequence in enumerate(sequences):
        kmers = generate_kmers(sequence, k)
        for kmer in kmers:
            if kmer not in index:
                index[kmer] = set()
            index[kmer].add(seq_idx)

    return index


def query_kmer_index(
    sequence: str,
    index: Dict[str, Set[int]],
    k: int = 5,
    min_shared: int = 1,
) -> Set[int]:
    """
    Query the k-mer index to find similar sequences.
    查询 k-mer 索引以查找相似序列。

    Args / 参数:
        sequence (str): Query sequence.
            查询序列。
        index (Dict[str, Set[int]]): K-mer index.
            K-mer 索引。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。
        min_shared (int): Minimum shared k-mers to include (default: 1).
            包含的最小共享 k-mer 数（默认：1）。

    Returns / 返回:
        Set[int]: Set of sequence indices that share k-mers.
            共享 k-mer 的序列索引集合。

    Consumers / 调用方:
        - metanano/filters/diversity.py: Fast candidate filtering
    """
    query_kmers = generate_kmers(sequence, k)
    candidate_counts: Dict[int, int] = {}

    for kmer in query_kmers:
        if kmer in index:
            for seq_idx in index[kmer]:
                candidate_counts[seq_idx] = candidate_counts.get(seq_idx, 0) + 1

    return {
        seq_idx
        for seq_idx, count in candidate_counts.items()
        if count >= min_shared
    }





