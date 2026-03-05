"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - docs/cn/README.md: 第1.2节 - 天然性过滤器
    - metanano/config.py: NativenessConfig
    - abnumber library: IMGT numbering
    - metanano.utils.igblast_nativeness: IgBLAST-based nativeness/humanness scoring

File / 文件:
    - metanano/filters/nativeness.py

Overview / 概述:
    Nativeness filter implementation for validating nanobody sequences.
    验证纳米抗体序列的天然性过滤器实现。

    Core operations:
    核心操作：
        1. IMGT numbering via abnumber
        2. Nativeness scoring via IgBLAST-based VHH nativeness heuristic
        3. Humanness scoring via IgBLAST-based human framework heuristic
        4. Optional promb cross-validation

Consumers / 调用方:
    - metanano/filters/__init__.py
    - metanano/validators/nativeness_validator.py
"""

import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

from metanano.config import NativenessConfig


@dataclass
class NativenessResult:
    """
    Result from nativeness filter analysis.
    天然性过滤器分析结果。

    Attributes / 属性:
        passed: Whether nativeness requirements are met / 是否满足天然性要求
        imgt_numbered: Whether IMGT numbering succeeded / IMGT 编号是否成功
        nativeness_score: Nativeness score / 天然性分数
        humanness_score: Humanness score / 人源性分数
        promb_score: Optional promb OASis score / 可选的 promb OASis 分数
        reason: Failure reason if not passed / 未通过时的失败原因

    Consumers / 调用方:
        - metanano/validators/nativeness_validator.py
    """

    passed: bool
    imgt_numbered: bool = False
    nativeness_score: Optional[float] = None
    humanness_score: Optional[float] = None
    promb_score: Optional[float] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary. / 转换为字典。"""
        result = {
            "passed": self.passed,
            "imgt_numbered": self.imgt_numbered,
        }
        if self.nativeness_score is not None:
            result["nativeness_score"] = self.nativeness_score
        if self.humanness_score is not None:
            result["humanness_score"] = self.humanness_score
        if self.promb_score is not None:
            result["promb_score"] = self.promb_score
        if self.reason:
            result["reason"] = self.reason
        return result


class NativenessFilter:
    """
    Filter for validating nanobody nativeness and humanness.
    验证纳米抗体天然性和人源性的过滤器。

    This filter checks:
    该过滤器检查：
        1. IMGT numbering success (abnumber)
        2. Nativeness score >= 0.80 (IgBLAST VHH nativeness heuristic)
        3. Humanness score >= 0.75 (IgBLAST human framework heuristic)
        4. Optional: promb OASis humanness cross-validation

    Example / 示例:
        >>> config = NativenessConfig()
        >>> filter = NativenessFilter(config)
        >>> result = filter.analyze(sequence)

    Consumers / 调用方:
        - metanano/filters/__init__.py
        - metanano/validators/nativeness_validator.py
    """

    def __init__(self, config: NativenessConfig) -> None:
        """
        Initialize the nativeness filter.
        初始化天然性过滤器。

        Args / 参数:
            config (NativenessConfig): Filter configuration.
                过滤器配置。

        References / 参考:
            - metanano/config.py: NativenessConfig
        """
        self.config = config
        self._abnumber_scheme = config.abnumber.scheme
        # Cache for IgBLAST-based nativeness results to avoid duplicate work
        # IgBLAST 结果缓存，以避免重复计算
        self._last_igblast_sequence: Optional[str] = None
        self._last_igblast_result: Optional[Dict[str, Any]] = None

    def number_sequence(self, sequence: str) -> Optional[Dict[str, Any]]:
        """
        Apply IMGT numbering to the sequence.
        对序列应用 IMGT 编号。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[Dict[str, Any]]: Numbered sequence data or None if failed.
                编号后的序列数据，如果失败则返回 None。

        References / 参考:
            - abnumber library: Chain class

        Consumers / 调用方:
            - NativenessFilter.analyze
        """
        try:
            from abnumber import Chain

            chain = Chain(sequence, scheme=self._abnumber_scheme)
            return {
                "chain": chain,
                "scheme": self._abnumber_scheme,
                "cdr1": str(chain.cdr1_seq) if chain.cdr1_seq else None,
                "cdr2": str(chain.cdr2_seq) if chain.cdr2_seq else None,
                "cdr3": str(chain.cdr3_seq) if chain.cdr3_seq else None,
            }
        except Exception:
            return None
    def _get_igblast_result(self, sequence: str) -> Optional[Dict[str, Any]]:
        """
        Run IgBLAST-based nativeness scoring for a single sequence.
        对单个序列运行基于 IgBLAST 的天然性评分。

        Returns / 返回:
            Optional[Dict[str, Any]]: Result dict from
                metanano.utils.igblast_nativeness.run or None on failure. /
                结果字典或在失败时返回 None。
        """
        seq = (sequence or "").strip()
        if not seq:
            return None

        # Return cached result if the same sequence was scored previously.
        # 如果是之前评分过的相同序列，则返回缓存结果。
        if self._last_igblast_sequence == seq and self._last_igblast_result is not None:
            return self._last_igblast_result

        try:
            # Import lazily to avoid hard dependency when not needed.
            # 延迟导入以避免在不需要时产生硬依赖。
            from metanano.utils import igblast_nativeness

            with tempfile.TemporaryDirectory() as td:
                fasta_path = os.path.join(td, "query.fasta")
                with open(fasta_path, "w", encoding="utf-8") as fh:
                    fh.write(">query\n")
                    fh.write(seq + "\n")

                results = igblast_nativeness.run(fasta_path)
        except Exception:
            return None

        if not results:
            return None

        result = results[0]
        self._last_igblast_sequence = seq
        self._last_igblast_result = result
        return result

    def compute_nativeness_score(self, sequence: str) -> Optional[float]:
        """
        Compute nativeness score using IgBLAST-based VHH nativeness heuristic.
        使用基于 IgBLAST 的 VHH 天然性启发式方法计算天然性分数。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[float]: Nativeness score (0-1) or None if failed.
                天然性分数（0-1），如果失败则返回 None。

        References / 参考:
            - metanano.utils.igblast_nativeness: vhh_nativeness_score

        Consumers / 调用方:
            - NativenessFilter.analyze
        """
        result = self._get_igblast_result(sequence)
        if not result:
            return None
        if result.get("hard_reject"):
            return None
        score = result.get("vhh_nativeness")
        if score is None:
            return None
        try:
            return float(score)
        except Exception:
            return None

    def compute_humanness_score(self, sequence: str) -> Optional[float]:
        """
        Compute humanness score using IgBLAST-based human framework heuristic.
        使用基于 IgBLAST 的人源框架启发式方法计算人源性分数。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[float]: Humanness score (0-1) or None if failed.
                人源性分数（0-1），如果失败则返回 None。

        References / 参考:
            - metanano.utils.igblast_nativeness: human_framework_score

        Consumers / 调用方:
            - NativenessFilter.analyze
        """
        result = self._get_igblast_result(sequence)
        if not result:
            return None
        if result.get("hard_reject"):
            return None
        score = result.get("human_framework")
        if score is None:
            return None
        try:
            return float(score)
        except Exception:
            return None

    def compute_promb_score(self, sequence: str) -> Optional[float]:
        """
        Compute OASis humanness score using promb (optional).
        使用 promb 计算 OASis 人源性分数（可选）。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[float]: OASis score or None if disabled/failed.
                OASis 分数，如果禁用/失败则返回 None。

        References / 参考:
            - promb library

        Consumers / 调用方:
            - NativenessFilter.analyze
        """
        if not self.config.promb.enabled:
            return None

        try:
            from promb import compute_humanness

            score = compute_humanness(
                sequence,
                db=self.config.promb.db,
                peptide_length=self.config.promb.peptide_length,
            )
            return score
        except Exception:
            return None

    def analyze(self, sequence: str) -> NativenessResult:
        """
        Perform complete nativeness analysis.
        执行完整的天然性分析。

        Args / 参数:
            sequence (str): The nanobody sequence to analyze.
                要分析的纳米抗体序列。

        Returns / 返回:
            NativenessResult: Complete analysis result.
                完整的分析结果。

        References / 参考:
            - abnumber library
            - metanano.utils.igblast_nativeness
            - promb library (optional)

        Consumers / 调用方:
            - metanano/validators/nativeness_validator.py
        """
        # Step 1: IMGT numbering
        # 第1步：IMGT 编号
        numbered = self.number_sequence(sequence)
        if not numbered:
            return NativenessResult(
                passed=False,
                imgt_numbered=False,
                reason="Failed to number sequence under IMGT scheme. / "
                "无法使用 IMGT 方案对序列编号。",
            )

        # Step 2: Nativeness score
        # 第2步：天然性分数
        nativeness = self.compute_nativeness_score(sequence)
        if nativeness is None:
            return NativenessResult(
                passed=False,
                imgt_numbered=True,
                reason="Failed to compute nativeness score. / "
                "无法计算天然性分数。",
            )

        nativeness_threshold = self.config.abnativ_v2.nativeness_threshold
        if nativeness < nativeness_threshold:
            return NativenessResult(
                passed=False,
                imgt_numbered=True,
                nativeness_score=nativeness,
                reason=f"nativeness_score ({nativeness:.2f}) below threshold "
                f"({nativeness_threshold}). / "
                f"天然性分数 ({nativeness:.2f}) 低于阈值 ({nativeness_threshold})。",
            )

        # Step 3: Humanness score
        # 第3步：人源性分数
        humanness = self.compute_humanness_score(sequence)
        if humanness is None:
            return NativenessResult(
                passed=False,
                imgt_numbered=True,
                nativeness_score=nativeness,
                reason="Failed to compute humanness score. / "
                "无法计算人源性分数。",
            )

        humanness_threshold = self.config.abnativ_v2.humanness_threshold
        if humanness < humanness_threshold:
            return NativenessResult(
                passed=False,
                imgt_numbered=True,
                nativeness_score=nativeness,
                humanness_score=humanness,
                reason=f"humanness_score ({humanness:.2f}) below threshold "
                f"({humanness_threshold}). / "
                f"人源性分数 ({humanness:.2f}) 低于阈值 ({humanness_threshold})。",
            )

        # Step 4: Optional promb cross-validation
        # 第4步：可选的 promb 交叉验证
        promb_score = self.compute_promb_score(sequence)

        return NativenessResult(
            passed=True,
            imgt_numbered=True,
            nativeness_score=nativeness,
            humanness_score=humanness,
            promb_score=promb_score,
        )




