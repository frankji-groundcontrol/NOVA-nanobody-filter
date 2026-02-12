"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Sequence Search
    - docs/cn/README.md: 第1.1节 - 序列搜索
    - metanano/search/index_manager.py: coarse candidate filtering
    - metanano/utils/alignment.py: fine alignment scoring

File / 文件:
    - metanano/search/search_engine.py

Overview / 概述:
    Unified search pipeline orchestrating coarse filter, fine alignment,
    and CDR similarity comparison.
    统一搜索流水线，编排粗过滤、精细对齐和 CDR 相似度比较。

Consumers / 调用方:
    - metanano/search/__init__.py
    - metanano/routes/search_routes.py (future)
"""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from metanano.config import SearchConfig
from metanano.search.index_manager import IndexManager
from metanano.utils.alignment import AlignmentEngine
from metanano.utils.cdr_utils import extract_cdrs
from metanano.utils.kmer import generate_kmers


@dataclass
class SearchMatch:
    """
    Ranked search match after fine alignment.
    精细对齐后的排序匹配结果。

    Attributes / 属性:
        target_id (str): Matched sequence identifier.
            匹配序列标识符。
        target_sequence (str): Matched sequence text.
            匹配序列文本。
        score (int): Alignment score.
            对齐分数。
        identity (float): Alignment identity ratio (0.0-1.0).
            对齐一致性比例（0.0-1.0）。
        tier (str): Cosmetic tier label from identity thresholds.
            由一致性阈值得到的分层标签。
        cigar (Optional[str]): Alignment CIGAR string.
            对齐 CIGAR 字符串。
        aligned_query (Optional[str]): Aligned query with gaps.
            包含 gap 的对齐查询序列。
        aligned_target (Optional[str]): Aligned target with gaps.
            包含 gap 的对齐目标序列。
        cdr_similarity (Optional[Dict[str, float]]): Per-CDR similarity scores.
            各 CDR 区域相似度分数。

    Consumers / 调用方:
        - metanano/search/search_engine.py: SearchEngine.search
    """

    target_id: str
    target_sequence: str
    score: int
    identity: float
    tier: str
    cigar: Optional[str]
    aligned_query: Optional[str]
    aligned_target: Optional[str]
    cdr_similarity: Optional[Dict[str, float]]


@dataclass
class SearchResult:
    """
    Search response payload for a single query.
    单次查询的搜索响应载荷。

    Attributes / 属性:
        query_sequence (str): Input query sequence.
            输入查询序列。
        matches (List[SearchMatch]): Ranked matches.
            排序后的匹配列表。
        total_candidates (int): Number of coarse-filter candidates.
            粗过滤候选数量。
        total_indexed (int): Number of indexed sequences.
            索引中的序列总数。
        elapsed_ms (float): End-to-end latency in milliseconds.
            端到端耗时（毫秒）。

    Consumers / 调用方:
        - metanano/search/search_engine.py: SearchEngine.search
    """

    query_sequence: str
    matches: List[SearchMatch]
    total_candidates: int
    total_indexed: int
    elapsed_ms: float


class SearchEngine:
    """
    MapReduce-style search orchestrator for one query at a time.
    面向单条查询的 MapReduce 风格搜索编排器。

    Pipeline:
        1) Coarse filter by k-mer overlap/Jaccard.
        2) Fine alignment in parallel threads.
        3) Optional CDR comparison from pre-extracted annotations.
    流水线：
        1）基于 k-mer 重叠/Jaccard 的粗过滤；
        2）并行线程执行精细对齐；
        3）基于预提取注释的可选 CDR 比较。

    Args:
        config (SearchConfig): Search configuration.
            搜索配置。
        index_manager (IndexManager): Indexed sequence storage and coarse filter.
            索引序列存储与粗过滤管理器。
        alignment_engine (AlignmentEngine): Fine alignment backend.
            精细对齐后端。

    Consumers / 调用方:
        - metanano/search/__init__.py
        - metanano/routes/search_routes.py (future)
    """

    _BATCH_SIZE: int = 16

    def __init__(
        self,
        config: SearchConfig,
        index_manager: IndexManager,
        alignment_engine: AlignmentEngine,
    ) -> None:
        """
        Initialize SearchEngine with injected dependencies.
        使用注入依赖初始化 SearchEngine。

        Args:
            config (SearchConfig): Search configuration.
                搜索配置。
            index_manager (IndexManager): Indexed storage and coarse filter manager.
                索引存储与粗过滤管理器。
            alignment_engine (AlignmentEngine): Fine alignment backend.
                精细对齐后端。
        """
        self._config = config
        self._index_manager = index_manager
        self._alignment_engine = alignment_engine

    def search(
        self,
        query: str,
        include_alignment: bool = False,
        exclude_ids: Optional[Set[str]] = None,
        coarse_min_shared: Optional[int] = None,
        coarse_jaccard: Optional[float] = None,
    ) -> SearchResult:
        """
        Run full search workflow for one query sequence.
        对单条查询序列执行完整搜索流程。

        Args:
            query (str): Query amino-acid sequence.
                查询氨基酸序列。
            include_alignment (bool): Include aligned strings in each match.
                是否在每个匹配中返回对齐字符串。
            exclude_ids (Optional[Set[str]]): Target IDs to exclude.
                需要排除的目标 ID 集合。
            coarse_min_shared (Optional[int]): Override coarse min shared k-mers.
                覆盖粗过滤最小共享 k-mer 数。
            coarse_jaccard (Optional[float]): Override coarse Jaccard threshold.
                覆盖粗过滤 Jaccard 阈值。

        Returns:
            SearchResult: Ranked search output and metadata.
                排序后的搜索输出及元数据。
        """
        started = time.perf_counter()

        k = self._config.k
        query_kmers = generate_kmers(query, k=k)

        min_shared = (
            coarse_min_shared
            if coarse_min_shared is not None
            else self._config.coarse_filter.min_shared_kmers
        )
        jaccard_threshold = (
            coarse_jaccard
            if coarse_jaccard is not None
            else self._config.coarse_filter.jaccard_threshold
        )
        max_candidates = self._config.coarse_filter.max_candidates

        final_exclude_ids = set(exclude_ids or set())
        final_exclude_ids.update(self._index_manager.get_ids_for_sequence(query))

        if self._config.coarse_filter.retrieval_strategy == "lsh":
            candidate_indices = self._index_manager.lsh_query(
                query_kmers=query_kmers,
                max_candidates=max_candidates,
                exclude_ids=final_exclude_ids,
            )
        else:
            candidate_indices = self._index_manager.coarse_filter(
                query_kmers=query_kmers,
                min_shared=min_shared,
                jaccard_threshold=jaccard_threshold,
                max_candidates=max_candidates,
                exclude_ids=final_exclude_ids,
            )

        query_cdrs = self._resolve_query_cdrs(query)
        matches: List[SearchMatch] = []

        if candidate_indices:
            batch_size = max(1, self._BATCH_SIZE)
            candidate_batches = [
                candidate_indices[idx : idx + batch_size]
                for idx in range(0, len(candidate_indices), batch_size)
            ]
            max_workers = max(1, min(32, len(candidate_batches)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(
                        self._align_batch,
                        query,
                        candidate_batch,
                        include_alignment,
                        query_cdrs,
                    )
                    for candidate_batch in candidate_batches
                ]
                matches = [
                    match
                    for future in futures
                    for match in future.result()
                ]

        matches.sort(key=lambda match: (-match.identity, match.target_id))
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        return SearchResult(
            query_sequence=query,
            matches=matches,
            total_candidates=len(candidate_indices),
            total_indexed=self._index_manager.size(),
            elapsed_ms=elapsed_ms,
        )

    def _align_candidate(
        self,
        query: str,
        candidate_index: int,
        include_alignment: bool,
        query_cdrs: Optional[Dict[str, str]],
    ) -> SearchMatch:
        """
        Align query to one candidate and materialize SearchMatch.
        将查询与单个候选对齐并构建 SearchMatch。

        Args:
            query (str): Query amino-acid sequence.
                查询氨基酸序列。
            candidate_index (int): Index of candidate record in IndexManager.
                IndexManager 中候选记录的索引。
            include_alignment (bool): Whether aligned strings are included.
                是否包含对齐字符串。
            query_cdrs (Optional[Dict[str, str]]): Query CDR annotations.
                查询序列 CDR 注释。

        Returns:
            SearchMatch: Ranked candidate match with alignment and CDR metrics.
                包含对齐与 CDR 指标的候选匹配结果。
        """
        target_record = self._index_manager.get_record(candidate_index)
        alignment = self._alignment_engine.align(
            query,
            target_record.sequence,
            include_alignment=include_alignment,
        )

        return SearchMatch(
            target_id=target_record.id,
            target_sequence=target_record.sequence,
            score=alignment.score,
            identity=alignment.identity,
            tier=self._classify_tier(alignment.identity),
            cigar=alignment.cigar,
            aligned_query=alignment.aligned_query,
            aligned_target=alignment.aligned_target,
            cdr_similarity=self._compare_cdrs(query_cdrs, target_record.cdrs),
        )

    def _align_batch(
        self,
        query: str,
        candidate_indices: List[int],
        include_alignment: bool,
        query_cdrs: Optional[Dict[str, str]],
    ) -> List[SearchMatch]:
        return [
            self._align_candidate(
                query,
                candidate_index,
                include_alignment,
                query_cdrs,
            )
            for candidate_index in candidate_indices
        ]

    def _resolve_query_cdrs(self, query: str) -> Optional[Dict[str, str]]:
        """
        Resolve query CDRs from indexed records first, extraction second.
        优先从已索引记录解析查询 CDR，失败时再尝试提取。

        Args:
            query (str): Query amino-acid sequence.
                查询氨基酸序列。

        Returns:
            Optional[Dict[str, str]]: CDR dictionary if available.
                若可用则返回 CDR 字典。
        """
        for seq_id in self._index_manager.get_ids_for_sequence(query):
            record = self._index_manager.get_record_by_id(seq_id)
            if record is not None and record.cdrs is not None:
                return record.cdrs
        return extract_cdrs(query)

    def _compare_cdrs(
        self,
        query_cdrs: Optional[Dict[str, str]],
        target_cdrs: Optional[Dict[str, str]],
    ) -> Optional[Dict[str, float]]:
        """
        Compare CDR1/2/3 similarity using simple edit-distance-like ratios.
        使用简单类编辑距离比率比较 CDR1/2/3 相似度。

        Uses Hamming distance when lengths are equal; otherwise counts
        position-wise mismatches plus length delta.
        等长时使用 Hamming 距离；长度不同则使用逐位错配加长度差。

        Args:
            query_cdrs (Optional[Dict]): Query CDR dictionary.
                查询 CDR 字典。
            target_cdrs (Optional[Dict]): Target CDR dictionary.
                目标 CDR 字典。

        Returns:
            Optional[Dict[str, float]]: Similarity per CDR in [0.0, 1.0],
                or None when either side is missing.
                各 CDR 的 [0.0, 1.0] 相似度；若任一侧缺失则返回 None。
        """
        if query_cdrs is None or target_cdrs is None:
            return None

        similarities: Dict[str, float] = {}
        for cdr_name in ("CDR1", "CDR2", "CDR3"):
            query_value = str(
                query_cdrs.get(cdr_name)
                or query_cdrs.get(cdr_name.lower())
                or ""
            )
            target_value = str(
                target_cdrs.get(cdr_name)
                or target_cdrs.get(cdr_name.lower())
                or ""
            )

            if len(query_value) == len(target_value):
                length = len(query_value)
                if length == 0:
                    similarities[cdr_name] = 1.0
                    continue
                distance = sum(1 for q, t in zip(query_value, target_value) if q != t)
                similarities[cdr_name] = max(0.0, 1.0 - (distance / length))
                continue

            min_length = min(len(query_value), len(target_value))
            distance = sum(
                1 for q, t in zip(query_value[:min_length], target_value[:min_length]) if q != t
            )
            distance += abs(len(query_value) - len(target_value))
            denominator = max(len(query_value), len(target_value))
            similarities[cdr_name] = 1.0 if denominator == 0 else max(
                0.0,
                1.0 - (distance / denominator),
            )

        return similarities

    def _classify_tier(self, identity: float) -> str:
        """
        Classify identity into cosmetic result tiers.
        将一致性分数分类为结果分层标签。

        Args:
            identity (float): Alignment identity in [0.0, 1.0].
                对齐一致性（[0.0, 1.0]）。

        Returns:
            str: One of exact/high/moderate/low.
                exact/high/moderate/low 之一。
        """
        if identity >= 0.95:
            return "exact"
        if identity >= 0.80:
            return "high"
        if identity >= 0.50:
            return "moderate"
        return "low"
