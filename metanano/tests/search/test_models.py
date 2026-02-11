"""
References / 参考:
    - docs/en/README.md: Section 6 - Testing
    - docs/cn/README.md: 第6节 - 测试

File / 文件:
    - metanano/tests/search/test_models.py

Overview / 概述:
    Tests for enriched Sequence model and SearchConfig.
    增强的 Sequence 模型和 SearchConfig 的测试。

Consumers / 调用方:
    - pytest
"""

import pytest
from metanano.models.sequence import Sequence
from metanano.config import Config


def test_sequence_model_backwards_compatible():
    """
    Test that Sequence model remains backwards compatible.
    测试 Sequence 模型保持向后兼容。
    
    Ensures existing code using Sequence(sequence="...") still works.
    确保使用 Sequence(sequence="...") 的现有代码仍然有效。
    """
    # Arrange / 准备
    seq_str = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSSAAAAA"
    
    # Act / 执行
    seq = Sequence(sequence=seq_str)
    
    # Assert / 断言
    assert seq.sequence == seq_str
    assert seq.id is None
    assert seq.cdrs is None
    assert seq.kmers is None


def test_sequence_with_enriched_fields():
    """
    Test Sequence model with all enriched fields populated.
    测试填充所有增强字段的 Sequence 模型。
    
    Verifies new optional fields can be set and retrieved.
    验证可以设置和检索新的可选字段。
    """
    # Arrange / 准备
    seq_str = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSSAAAAA"
    seq_id = "seq_001"
    cdrs = {
        "CDR1": "GFTFSYFY",
        "CDR2": "DUMMY",
        "CDR3": "DUMMY"
    }
    kmers = {"EVQLV", "VQLVE", "QLVES"}
    
    # Act / 执行
    seq = Sequence(
        sequence=seq_str,
        id=seq_id,
        cdrs=cdrs,
        kmers=kmers
    )
    
    # Assert / 断言
    assert seq.sequence == seq_str
    assert seq.id == seq_id
    assert seq.cdrs == cdrs
    assert seq.kmers == kmers


def test_sequence_optional_fields_default_none():
    """
    Test that optional fields default to None.
    测试可选字段默认为 None。
    
    Ensures new fields don't break existing instantiation patterns.
    确保新字段不会破坏现有的实例化模式。
    """
    # Arrange / 准备
    seq_str = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSYFYYWGQGTLVTVSSAAAAA"
    
    # Act / 执行
    seq = Sequence(sequence=seq_str)
    
    # Assert / 断言
    assert hasattr(seq, "id")
    assert hasattr(seq, "cdrs")
    assert hasattr(seq, "kmers")
    assert seq.id is None
    assert seq.cdrs is None
    assert seq.kmers is None


def test_search_config_defaults():
    """
    Test SearchConfig has correct default values.
    测试 SearchConfig 具有正确的默认值。
    
    Verifies coarse filter and fine alignment defaults.
    验证粗过滤和精细对齐的默认值。
    """
    # Arrange / 准备
    from metanano.config import SearchConfig
    
    # Act / 执行
    config = SearchConfig()
    
    # Assert / 断言
    assert config.coarse_filter.min_shared_kmers == 3
    assert config.coarse_filter.jaccard_threshold == 0.3
    assert config.fine_alignment.gap_open == 10


def test_root_config_includes_search():
    """
    Test root Config includes SearchConfig.
    测试根 Config 包含 SearchConfig。
    
    Ensures Config().search returns a SearchConfig instance.
    确保 Config().search 返回 SearchConfig 实例。
    """
    # Arrange / 准备
    from metanano.config import SearchConfig
    
    # Act / 执行
    config = Config()
    
    # Assert / 断言
    assert hasattr(config, "search")
    assert isinstance(config.search, SearchConfig)
    assert config.search.coarse_filter.min_shared_kmers == 3
