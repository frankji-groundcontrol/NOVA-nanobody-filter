"""
References / 参考:
    - docs/en/README.md: Section 1.1.2 - K-mer Index
    - docs/cn/README.md: 第1.1.2节 - K-mer 索引
    - pytest documentation: fixtures

File / 文件:
    - metanano/tests/search/conftest.py

Overview / 概述:
    Pytest fixtures for sequence search tests.
    序列搜索测试的 Pytest fixtures。

    Provides sample VHH sequences, databases, and k-mer indices for testing.
    提供用于测试的示例 VHH 序列、数据库和 k-mer 索引。

Consumers / 调用方:
    - metanano/tests/search/test_*.py
"""

import pytest
from typing import Dict, List

from metanano.utils.kmer import build_kmer_index


# Sample VHH sequences for search testing
# 用于搜索测试的示例 VHH 序列
SEARCH_FIXTURES: Dict[str, str] = {
    # Query VHH sequence (base for similarity comparisons)
    # 查询 VHH 序列（相似性比较的基准）
    "query_vhh": (
        "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
        "RVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
    ),
    
    # Similar VHH (different framework, similar CDRs)
    # 相似的 VHH（不同框架，相似的 CDR）
    "similar_vhh": (
        "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKG"
        "RFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDLGWSFDYWGQGTLVTVSS"
    ),
    
    # Dissimilar VHH (llama-derived, very different CDRs)
    # 不相似的 VHH（羊驼来源，非常不同的 CDR）
    "dissimilar_vhh": (
        "DVQLVESGGGLVQAGGSLRLSCAASGRTFSSYAMGWFRQAPGKEREFVAAISWSGGSTYYADSVKG"
        "RFTISRDNAKNTVYLQMNSLKPEDTAVYYCAAWDDSLNGWGQGTQVTVSS"
    ),
    
    # Near-identical VHH (query with 2 mutations at C-terminus)
    # 近乎相同的 VHH（查询序列在 C 端有 2 个突变）
    "near_identical_vhh": (
        "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKN"
        "RVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVAA"
    ),
}


@pytest.fixture
def query_sequence() -> str:
    """
    Provide the query VHH sequence for search testing.
    提供用于搜索测试的查询 VHH 序列。
    
    Returns / 返回:
        str: Query nanobody sequence.
            查询纳米抗体序列。
    """
    return SEARCH_FIXTURES["query_vhh"]


@pytest.fixture
def similar_sequence() -> str:
    """
    Provide a similar VHH sequence for positive search results.
    提供用于正向搜索结果的相似 VHH 序列。
    
    Returns / 返回:
        str: Similar nanobody sequence.
            相似的纳米抗体序列。
    """
    return SEARCH_FIXTURES["similar_vhh"]


@pytest.fixture
def dissimilar_sequence() -> str:
    """
    Provide a dissimilar VHH sequence for negative search results.
    提供用于负向搜索结果的不相似 VHH 序列。
    
    Returns / 返回:
        str: Dissimilar nanobody sequence.
            不相似的纳米抗体序列。
    """
    return SEARCH_FIXTURES["dissimilar_vhh"]


@pytest.fixture
def near_identical_sequence() -> str:
    """
    Provide a near-identical VHH sequence for high-similarity testing.
    提供用于高相似性测试的近乎相同的 VHH 序列。
    
    Returns / 返回:
        str: Near-identical nanobody sequence (2 mutations from query).
            近乎相同的纳米抗体序列（与查询序列有 2 个突变）。
    """
    return SEARCH_FIXTURES["near_identical_vhh"]


@pytest.fixture
def sequence_database() -> List[str]:
    """
    Provide a database of VHH sequences for search testing.
    提供用于搜索测试的 VHH 序列数据库。
    
    Returns / 返回:
        List[str]: List of nanobody sequences (10-15 sequences).
            纳米抗体序列列表（10-15 个序列）。
    """
    # Start with the 4 core fixtures
    # 从 4 个核心 fixture 开始
    sequences = [
        SEARCH_FIXTURES["query_vhh"],
        SEARCH_FIXTURES["similar_vhh"],
        SEARCH_FIXTURES["dissimilar_vhh"],
        SEARCH_FIXTURES["near_identical_vhh"],
    ]
    
    # Add variants by mutating query_vhh at different positions
    # 通过在不同位置突变 query_vhh 来添加变体
    base = SEARCH_FIXTURES["query_vhh"]
    
    # Variant 1: N-terminal mutation (position 10-12)
    # 变体 1：N 端突变（位置 10-12）
    sequences.append(base[:10] + "AAA" + base[13:])
    
    # Variant 2: CDR1 region mutation (position 30-33)
    # 变体 2：CDR1 区域突变（位置 30-33）
    sequences.append(base[:30] + "GGGG" + base[34:])
    
    # Variant 3: CDR2 region mutation (position 50-53)
    # 变体 3：CDR2 区域突变（位置 50-53）
    sequences.append(base[:50] + "SSSS" + base[54:])
    
    # Variant 4: CDR3 region mutation (position 95-98)
    # 变体 4：CDR3 区域突变（位置 95-98）
    sequences.append(base[:95] + "YYYY" + base[99:])
    
    # Variant 5: Framework mutation (position 70-73)
    # 变体 5：框架区突变（位置 70-73）
    sequences.append(base[:70] + "TTTT" + base[74:])
    
    # Add variants of similar_vhh
    # 添加 similar_vhh 的变体
    base2 = SEARCH_FIXTURES["similar_vhh"]
    
    # Variant 6: similar_vhh with C-terminal mutation
    # 变体 6：C 端突变的 similar_vhh
    sequences.append(base2[:-4] + "GGGG")
    
    # Variant 7: similar_vhh with N-terminal mutation
    # 变体 7：N 端突变的 similar_vhh
    sequences.append("AAAA" + base2[4:])
    
    # Add variants of dissimilar_vhh
    # 添加 dissimilar_vhh 的变体
    base3 = SEARCH_FIXTURES["dissimilar_vhh"]
    
    # Variant 8: dissimilar_vhh with middle mutation
    # 变体 8：中间突变的 dissimilar_vhh
    sequences.append(base3[:60] + "PPPP" + base3[64:])
    
    # Variant 9: dissimilar_vhh with CDR3 mutation
    # 变体 9：CDR3 突变的 dissimilar_vhh
    sequences.append(base3[:90] + "WWWW" + base3[94:])
    
    # Variant 10: Hybrid (first half query, second half similar)
    # 变体 10：混合体（前半部分查询，后半部分相似）
    mid = len(base) // 2
    sequences.append(base[:mid] + base2[mid:])
    
    return sequences


@pytest.fixture
def known_cdrs() -> Dict[str, Dict[str, str]]:
    """
    Provide known CDR regions for test sequences.
    提供测试序列的已知 CDR 区域。
    
    Returns / 返回:
        Dict[str, Dict[str, str]]: Mapping from sequence name to CDR dict.
            从序列名称到 CDR 字典的映射。
            
    Example / 示例:
        {
            "query_vhh": {
                "CDR1": "GYTFTNYYMY",
                "CDR2": "INPSNGGTNFNEKFKN",
                "CDR3": "RDYRFDMGFDY"
            }
        }
    """
    # IMGT CDR definitions for VHH sequences
    # VHH 序列的 IMGT CDR 定义
    return {
        "query_vhh": {
            "CDR1": "GYTFTNYYMY",
            "CDR2": "INPSNGGTNFNEKFKN",
            "CDR3": "RDYRFDMGFDY",
        },
        "similar_vhh": {
            "CDR1": "GFTFSSYAMS",
            "CDR2": "ISGSGGSTYYADSVKG",
            "CDR3": "DLGWSFDY",
        },
        "dissimilar_vhh": {
            "CDR1": "GRTFSSYAMG",
            "CDR2": "ISWSGGSTYYADSVKG",
            "CDR3": "WDDSLNG",
        },
        "near_identical_vhh": {
            "CDR1": "GYTFTNYYMY",
            "CDR2": "INPSNGGTNFNEKFKN",
            "CDR3": "RDYRFDMGFDY",
        },
    }


@pytest.fixture
def sample_kmer_index(sequence_database: List[str]) -> Dict[str, set]:
    """
    Provide a k-mer index built from the sequence database.
    提供从序列数据库构建的 k-mer 索引。
    
    Args / 参数:
        sequence_database (List[str]): Database of sequences to index.
            要索引的序列数据库。
    
    Returns / 返回:
        Dict[str, set]: K-mer index mapping k-mers to sequence indices.
            将 k-mer 映射到序列索引的 k-mer 索引。
    """
    return build_kmer_index(sequence_database, k=5)
