"""
File / 文件:
    - metanano/search/__init__.py

Overview / 概述:
    Sequence search package — fast similarity search using k-mer indices.
    序列搜索包 — 使用 k-mer 索引的快速相似性搜索。

Consumers / 调用方:
    - metanano/pipeline.py (future)
"""

from metanano.search.index_manager import IndexManager, SequenceRecord
from metanano.search.search_engine import SearchEngine, SearchMatch, SearchResult

__all__ = [
    "IndexManager",
    "SequenceRecord",
    "SearchEngine",
    "SearchMatch",
    "SearchResult",
]
