"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Diversity Filter
    - docs/cn/README.md: 第1.1节 - 多样性过滤器
    - metanano/config.py: DiversityConfig
    - metanano/utils/mmseqs2_wrapper.py: MMseqs2 integration
    - metanano/utils/similarity.py: K-mer and MinHash utilities

File / 文件:
    - metanano/filters/diversity.py

Overview / 概述:
    Diversity filter implementation for ensuring sequence uniqueness.
    确保序列唯一性的多样性过滤器实现。

    Core operations:
    核心操作：
        1. MMseqs2 clustering (global_cluster_identity >= 0.98)
        2. CDR mutation checking (combined >= 2, CDR3 >= 1)
        3. Historical comparison via k-mer/MinHash similarity

Consumers / 调用方:
    - metanano/filters/__init__.py
    - metanano/validators/diversity_validator.py
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from metanano.config import DiversityConfig
from metanano.utils.cdr_utils import extract_cdrs, count_cdr_mutations
from metanano.utils.mmseqs2_wrapper import MMseqs2Wrapper
from metanano.utils.similarity import compute_kmer_similarity, weighted_minhash


@dataclass
class DiversityResult:
    """
    Result from diversity filter analysis.
    多样性过滤器分析结果。

    Attributes / 属性:
        passed: Whether diversity requirements are met / 是否满足多样性要求
        global_cluster_identity: Maximum identity found in batch / 批次中发现的最大相似度
        cdrs_combined_mutations: Total mutations across CDRs / CDR 总突变数
        cdr3_mutations: Mutations in CDR3 region / CDR3 区域突变数
        jaccard_similarity: Similarity to historical sequences / 与历史序列的相似度
        reason: Failure reason if not passed / 未通过时的失败原因

    Consumers / 调用方:
        - metanano/validators/diversity_validator.py
    """

    passed: bool
    global_cluster_identity: Optional[float] = None
    cdrs_combined_mutations: Optional[int] = None
    cdr3_mutations: Optional[int] = None
    jaccard_similarity: Optional[float] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary. / 转换为字典。"""
        result = {"passed": self.passed}
        if self.global_cluster_identity is not None:
            result["global_cluster_identity"] = self.global_cluster_identity
        if self.cdrs_combined_mutations is not None:
            result["cdrs_combined_mutations"] = self.cdrs_combined_mutations
        if self.cdr3_mutations is not None:
            result["cdr3_mutations"] = self.cdr3_mutations
        if self.jaccard_similarity is not None:
            result["jaccard_similarity"] = self.jaccard_similarity
        if self.reason:
            result["reason"] = self.reason
        return result


class DiversityFilter:
    """
    Filter for ensuring nanobody sequence diversity.
    确保纳米抗体序列多样性的过滤器。

    This filter checks:
    该过滤器检查：
        1. Batch diversity via MMseqs2 clustering
        2. CDR mutation requirements
        3. Historical uniqueness via k-mer/MinHash

    Example / 示例:
        >>> config = DiversityConfig()
        >>> filter = DiversityFilter(config)
        >>> result = filter.check_batch_diversity(sequences)

    Consumers / 调用方:
        - metanano/filters/__init__.py
        - metanano/validators/diversity_validator.py
    """

    def __init__(self, config: DiversityConfig) -> None:
        """
        Initialize the diversity filter.
        初始化多样性过滤器。

        Args / 参数:
            config (DiversityConfig): Filter configuration.
                过滤器配置。

        References / 参考:
            - metanano/config.py: DiversityConfig
        """
        self.config = config
        self._mmseqs2 = MMseqs2Wrapper(config.mmseqs2)

    def check_batch_diversity(
        self,
        sequence: str,
        batch_sequences: List[str],
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if sequence is diverse within the submission batch.
        检查序列在提交批次内是否具有多样性。

        Uses MMseqs2 clustering to identify near-duplicates.
        使用 MMseqs2 聚类识别近似重复序列。

        Args / 参数:
            sequence (str): The sequence to check.
                要检查的序列。
            batch_sequences (List[str]): Other sequences in the batch.
                批次中的其他序列。

        Returns / 返回:
            Tuple[bool, Optional[float]]: (passed, max_identity_found)
                (是否通过, 发现的最大相似度)

        References / 参考:
            - metanano/utils/mmseqs2_wrapper.py: MMseqs2Wrapper.cluster

        Consumers / 调用方:
            - metanano/validators/diversity_validator.py
        """
        if not batch_sequences:
            return True, None

        all_sequences = [sequence] + batch_sequences
        clusters = self._mmseqs2.cluster(all_sequences)

        # Find if sequence is clustered with any other
        # 查找序列是否与其他序列聚类
        threshold = self.config.mmseqs2.global_cluster_identity
        max_identity = 0.0

        for cluster in clusters:
            if sequence in cluster and len(cluster) > 1:
                # Sequence is in a cluster with others - check identity
                # 序列与其他序列在同一聚类中 - 检查相似度
                for other_seq in cluster:
                    if other_seq != sequence:
                        identity = self._mmseqs2.compute_identity(sequence, other_seq)
                        max_identity = max(max_identity, identity)

        passed = max_identity < threshold
        return passed, max_identity if max_identity > 0 else None

    def check_cdr_mutations(
        self,
        sequence: str,
        reference_sequence: Optional[str] = None,
    ) -> Tuple[bool, int, int]:
        """
        Check CDR mutation requirements.
        检查 CDR 突变要求。

        Args / 参数:
            sequence (str): The sequence to check.
                要检查的序列。
            reference_sequence (Optional[str]): Reference for mutation counting.
                用于突变计数的参考序列。

        Returns / 返回:
            Tuple[bool, int, int]: (passed, cdrs_combined, cdr3_mutations)
                (是否通过, CDR总突变数, CDR3突变数)

        References / 参考:
            - metanano/utils/cdr_utils.py: extract_cdrs, count_cdr_mutations

        Consumers / 调用方:
            - metanano/validators/diversity_validator.py
        """
        cdrs = extract_cdrs(sequence)
        if not cdrs:
            return False, 0, 0

        combined, cdr3 = count_cdr_mutations(sequence, reference_sequence)

        passed = (
            combined >= self.config.mutations.cdrs_combined_min
            and cdr3 >= self.config.mutations.cdr3_min
        )
        return passed, combined, cdr3

    def check_historical_similarity(
        self,
        sequence: str,
        historical_sequences: List[str],
    ) -> Tuple[bool, Optional[float]]:
        """
        Check similarity against historical submissions.
        检查与历史提交的相似度。

        Uses the configured strategy (Plan A or Plan B).
        使用配置的策略（方案 A 或方案 B）。

        Args / 参数:
            sequence (str): The sequence to check.
                要检查的序列。
            historical_sequences (List[str]): Historical submissions.
                历史提交序列。

        Returns / 返回:
            Tuple[bool, Optional[float]]: (passed, max_similarity)
                (是否通过, 最大相似度)

        References / 参考:
            - metanano/utils/similarity.py: compute_kmer_similarity, weighted_minhash

        Consumers / 调用方:
            - metanano/validators/diversity_validator.py
        """
        if not historical_sequences:
            return True, None

        strategy = self.config.comparison.strategy
        k = self.config.kmer_index.k

        if strategy == "plan_b":
            # Compare only against top N
            # 仅与前 N 名比较
            top_n = self.config.comparison.plan_b.current_top_n
            compare_sequences = historical_sequences[:top_n]
        else:
            # Plan A: compare against all
            # 方案 A：与所有序列比较
            compare_sequences = historical_sequences

        max_similarity = 0.0
        for hist_seq in compare_sequences:
            similarity = compute_kmer_similarity(sequence, hist_seq, k=k)
            max_similarity = max(max_similarity, similarity)

        threshold = self.config.comparison.plan_a.jaccard_threshold
        passed = max_similarity < threshold

        return passed, max_similarity if max_similarity > 0 else None





