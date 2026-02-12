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
from importlib import import_module
from typing import Dict, List, Optional, Set
from typing import Protocol, cast

from metanano.config import SearchConfig
from metanano.utils.similarity import generate_minhash_signature


class MinHashLike(Protocol):
    num_perm: int

    def update(self, value: bytes) -> None: ...

    def jaccard(self, other: "MinHashLike") -> float: ...


class MinHashFactory(Protocol):
    def __call__(self, *, num_perm: int) -> MinHashLike: ...


class MinHashLSHLike(Protocol):
    def insert(self, key: str, minhash: MinHashLike) -> None: ...

    def query(self, minhash: MinHashLike) -> List[str]: ...


class MinHashLSHFactory(Protocol):
    def __call__(
        self,
        *,
        threshold: float,
        num_perm: int,
        weights: tuple[float, float],
    ) -> MinHashLSHLike: ...


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
        kmer_count (int): Number of unique k-mers for this sequence.
            此序列的唯一 k-mer 数量。

    Consumers / 调用方:
        - metanano/search/index_manager.py: IndexManager
    """

    id: str
    sequence: str
    cdrs: Optional[Dict[str, str]]
    kmer_count: int = field(default=0)


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
        self._inverted_index: Dict[int, List[int]] = {}
        self._records: List[SequenceRecord] = []
        self._seq_to_ids: Dict[str, Set[str]] = {}
        self._id_to_idx: Dict[str, int] = {}
        self._lsh_index: Optional[MinHashLSHLike] = None
        self._minhash_signatures: Dict[int, MinHashLike] = {}
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
            hashed_kmers = frozenset(hash(kmer) for kmer in kmers)
            record = SequenceRecord(
                id=seq_id,
                sequence=sequence,
                cdrs=cdrs,
                kmer_count=len(hashed_kmers),
            )
            self._records.append(record)
            self._id_to_idx[seq_id] = idx
            if sequence not in self._seq_to_ids:
                self._seq_to_ids[sequence] = set()
            self._seq_to_ids[sequence].add(seq_id)

            if self._config.coarse_filter.retrieval_strategy == "lsh":
                signature = generate_minhash_signature(
                    sequence,
                    k=self._config.k,
                    num_perm=self._config.lsh.num_perm,
                )
                if signature is None:
                    raise RuntimeError("datasketch is required for retrieval_strategy='lsh'")
                if self._lsh_index is None:
                    self._lsh_index = self._create_lsh_index()
                self._lsh_index.insert(seq_id, signature)
                self._minhash_signatures[idx] = signature

            for kmer in hashed_kmers:
                if kmer not in self._inverted_index:
                    self._inverted_index[kmer] = []
                self._inverted_index[kmer].append(idx)

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
        query_hashes = frozenset(hash(kmer) for kmer in query_kmers)
        query_count = len(query_hashes)
        candidate_counts: Dict[int, int] = {}
        with self._lock:
            for kmer in query_hashes:
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
                intersection = candidate_counts[idx]
                union = query_count + self._records[idx].kmer_count - intersection
                jaccard = 0.0 if union <= 0 else intersection / union
                if jaccard >= jaccard_threshold:
                    scored.append((idx, jaccard))

        # Stage 3: Sort by Jaccard descending, cap at max_candidates
        # 阶段 3：按 Jaccard 降序排序，限制在 max_candidates
        scored.sort(key=lambda x: (-x[1], self._records[x[0]].id))
        return [idx for idx, _ in scored[:max_candidates]]

    def lsh_query(
        self,
        query_kmers: Set[str],
        max_candidates: int,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[int]:
        if exclude_ids is None:
            exclude_ids = set()
        if not query_kmers or max_candidates <= 0:
            return []

        with self._lock:
            if not self._records:
                return []

            if self._lsh_index is None or len(self._minhash_signatures) != len(self._records):
                self._build_lsh_index_locked()

            minhash_factory = self._get_minhash_factory()
            query_signature = minhash_factory(num_perm=self._config.lsh.num_perm)
            for kmer in query_kmers:
                query_signature.update(kmer.encode("utf-8"))

            assert self._lsh_index is not None
            candidate_ids = self._lsh_index.query(query_signature)

            scored: List[tuple[int, float]] = []
            for seq_id in candidate_ids:
                if seq_id in exclude_ids:
                    continue
                idx = self._id_to_idx.get(seq_id)
                if idx is None:
                    continue
                signature = self._minhash_signatures.get(idx)
                if signature is None:
                    continue
                scored.append((idx, query_signature.jaccard(signature)))

        scored.sort(key=lambda item: (-item[1], self._records[item[0]].id))
        return [idx for idx, _ in scored[:max_candidates]]

    def build_lsh_index(self) -> None:
        with self._lock:
            self._build_lsh_index_locked()

    def _build_lsh_index_locked(self) -> None:
        lsh_index = self._create_lsh_index()
        signatures: Dict[int, MinHashLike] = {}

        for idx, record in enumerate(self._records):
            signature = generate_minhash_signature(
                record.sequence,
                k=self._config.k,
                num_perm=self._config.lsh.num_perm,
            )
            if signature is None:
                raise RuntimeError("datasketch is required for MinHashLSH retrieval")
            lsh_index.insert(record.id, signature)
            signatures[idx] = signature

        self._lsh_index = lsh_index
        self._minhash_signatures = signatures

    def _create_lsh_index(self) -> MinHashLSHLike:
        minhash_lsh_factory = self._get_minhash_lsh_factory()
        return minhash_lsh_factory(
            threshold=self._config.lsh.lsh_threshold,
            num_perm=self._config.lsh.num_perm,
            weights=self._config.lsh.weights,
        )

    def _get_minhash_factory(self) -> MinHashFactory:
        try:
            datasketch = import_module("datasketch")
        except ImportError as exc:
            raise RuntimeError("datasketch is required for MinHashLSH retrieval") from exc
        return cast(MinHashFactory, getattr(datasketch, "MinHash"))

    def _get_minhash_lsh_factory(self) -> MinHashLSHFactory:
        try:
            datasketch = import_module("datasketch")
        except ImportError as exc:
            raise RuntimeError("datasketch is required for MinHashLSH retrieval") from exc
        return cast(MinHashLSHFactory, getattr(datasketch, "MinHashLSH"))

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

    def get_ids_for_sequence(self, sequence: str) -> Set[str]:
        with self._lock:
            return set(self._seq_to_ids.get(sequence, set()))

    def get_record_by_id(self, seq_id: str) -> Optional[SequenceRecord]:
        with self._lock:
            idx = self._id_to_idx.get(seq_id)
            if idx is None:
                return None
            return self._records[idx]

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
            self._seq_to_ids.clear()
            self._id_to_idx.clear()
            self._lsh_index = None
            self._minhash_signatures.clear()
