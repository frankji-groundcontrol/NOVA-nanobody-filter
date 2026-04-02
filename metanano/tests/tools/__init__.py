"""
References / 参考:
    - docs/en/TODO.md: Section 0 - External Tool Integration
    - docs/cn/TODO.md: 第0节 - 外部工具集成

File / 文件:
    - metanano/tests/tools/__init__.py

Overview / 概述:
    Test suite for external tool integrations.
    外部工具集成的测试套件。

    This module contains pytest tests for all external tools used in MetaNano:
    该模块包含 MetaNano 使用的所有外部工具的 pytest 测试：
        - TNP (Therapeutic Nanobody Profiler)
        - MMseqs2 (Sequence Clustering)
        - abnumber (IMGT Numbering)
        - IgBLAST-based nativeness scoring
        - promb (OASis Humanness)
        - datasketch (MinHash Similarity)

Consumers / 调用方:
    - pytest (test runner)
"""
