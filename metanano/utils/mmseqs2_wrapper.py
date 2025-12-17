"""
References / 参考:
    - docs/en/README.md: Section 1.1.1 - MMseqs2 clustering
    - docs/cn/README.md: 第1.1.1节 - MMseqs2 聚类
    - MMseqs2 GitHub: https://github.com/soedinglab/MMseqs2

File / 文件:
    - metanano/utils/mmseqs2_wrapper.py

Overview / 概述:
    Wrapper for MMseqs2 sequence clustering and comparison.
    MMseqs2 序列聚类和比较的封装器。

Consumers / 调用方:
    - metanano/utils/__init__.py
    - metanano/filters/diversity.py
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set

from metanano.config import MMseqs2Config


class MMseqs2Wrapper:
    """
    Wrapper for MMseqs2 CLI commands.
    MMseqs2 命令行工具的封装器。

    Provides Python interface for sequence clustering and identity computation.
    提供用于序列聚类和相似度计算的 Python 接口。

    Example / 示例:
        >>> config = MMseqs2Config()
        >>> mmseqs = MMseqs2Wrapper(config)
        >>> clusters = mmseqs.cluster(sequences)

    Consumers / 调用方:
        - metanano/filters/diversity.py: DiversityFilter
    """

    def __init__(self, config: MMseqs2Config) -> None:
        """
        Initialize the MMseqs2 wrapper.
        初始化 MMseqs2 封装器。

        Args / 参数:
            config (MMseqs2Config): Configuration for MMseqs2.
                MMseqs2 配置。

        References / 参考:
            - metanano/config.py: MMseqs2Config
        """
        self.config = config
        self._temp_dir = config.temp_dir or Path(tempfile.gettempdir())
        self._threads = config.threads
        self._identity_threshold = config.global_cluster_identity

    def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """
        Run an MMseqs2 command.
        运行 MMseqs2 命令。

        Args / 参数:
            cmd (List[str]): Command and arguments.
                命令和参数。

        Returns / 返回:
            subprocess.CompletedProcess: Command result.
                命令结果。

        Raises / 异常:
            RuntimeError: If command fails.
                如果命令失败。
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"MMseqs2 command failed: {e.stderr}. / "
                f"MMseqs2 命令失败：{e.stderr}。"
            )

    def cluster(
        self,
        sequences: List[str],
        identity: Optional[float] = None,
    ) -> List[Set[str]]:
        """
        Cluster sequences using MMseqs2.
        使用 MMseqs2 对序列进行聚类。

        Args / 参数:
            sequences (List[str]): Sequences to cluster.
                要聚类的序列。
            identity (Optional[float]): Identity threshold (default: from config).
                相似度阈值（默认：来自配置）。

        Returns / 返回:
            List[Set[str]]: List of sequence clusters.
                序列聚类列表。

        Example / 示例:
            >>> clusters = mmseqs.cluster(["EVQLV...", "QVQLV...", "EVQLV..."])
            >>> print(len(clusters))
            2

        Consumers / 调用方:
            - metanano/filters/diversity.py: DiversityFilter.check_batch_diversity
        """
        if not sequences:
            return []

        identity = identity or self._identity_threshold

        with tempfile.TemporaryDirectory(dir=self._temp_dir) as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Write sequences to FASTA
            # 将序列写入 FASTA
            fasta_path = tmpdir_path / "sequences.fasta"
            with open(fasta_path, "w") as f:
                for i, seq in enumerate(sequences):
                    f.write(f">seq_{i}\n{seq}\n")

            # Create database
            # 创建数据库
            db_path = tmpdir_path / "seqdb"
            self._run_command([
                "mmseqs", "createdb",
                str(fasta_path),
                str(db_path),
            ])

            # Cluster
            # 聚类
            cluster_path = tmpdir_path / "clusters"
            tmp_path = tmpdir_path / "tmp"
            tmp_path.mkdir(exist_ok=True)

            self._run_command([
                "mmseqs", "cluster",
                str(db_path),
                str(cluster_path),
                str(tmp_path),
                "--min-seq-id", str(identity),
                "--threads", str(self._threads),
            ])

            # Create TSV output
            # 创建 TSV 输出
            tsv_path = tmpdir_path / "clusters.tsv"
            self._run_command([
                "mmseqs", "createtsv",
                str(db_path),
                str(db_path),
                str(cluster_path),
                str(tsv_path),
            ])

            # Parse clusters
            # 解析聚类结果
            return self._parse_clusters(tsv_path, sequences)

    def _parse_clusters(
        self,
        tsv_path: Path,
        sequences: List[str],
    ) -> List[Set[str]]:
        """
        Parse MMseqs2 cluster TSV output.
        解析 MMseqs2 聚类 TSV 输出。

        Args / 参数:
            tsv_path (Path): Path to TSV file.
                TSV 文件路径。
            sequences (List[str]): Original sequences.
                原始序列。

        Returns / 返回:
            List[Set[str]]: Parsed clusters.
                解析后的聚类。
        """
        # Map sequence names to actual sequences
        # 将序列名称映射到实际序列
        name_to_seq = {f"seq_{i}": seq for i, seq in enumerate(sequences)}

        # Parse TSV (format: representative\tmember)
        # 解析 TSV（格式：代表序列\t成员序列）
        clusters_dict: Dict[str, Set[str]] = {}

        with open(tsv_path, "r") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    rep, member = parts[0], parts[1]
                    if rep not in clusters_dict:
                        clusters_dict[rep] = set()
                    clusters_dict[rep].add(name_to_seq.get(member, member))

        return [cluster for cluster in clusters_dict.values()]

    def compute_identity(self, seq1: str, seq2: str) -> float:
        """
        Compute pairwise sequence identity.
        计算成对序列相似度。

        Args / 参数:
            seq1 (str): First sequence.
                第一个序列。
            seq2 (str): Second sequence.
                第二个序列。

        Returns / 返回:
            float: Sequence identity (0-1).
                序列相似度（0-1）。

        Consumers / 调用方:
            - metanano/filters/diversity.py: DiversityFilter.check_batch_diversity
        """
        # Simple identity calculation (can be replaced with MMseqs2 align)
        # 简单的相似度计算（可替换为 MMseqs2 align）
        if not seq1 or not seq2:
            return 0.0

        min_len = min(len(seq1), len(seq2))
        max_len = max(len(seq1), len(seq2))

        if max_len == 0:
            return 0.0

        matches = sum(1 for i in range(min_len) if seq1[i] == seq2[i])
        return matches / max_len





