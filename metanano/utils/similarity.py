"""
References / 参考:
    - docs/en/README.md: Section 1.1.2 - Weighted MinHash
    - docs/cn/README.md: 第1.1.2节 - 加权 MinHash
    - datasketch library: MinHash implementation

File / 文件:
    - metanano/utils/similarity.py

Overview / 概述:
    Sequence similarity computation using k-mers and MinHash.
    使用 k-mer 和 MinHash 计算序列相似度。

Consumers / 调用方:
    - metanano/utils/__init__.py
    - metanano/filters/diversity.py
"""

from typing import Optional

from metanano.utils.kmer import generate_kmers, generate_kmers_with_counts


def compute_kmer_similarity(
    seq1: str,
    seq2: str,
    k: int = 5,
) -> float:
    """
    Compute Jaccard similarity between two sequences using k-mers.
    使用 k-mer 计算两个序列之间的 Jaccard 相似度。

    Args / 参数:
        seq1 (str): First sequence.
            第一个序列。
        seq2 (str): Second sequence.
            第二个序列。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。

    Returns / 返回:
        float: Jaccard similarity (0-1).
            Jaccard 相似度（0-1）。

    Example / 示例:
        >>> similarity = compute_kmer_similarity("EVQLVES", "QVQLVES", k=3)
        >>> print(f"{similarity:.2f}")
        0.80

    References / 参考:
        - metanano/utils/kmer.py: generate_kmers

    Consumers / 调用方:
        - metanano/filters/diversity.py: DiversityFilter.check_historical_similarity
    """
    kmers1 = generate_kmers(seq1, k)
    kmers2 = generate_kmers(seq2, k)

    if not kmers1 or not kmers2:
        return 0.0

    intersection = len(kmers1 & kmers2)
    union = len(kmers1 | kmers2)

    if union == 0:
        return 0.0

    return intersection / union


def weighted_minhash(
    seq1: str,
    seq2: str,
    k: int = 5,
    num_perm: int = 128,
) -> float:
    """
    Compute weighted MinHash similarity between sequences.
    计算序列之间的加权 MinHash 相似度。

    Uses datasketch library for efficient MinHash computation.
    使用 datasketch 库进行高效的 MinHash 计算。

    Args / 参数:
        seq1 (str): First sequence.
            第一个序列。
        seq2 (str): Second sequence.
            第二个序列。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。
        num_perm (int): Number of permutations for MinHash (default: 128).
            MinHash 的排列数（默认：128）。

    Returns / 返回:
        float: Estimated Jaccard similarity (0-1).
            估算的 Jaccard 相似度（0-1）。

    References / 参考:
        - datasketch library: MinHash

    Consumers / 调用方:
        - metanano/filters/diversity.py: DiversityFilter.check_historical_similarity
    """
    try:
        from datasketch import MinHash

        # Generate k-mers
        # 生成 k-mer
        kmers1 = generate_kmers(seq1, k)
        kmers2 = generate_kmers(seq2, k)

        if not kmers1 or not kmers2:
            return 0.0

        # Create MinHash objects
        # 创建 MinHash 对象
        m1 = MinHash(num_perm=num_perm)
        m2 = MinHash(num_perm=num_perm)

        for kmer in kmers1:
            m1.update(kmer.encode("utf-8"))
        for kmer in kmers2:
            m2.update(kmer.encode("utf-8"))

        return m1.jaccard(m2)

    except ImportError:
        # Fall back to exact computation if datasketch not available
        # 如果 datasketch 不可用，回退到精确计算
        return compute_kmer_similarity(seq1, seq2, k)


def weighted_jaccard(
    seq1: str,
    seq2: str,
    k: int = 5,
) -> float:
    """
    Compute weighted Jaccard similarity using k-mer counts.
    使用 k-mer 计数计算加权 Jaccard 相似度。

    Weights are based on k-mer frequency in each sequence.
    权重基于每个序列中 k-mer 的频率。

    Args / 参数:
        seq1 (str): First sequence.
            第一个序列。
        seq2 (str): Second sequence.
            第二个序列。
        k (int): K-mer length (default: 5).
            K-mer 长度（默认：5）。

    Returns / 返回:
        float: Weighted Jaccard similarity (0-1).
            加权 Jaccard 相似度（0-1）。

    Consumers / 调用方:
        - metanano/filters/diversity.py (alternative to MinHash)
    """
    counts1 = generate_kmers_with_counts(seq1, k)
    counts2 = generate_kmers_with_counts(seq2, k)

    if not counts1 or not counts2:
        return 0.0

    all_kmers = set(counts1.keys()) | set(counts2.keys())

    min_sum = 0
    max_sum = 0

    for kmer in all_kmers:
        c1 = counts1.get(kmer, 0)
        c2 = counts2.get(kmer, 0)
        min_sum += min(c1, c2)
        max_sum += max(c1, c2)

    if max_sum == 0:
        return 0.0

    return min_sum / max_sum





