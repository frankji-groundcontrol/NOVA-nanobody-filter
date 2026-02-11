"""
References / 参考:
    - docs/en/README.md: Section 1.1.2 - K-mer Index
    - docs/cn/README.md: 第1.1.2节 - K-mer 索引
    - metanano/utils/kmer.py: build_kmer_index, query_kmer_index

File / 文件:
    - metanano/search/index_manager.py

Overview / 概述:
    Thread-safe in-memory k-mer inverted index with two-stage coarse filter.
    线程安全的内存 k-mer 倒排索引，带两阶段粗过滤。

    Replaces brute-force O(N) Jaccard comparison in diversity.py with a
    coarse filter that quickly narrows candidates before precise scoring.
    替换 diversity.py 中的暴力 O(N) Jaccard 比较，使用粗过滤快速缩小候选范围。

Consumers / 调用方:
    - metanano/search/__init__.py
    - metanano/pipeline.py (future)
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from metanano.config import SearchConfig
from metanano.utils.similarity import compute_kmer_similarity_precomputed


@dataclass
class SequenceRecord:
    """
    Stored record for an indexed sequence.
    已索引序列的存储记录。

    Attributes / 属性:
        id (str): Unique sequence identifier.
            唯一序列标识符。
        sequence (str): Full amino acid sequence.
            完整氨基酸序列。
        cdrs (Optional[Dict[str, str]]): CDR regions (may be None if extraction failed).
            CDR 区域（如果提取失败则为 None）。
        kmers (Set[str]): Pre-generated k-mer set for this sequence.
            此序列的预生成 k-mer 集合。

    Consumers / 调用方:
        - metanano/search/index_manager.py: IndexManager
    """

    id: str
    sequence: str
    cdrs: Optional[Dict[str, str]]
    kmers: Set[str] = field(default_factory=set)


class IndexManager:
    """
    Thread-safe in-memory k-mer inverted index with two-stage coarse filter.
    线程安全的内存 k-mer 倒排索引，带两阶段粗过滤。

    The two-stage coarse filter:
        Stage 1: Count shared k-mers per candidate, filter by min_shared.
        Stage 2: Compute Jaccard on survivors, filter by jaccard_threshold.
        Stage 3: Sort by Jaccard descending, cap at max_candidates.
    两阶段粗过滤：
        阶段 1：统计每个候选的共享 k-mer 数量，按 min_shared 过滤。
        阶段 2：对幸存者计算 Jaccard，按 jaccard_threshold 过滤。
        阶段 3：按 Jaccard 降序排序，限制在 max_candidates 以内。

    Args:
        config (SearchConfig): Search configuration containing coarse filter params.
            搜索配置，包含粗过滤参数。

    Example / 示例:
        >>> from metanano.config import SearchConfig
        >>> from metanano.utils.kmer import generate_kmers
        >>> mgr = IndexManager(SearchConfig())
        >>> kmers = generate_kmers("EVQLVQSGVEVKKPGA", 5)
        >>> mgr.add_sequence("seq_0", "EVQLVQSGVEVKKPGA", None, kmers)
        >>> mgr.size()
        1

    Consumers / 调用方:
        - metanano/search/__init__.py
        - metanano/pipeline.py (future)
    """

    def __init__(self, config: SearchConfig) -> None:
        """
        Initialize IndexManager with search configuration.
        使用搜索配置初始化 IndexManager。

        Args:
            config (SearchConfig): Search configuration for coarse filtering.
                粗过滤相关的搜索配置。
        """
        self._config = config
        self._inverted_index: Dict[str, Set[int]] = {}
        self._records: List[SequenceRecord] = []
        self._lock = threading.Lock()

    def add_sequence(
        self,
        seq_id: str,
        sequence: str,
        cdrs: Optional[Dict[str, str]],
        kmers: Set[str],
    ) -> None:
        """
        Thread-safe append of a sequence to the index.
        线程安全地将序列追加到索引中。

        Args:
            seq_id (str): Unique identifier for this sequence.
                此序列的唯一标识符。
            sequence (str): Full amino acid sequence.
                完整氨基酸序列。
            cdrs (Optional[Dict[str, str]]): CDR regions or None.
                CDR 区域或 None。
            kmers (Set[str]): Pre-generated k-mer set.
                预生成的 k-mer 集合。
        """
        with self._lock:
            idx = len(self._records)
            record = SequenceRecord(
                id=seq_id,
                sequence=sequence,
                cdrs=cdrs,
                kmers=kmers,
            )
            self._records.append(record)

            for kmer in kmers:
                if kmer not in self._inverted_index:
                    self._inverted_index[kmer] = set()
                self._inverted_index[kmer].add(idx)

    def coarse_filter(
        self,
        query_kmers: Set[str],
        min_shared: int,
        jaccard_threshold: float,
        max_candidates: int,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[int]:
        """
        Two-stage coarse filter returning candidate indices sorted by Jaccard descending.
        两阶段粗过滤，返回按 Jaccard 降序排序的候选索引。

        Stage 1: Count shared k-mers per candidate, keep those >= min_shared.
        Stage 2: Compute Jaccard similarity on survivors, keep those >= jaccard_threshold.
        Stage 3: Sort by Jaccard descending, cap at max_candidates.
        阶段 1：统计每个候选共享的 k-mer 数量，保留 >= min_shared 的。
        阶段 2：对幸存者计算 Jaccard 相似度，保留 >= jaccard_threshold 的。
        阶段 3：按 Jaccard 降序排序，限制在 max_candidates 以内。

        Args:
            query_kmers (Set[str]): K-mers of the query sequence.
                查询序列的 k-mer 集合。
            min_shared (int): Minimum shared k-mers for stage 1.
                阶段 1 的最小共享 k-mer 数。
            jaccard_threshold (float): Minimum Jaccard for stage 2.
                阶段 2 的最小 Jaccard 相似度。
            max_candidates (int): Maximum candidates to return.
                返回的最大候选数。
            exclude_ids (Optional[Set[str]]): Sequence IDs to exclude from results.
                从结果中排除的序列 ID 集合。

        Returns:
            List[int]: Candidate record indices sorted by Jaccard similarity descending.
                按 Jaccard 相似度降序排序的候选记录索引列表。
        """
        if exclude_ids is None:
            exclude_ids = set()

        # Stage 1: Count shared k-mers per candidate
        # 阶段 1：统计每个候选的共享 k-mer 数量
        candidate_counts: Dict[int, int] = {}
        with self._lock:
            for kmer in query_kmers:
                if kmer in self._inverted_index:
                    for idx in self._inverted_index[kmer]:
                        candidate_counts[idx] = candidate_counts.get(idx, 0) + 1

            # Filter by min_shared and exclude_ids
            # 按 min_shared 和 exclude_ids 过滤
            stage1_survivors: List[int] = [
                idx
                for idx, count in candidate_counts.items()
                if count >= min_shared and self._records[idx].id not in exclude_ids
            ]

            # Stage 2: Compute Jaccard on survivors
            # 阶段 2：对幸存者计算 Jaccard
            scored: List[tuple[int, float]] = []
            for idx in stage1_survivors:
                jaccard = compute_kmer_similarity_precomputed(
                    query_kmers, self._records[idx].kmers
                )
                if jaccard >= jaccard_threshold:
                    scored.append((idx, jaccard))

        # Stage 3: Sort by Jaccard descending, cap at max_candidates
        # 阶段 3：按 Jaccard 降序排序，限制在 max_candidates
        scored.sort(key=lambda x: (-x[1], self._records[x[0]].id))
        return [idx for idx, _ in scored[:max_candidates]]

    def get_record(self, index: int) -> SequenceRecord:
        """
        Retrieve a stored SequenceRecord by index.
        通过索引检索存储的 SequenceRecord。

        Args:
            index (int): Record index (0-based).
                记录索引（从 0 开始）。

        Returns:
            SequenceRecord: The stored sequence record.
                存储的序列记录。
        """
        return self._records[index]

    def size(self) -> int:
        """
        Return the number of indexed sequences.
        返回已索引序列的数量。

        Returns:
            int: Number of records in the index.
                索引中的记录数。
        """
        return len(self._records)

    def clear(self) -> None:
        """
        Remove all indexed sequences (for test cleanup).
        移除所有已索引序列（用于测试清理）。
        """
        with self._lock:
            self._inverted_index.clear()
            self._records.clear()
