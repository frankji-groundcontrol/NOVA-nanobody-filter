"""
References / 参考:
    - docs/en/README.md: Section 1.1.3 - Fine Alignment
    - docs/cn/README.md: 第1.1.3节 - 精细对齐

File / 文件:
    - metanano/utils/alignment.py

Overview / 概述:
    Pairwise sequence alignment engine with parasail backend and BioPython fallback.
    基于 parasail 后端的成对序列对齐引擎，支持 BioPython 回退。

    Supports Smith-Waterman (local) and Needleman-Wunsch (global) alignment
    using BLOSUM62 substitution matrix.
    支持使用 BLOSUM62 替换矩阵的 Smith-Waterman（局部）和 Needleman-Wunsch（全局）对齐。

Consumers / 调用方:
    - metanano/search/fine_alignment.py (future)
"""

from dataclasses import dataclass
from typing import Optional

from metanano.config import FineAlignmentConfig


@dataclass
class AlignmentResult:
    """
    Result from a pairwise sequence alignment.
    成对序列对齐的结果。

    Attributes / 属性:
        score: Alignment score (raw). / 对齐分数（原始值）。
        identity: Fraction of matching positions (0.0-1.0). / 匹配位置的比例（0.0-1.0）。
        cigar: CIGAR string encoding alignment operations. / 编码对齐操作的 CIGAR 字符串。
        aligned_query: Aligned query string with gaps. / 包含间隙的对齐查询字符串。
        aligned_target: Aligned target string with gaps. / 包含间隙的对齐目标字符串。
        length: Alignment length (including gaps). / 对齐长度（包含间隙）。
        matches: Number of exact matches. / 精确匹配的数量。

    Consumers / 调用方:
        - metanano/search/fine_alignment.py (future)
    """

    score: int
    identity: float
    cigar: Optional[str]
    aligned_query: Optional[str]
    aligned_target: Optional[str]
    length: int
    matches: int


class AlignmentEngine:
    """
    Pairwise alignment engine using parasail with BioPython fallback.
    使用 parasail 的成对对齐引擎，支持 BioPython 回退。

    Follows the try/except ImportError pattern from similarity.py for
    graceful degradation when parasail is unavailable.
    遵循 similarity.py 中的 try/except ImportError 模式，
    在 parasail 不可用时优雅降级。

    Args:
        config: Fine alignment configuration with gap penalties.
            包含间隙惩罚参数的精细对齐配置。

    Consumers / 调用方:
        - metanano/search/fine_alignment.py (future)
    """

    def __init__(self, config: FineAlignmentConfig) -> None:
        """
        Initialize alignment engine, detecting parasail availability.
        初始化对齐引擎，检测 parasail 可用性。

        Args:
            config (FineAlignmentConfig): Fine-alignment configuration.
                精细对齐配置。
        """
        self._config = config
        self._gap_open = config.gap_open
        self._gap_extend = 1  # Default gap extension penalty / 默认间隙延伸惩罚

        try:
            import parasail as _parasail

            self._parasail = _parasail
            self._use_parasail = True
        except ImportError:
            self._parasail = None
            self._use_parasail = False

    def align(
        self,
        seq1: str,
        seq2: str,
        method: str = "local",
        include_alignment: bool = True,
    ) -> AlignmentResult:
        """
        Align two sequences using Smith-Waterman or Needleman-Wunsch.
        使用 Smith-Waterman 或 Needleman-Wunsch 对齐两个序列。

        Args:
            seq1: Query sequence. / 查询序列。
            seq2: Target sequence. / 目标序列。
            method: "local" (Smith-Waterman) or "global" (Needleman-Wunsch).
                "local"（Smith-Waterman）或 "global"（Needleman-Wunsch）。
            include_alignment: Whether to include aligned sequences in result.
                是否在结果中包含对齐序列。

        Returns:
            AlignmentResult: Alignment result with score, identity, and CIGAR.
                包含分数、相似度和 CIGAR 的对齐结果。
        """
        if self._use_parasail:
            return self._align_parasail(seq1, seq2, method, include_alignment)
        return self._align_biopython(seq1, seq2, method, include_alignment)

    def _align_parasail(
        self,
        seq1: str,
        seq2: str,
        method: str,
        include_alignment: bool,
    ) -> AlignmentResult:
        """
        Perform alignment using parasail library.
        使用 parasail 库执行对齐。

        Args:
            seq1: Query sequence. / 查询序列。
            seq2: Target sequence. / 目标序列。
            method: "local" or "global". / "local" 或 "global"。
            include_alignment: Include aligned sequences. / 包含对齐序列。

        Returns:
            AlignmentResult: Parasail alignment result. / parasail 对齐结果。

        Raises:
            ValueError: If `method` is unsupported by the caller contract.
                当调用方传入不支持的 `method` 时抛出。
        """
        if method not in ("local", "global"):
            raise ValueError(
                f"Unsupported method: {method}. Use 'local' or 'global'."
            )
        parasail = self._parasail
        if parasail is None:
            raise RuntimeError("parasail backend is unavailable")

        matrix = getattr(parasail, "blosum62")

        if method == "global":
            result = getattr(parasail, "nw_trace_striped_16")(
                seq1, seq2, self._gap_open, self._gap_extend, matrix
            )
        else:
            result = getattr(parasail, "sw_trace_striped_16")(
                seq1, seq2, self._gap_open, self._gap_extend, matrix
            )

        # Extract CIGAR string / 提取 CIGAR 字符串
        raw_cigar = getattr(result.cigar, "decode", result.cigar)
        cigar_str = raw_cigar.decode("utf-8") if isinstance(raw_cigar, bytes) else str(raw_cigar)

        # Extract aligned sequences from traceback / 从回溯中提取对齐序列
        aligned_query: Optional[str] = None
        aligned_target: Optional[str] = None
        if include_alignment:
            aligned_query = result.traceback.query
            aligned_target = result.traceback.ref

        # Calculate matches and identity / 计算匹配数和相似度
        tb_query = result.traceback.query
        tb_ref = result.traceback.ref
        alignment_length = len(tb_ref)
        matches = sum(
            1 for a, b in zip(tb_query, tb_ref) if a == b and a != "-"
        )
        identity = matches / alignment_length if alignment_length > 0 else 0.0

        return AlignmentResult(
            score=result.score,
            identity=identity,
            cigar=cigar_str,
            aligned_query=aligned_query,
            aligned_target=aligned_target,
            length=alignment_length,
            matches=matches,
        )

    def _align_biopython(
        self,
        seq1: str,
        seq2: str,
        method: str,
        include_alignment: bool,
    ) -> AlignmentResult:
        """
        Fallback alignment using BioPython PairwiseAligner.
        使用 BioPython PairwiseAligner 的回退对齐。

        Args:
            seq1: Query sequence. / 查询序列。
            seq2: Target sequence. / 目标序列。
            method: "local" or "global". / "local" 或 "global"。
            include_alignment: Include aligned sequences. / 包含对齐序列。

        Returns:
            AlignmentResult: BioPython alignment result. / BioPython 对齐结果。

        Raises:
            ValueError: If `method` is unsupported by the caller contract.
                当调用方传入不支持的 `method` 时抛出。
        """
        if method not in ("local", "global"):
            raise ValueError(
                f"Unsupported method: {method}. Use 'local' or 'global'."
            )
        from Bio.Align import PairwiseAligner, substitution_matrices

        aligner = PairwiseAligner()
        setattr(aligner, "mode", method)
        setattr(aligner, "substitution_matrix", substitution_matrices.load("BLOSUM62"))
        setattr(aligner, "open_gap_score", -self._gap_open)
        setattr(aligner, "extend_gap_score", -self._gap_extend)

        alignments = aligner.align(seq1, seq2)
        alignment = alignments[0]

        score = int(getattr(alignment, "score", 0.0))

        # Extract aligned sequences from formatted output
        # 从格式化输出中提取对齐序列
        fmt = alignment.format()
        lines = fmt.strip().split("\n")

        aligned_query_str: Optional[str] = None
        aligned_target_str: Optional[str] = None

        # Parse formatted alignment: line 0=target, line 1=match, line 2=query
        # 解析格式化对齐：第0行=目标，第1行=匹配，第2行=查询
        if len(lines) >= 3:
            # Extract sequence part (after label and position)
            # 提取序列部分（在标签和位置之后）
            target_parts = lines[0].split()
            query_parts = lines[2].split()
            # Format: "target  0 SEQUENCE 25" → take index 2
            # 格式："target  0 SEQUENCE 25" → 取索引 2
            raw_target = target_parts[2] if len(target_parts) >= 3 else ""
            raw_query = query_parts[2] if len(query_parts) >= 3 else ""

            # Build CIGAR from match line / 从匹配行构建 CIGAR
            match_line = lines[1]
            # Match line format: "          0 .||||.|| 8"
            match_parts = match_line.split()
            match_str = match_parts[1] if len(match_parts) >= 2 else ""

            matches = match_str.count("|")
            alignment_length = len(raw_target)

            # Build simple CIGAR / 构建简单 CIGAR
            cigar_parts = []
            if alignment_length > 0:
                current_op = "=" if match_str[0] == "|" else "X"
                count = 1
                for ch in match_str[1:]:
                    op = "=" if ch == "|" else "X"
                    if op == current_op:
                        count += 1
                    else:
                        cigar_parts.append(f"{count}{current_op}")
                        current_op = op
                        count = 1
                cigar_parts.append(f"{count}{current_op}")
            cigar_str = "".join(cigar_parts)

            if include_alignment:
                aligned_query_str = raw_query
                aligned_target_str = raw_target
        else:
            matches = 0
            alignment_length = 0
            cigar_str = ""

        identity = matches / alignment_length if alignment_length > 0 else 0.0

        return AlignmentResult(
            score=score,
            identity=identity,
            cigar=cigar_str,
            aligned_query=aligned_query_str,
            aligned_target=aligned_target_str,
            length=alignment_length,
            matches=matches,
        )
