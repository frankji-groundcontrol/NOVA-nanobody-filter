"""
References / 参考:
    - docs/en/README.md: Section 1.2 - Nativeness Filter
    - docs/cn/README.md: 第1.2节 - 天然性过滤器
    - metanano/config.py: NativenessConfig
    - abnumber library: IMGT numbering
    - abnativ library: Nativeness/humanness scoring

File / 文件:
    - metanano/filters/nativeness.py

Overview / 概述:
    Nativeness filter implementation for validating nanobody sequences.
    验证纳米抗体序列的天然性过滤器实现。

    Core operations:
    核心操作：
        1. IMGT numbering via abnumber
        2. Nativeness scoring via AbnatiV v2 (threshold >= 0.80)
        3. Humanness scoring via AbnatiV v2 (threshold >= 0.75)
        4. Optional promb cross-validation

Consumers / 调用方:
    - metanano/filters/__init__.py
    - metanano/validators/nativeness_validator.py
"""

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
        nativeness_score: AbnatiV nativeness score / AbnatiV 天然性分数
        humanness_score: AbnatiV humanness score / AbnatiV 人源性分数
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
        2. Nativeness score >= 0.80 (AbnatiV v2)
        3. Humanness score >= 0.75 (AbnatiV v2)
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

    def compute_nativeness_score(self, sequence: str) -> Optional[float]:
        """
        Compute nativeness score using AbnatiV v2 (VHH model).
        使用 AbnatiV v2 (VHH 模型) 计算天然性分数。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[float]: Nativeness score (0-1) or None if failed.
                天然性分数（0-1），如果失败则返回 None。

        References / 参考:
            - abnativ library: abnativ_scoring with VHH model

        Consumers / 调用方:
            - NativenessFilter.analyze
        """
        try:
            from abnativ.scoring import abnativ_scoring
            from Bio.Seq import Seq
            from Bio.SeqRecord import SeqRecord

            record = SeqRecord(Seq(sequence), id="query")
            result, _ = abnativ_scoring(
                model_type="VHH",
                seq_records=[record],
                mean_score_only=True,
                do_align=True,
                is_VHH=True,
                verbose=False,
            )
            return float(result["AbNatiV VHH Score"].iloc[0])
        except Exception:
            return None

    def compute_humanness_score(self, sequence: str) -> Optional[float]:
        """
        Compute humanness score using AbnatiV v2 (VH model).
        使用 AbnatiV v2 (VH 模型) 计算人源性分数。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[float]: Humanness score (0-1) or None if failed.
                人源性分数（0-1），如果失败则返回 None。

        References / 参考:
            - abnativ library: abnativ_scoring with VH model

        Consumers / 调用方:
            - NativenessFilter.analyze
        """
        try:
            from abnativ.scoring import abnativ_scoring
            from Bio.Seq import Seq
            from Bio.SeqRecord import SeqRecord

            record = SeqRecord(Seq(sequence), id="query")
            result, _ = abnativ_scoring(
                model_type="VH",
                seq_records=[record],
                mean_score_only=True,
                do_align=True,
                is_VHH=True,  # Use VHH alignment for nanobodies
                verbose=False,
            )
            return float(result["AbNatiV VH Score"].iloc[0])
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
            - abnativ library
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




