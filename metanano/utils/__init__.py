"""
References / 参考:
    - docs/en/README.md: Section 2 - File Structure
    - docs/cn/README.md: 第2节 - 文件结构

File / 文件:
    - metanano/utils/__init__.py

Overview / 概述:
    Utility modules for sequence analysis and external tool integration.
    用于序列分析和外部工具集成的工具模块。

Consumers / 调用方:
    - metanano/filters/*.py
"""

from metanano.utils.cdr_utils import extract_cdrs, count_cdr_mutations
from metanano.utils.kmer import generate_kmers, build_kmer_index
from metanano.utils.similarity import compute_kmer_similarity, weighted_minhash
from metanano.utils.mmseqs2_wrapper import MMseqs2Wrapper
from metanano.utils.tnp_wrapper import TNPWrapper, TNPResult

__all__ = [
    "extract_cdrs",
    "count_cdr_mutations",
    "generate_kmers",
    "build_kmer_index",
    "compute_kmer_similarity",
    "weighted_minhash",
    "MMseqs2Wrapper",
    "TNPWrapper",
    "TNPResult",
]


