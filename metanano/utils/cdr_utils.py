"""
References / 参考:
    - docs/en/README.md: Section 1.1 - Diversity Filter (CDR mutations)
    - abnumber library: CDR extraction

File / 文件:
    - metanano/utils/cdr_utils.py

Overview / 概述:
    Utilities for CDR (Complementarity Determining Region) extraction and analysis.
    用于 CDR（互补决定区）提取和分析的工具。

Consumers / 调用方:
    - metanano/utils/__init__.py
    - metanano/filters/diversity.py
"""

from typing import Dict, Optional, Tuple


def extract_cdrs(sequence: str) -> Optional[Dict[str, str]]:
    """
    Extract CDR regions from a nanobody sequence using IMGT numbering.
    使用 IMGT 编号从纳米抗体序列中提取 CDR 区域。

    Args / 参数:
        sequence (str): The nanobody amino acid sequence.
            纳米抗体氨基酸序列。

    Returns / 返回:
        Optional[Dict[str, str]]: Dictionary with CDR1, CDR2, CDR3 sequences,
            or None if extraction failed.
            包含 CDR1、CDR2、CDR3 序列的字典，如果提取失败则返回 None。

    Example / 示例:
        >>> cdrs = extract_cdrs("EVQLVESGGGLVQPGG...")
        >>> print(cdrs["cdr3"])
        "ASGFTFS"

    References / 参考:
        - abnumber library: Chain.cdr1_seq, cdr2_seq, cdr3_seq

    Consumers / 调用方:
        - metanano/filters/diversity.py: DiversityFilter.check_cdr_mutations
    """
    try:
        from abnumber import Chain

        chain = Chain(sequence, scheme="imgt")
        return {
            "cdr1": str(chain.cdr1_seq) if chain.cdr1_seq else "",
            "cdr2": str(chain.cdr2_seq) if chain.cdr2_seq else "",
            "cdr3": str(chain.cdr3_seq) if chain.cdr3_seq else "",
        }
    except Exception:
        return None


def count_cdr_mutations(
    sequence: str,
    reference: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Count mutations in CDR regions.
    计算 CDR 区域的突变数。

    If no reference is provided, counts unique residues as a proxy for diversity.
    如果未提供参考序列，则计算唯一残基作为多样性的替代指标。

    Args / 参数:
        sequence (str): The nanobody sequence to analyze.
            要分析的纳米抗体序列。
        reference (Optional[str]): Reference sequence for comparison.
            用于比较的参考序列。

    Returns / 返回:
        Tuple[int, int]: (total_cdr_mutations, cdr3_mutations)
            (CDR 总突变数, CDR3 突变数)

    Example / 示例:
        >>> combined, cdr3 = count_cdr_mutations(sequence, reference)
        >>> print(f"Combined: {combined}, CDR3: {cdr3}")

    References / 参考:
        - abnumber library

    Consumers / 调用方:
        - metanano/filters/diversity.py: DiversityFilter.check_cdr_mutations
    """
    seq_cdrs = extract_cdrs(sequence)
    if not seq_cdrs:
        return 0, 0

    if reference:
        ref_cdrs = extract_cdrs(reference)
        if not ref_cdrs:
            return 0, 0

        # Count differences
        # 计算差异
        total_mutations = 0
        cdr3_mutations = 0

        for cdr_name in ["cdr1", "cdr2", "cdr3"]:
            seq_cdr = seq_cdrs.get(cdr_name, "")
            ref_cdr = ref_cdrs.get(cdr_name, "")

            # Align and count differences (simple comparison)
            # 对齐并计算差异（简单比较）
            min_len = min(len(seq_cdr), len(ref_cdr))
            mutations = sum(
                1 for i in range(min_len) if seq_cdr[i] != ref_cdr[i]
            )
            mutations += abs(len(seq_cdr) - len(ref_cdr))

            total_mutations += mutations
            if cdr_name == "cdr3":
                cdr3_mutations = mutations

        return total_mutations, cdr3_mutations
    else:
        # Without reference, use length-based heuristic
        # 没有参考序列时，使用基于长度的启发式方法
        cdr3 = seq_cdrs.get("cdr3", "")
        cdr3_len = len(cdr3)

        # Estimate mutations based on CDR lengths (heuristic)
        # 根据 CDR 长度估算突变数（启发式）
        total_len = sum(len(seq_cdrs.get(cdr, "")) for cdr in ["cdr1", "cdr2", "cdr3"])

        # Simple heuristic: longer CDRs = more diversity potential
        # 简单启发式：更长的 CDR = 更大的多样性潜力
        return total_len // 3, max(1, cdr3_len // 4)





