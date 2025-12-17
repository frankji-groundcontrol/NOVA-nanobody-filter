"""
References / 参考:
    - docs/en/README.md: Section 1.3 - Developability Filter
    - docs/cn/README.md: 第1.3节 - 可开发性过滤器
    - docs/en/TODO.md: Section 0.1 - TNP Integration
    - metanano/config.py: DevelopabilityConfig
    - metanano/utils/tnp_wrapper.py: TNPWrapper
    - TNP GitHub: https://github.com/oxpig/TNP

File / 文件:
    - metanano/filters/developability.py

Overview / 概述:
    Developability filter implementation for therapeutic readiness assessment.
    评估治疗就绪性的可开发性过滤器实现。

    Uses TNP CLI tool for profiling:
    使用 TNP CLI 工具进行分析：
        TNP --name <name> --output <dir> --seq <sequence>

    Red Region criteria (July 2025) - sequences are REJECTED if ANY condition is met:
    红区标准（2025年7月）- 如果满足任一条件则序列被拒绝：
        1. Total CDR length: REJECT if L < 20 OR L > 39
        2. CDR3 length: REJECT if L3 < 5 OR L3 > 23
        3. CDR3 compactness: REJECT if C < 0.56 OR C > 1.61
        4. Surface hydrophobic patches: REJECT if PSH < 73.4 OR PSH > 155.47
        5. Positive charge patches: REJECT if PPC > 1.18
        6. Negative charge patches: REJECT if PNC > 1.88

Consumers / 调用方:
    - metanano/filters/__init__.py
    - metanano/validators/developability_validator.py
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from metanano.config import DevelopabilityConfig
from metanano.utils.tnp_wrapper import TNPWrapper


@dataclass
class DevelopabilityResult:
    """
    Result from developability filter analysis.
    可开发性过滤器分析结果。

    Attributes / 属性:
        passed: Whether sequence passed (no Red Region criteria triggered) / 
            序列是否通过（无红区标准被触发）
        total_cdr_length: Total length of all CDRs / 所有 CDR 的总长度
        cdr3_length: Length of CDR3 / CDR3 的长度
        cdr3_compactness: CDR3 compactness score / CDR3 紧凑度分数
        surface_hydrophobic_patches: PSH score / PSH 分数
        positive_charge_patches: PPC score / PPC 分数
        negative_charge_patches: PNC score / PNC 分数
        red_flags: List of Red Region criteria that were triggered / 被触发的红区标准列表
        reason: Failure reason if not passed / 未通过时的失败原因

    Consumers / 调用方:
        - metanano/validators/developability_validator.py
    """

    passed: bool
    total_cdr_length: Optional[int] = None
    cdr3_length: Optional[int] = None
    cdr3_compactness: Optional[float] = None
    surface_hydrophobic_patches: Optional[float] = None
    positive_charge_patches: Optional[float] = None
    negative_charge_patches: Optional[float] = None
    red_flags: Optional[List[str]] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary. / 转换为字典。"""
        result = {"passed": self.passed}
        if self.total_cdr_length is not None:
            result["total_cdr_length"] = self.total_cdr_length
        if self.cdr3_length is not None:
            result["cdr3_length"] = self.cdr3_length
        if self.cdr3_compactness is not None:
            result["cdr3_compactness"] = self.cdr3_compactness
        if self.surface_hydrophobic_patches is not None:
            result["surface_hydrophobic_patches"] = self.surface_hydrophobic_patches
        if self.positive_charge_patches is not None:
            result["positive_charge_patches"] = self.positive_charge_patches
        if self.negative_charge_patches is not None:
            result["negative_charge_patches"] = self.negative_charge_patches
        if self.red_flags:
            result["red_flags"] = self.red_flags
        if self.reason:
            result["reason"] = self.reason
        return result


class DevelopabilityFilter:
    """
    Filter for assessing therapeutic developability of nanobodies.
    评估纳米抗体治疗可开发性的过滤器。

    Uses TNP (Therapeutic Nanobody Profiler) to evaluate sequences
    against Red Region criteria for therapeutic candidates.
    使用 TNP（治疗性纳米抗体分析器）根据红区标准评估治疗候选序列。

    Red Region: Sequences are REJECTED if ANY property falls in the Red Region.
    红区：如果任一属性落在红区内，则序列被拒绝。

    Example / 示例:
        >>> config = DevelopabilityConfig()
        >>> filter = DevelopabilityFilter(config)
        >>> result = filter.analyze(sequence)
        >>> if not result.passed:
        ...     print(f"Rejected due to: {result.red_flags}")

    Consumers / 调用方:
        - metanano/filters/__init__.py
        - metanano/validators/developability_validator.py
    """

    def __init__(self, config: DevelopabilityConfig) -> None:
        """
        Initialize the developability filter.
        初始化可开发性过滤器。

        Args / 参数:
            config (DevelopabilityConfig): Filter configuration.
                过滤器配置。

        References / 参考:
            - metanano/config.py: DevelopabilityConfig
            - metanano/utils/tnp_wrapper.py: TNPWrapper
        """
        self.config = config
        self._tnp = TNPWrapper()

    def compute_tnp_profile(self, sequence: str) -> Optional[Dict[str, Any]]:
        """
        Compute TNP profile for the sequence using TNP CLI.
        使用 TNP CLI 计算序列的 TNP 分析结果。

        Args / 参数:
            sequence (str): The nanobody sequence.
                纳米抗体序列。

        Returns / 返回:
            Optional[Dict[str, Any]]: TNP profile or None if failed.
                TNP 分析结果，如果失败则返回 None。

        References / 参考:
            - metanano/utils/tnp_wrapper.py: TNPWrapper.profile
            - TNP GitHub: https://github.com/oxpig/TNP

        Consumers / 调用方:
            - DevelopabilityFilter.analyze
        """
        result = self._tnp.profile(sequence)
        if result is None:
            return None
        return result.to_profile_dict()

    def check_red_region(
        self,
        profile: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """
        Check if profile triggers any Red Region criteria (rejection conditions).
        检查分析结果是否触发任何红区标准（拒绝条件）。

        Red Region defines problematic properties that make sequences unsuitable
        for therapeutic development. If ANY criterion is triggered, the sequence
        is REJECTED.
        红区定义了使序列不适合治疗开发的问题属性。如果触发任何标准，
        序列将被拒绝。

        Args / 参数:
            profile (Dict[str, Any]): TNP profile results.
                TNP 分析结果。

        Returns / 返回:
            tuple[bool, List[str]]: (passed, list_of_red_flags)
                - passed: True if NO red flags triggered (sequence is acceptable)
                - list_of_red_flags: Criteria that were triggered (rejection reasons)
                (是否通过, 红旗列表)
                - passed: 如果没有红旗被触发则为 True（序列可接受）
                - list_of_red_flags: 被触发的标准（拒绝原因）

        Consumers / 调用方:
            - DevelopabilityFilter.analyze
        """
        red_flags = []

        # Total CDR length: REJECT if L < min OR L > max (outside normal range)
        # 总 CDR 长度：如果 L < min 或 L > max 则拒绝（在正常范围外）
        total_cdr = profile.get("total_cdr_length", 0)
        cdr_config = self.config.total_cdr_length
        if total_cdr < cdr_config.min or total_cdr > cdr_config.max:
            red_flags.append(
                f"total_cdr_length ({total_cdr}) outside valid range "
                f"[{cdr_config.min}, {cdr_config.max}] / "
                f"总CDR长度 ({total_cdr}) 超出有效范围 [{cdr_config.min}, {cdr_config.max}]"
            )

        # CDR3 length: REJECT if L3 < min OR L3 > max
        # CDR3 长度：如果 L3 < min 或 L3 > max 则拒绝
        cdr3_len = profile.get("cdr3_length", 0)
        cdr3_config = self.config.cdr3_length
        if cdr3_len < cdr3_config.min or cdr3_len > cdr3_config.max:
            red_flags.append(
                f"cdr3_length ({cdr3_len}) outside valid range "
                f"[{cdr3_config.min}, {cdr3_config.max}] / "
                f"CDR3长度 ({cdr3_len}) 超出有效范围 [{cdr3_config.min}, {cdr3_config.max}]"
            )

        # CDR3 compactness: REJECT if C < min OR C > max
        # CDR3 紧凑度：如果 C < min 或 C > max 则拒绝
        compactness = profile.get("cdr3_compactness", 0)
        compact_config = self.config.cdr3_compactness
        if compactness < compact_config.min or compactness > compact_config.max:
            red_flags.append(
                f"cdr3_compactness ({compactness:.2f}) outside valid range "
                f"[{compact_config.min}, {compact_config.max}] / "
                f"CDR3紧凑度 ({compactness:.2f}) 超出有效范围 "
                f"[{compact_config.min}, {compact_config.max}]"
            )

        # Surface hydrophobic patches: REJECT if PSH < min OR PSH > max
        # 表面疏水性斑块：如果 PSH < min 或 PSH > max 则拒绝
        psh = profile.get("surface_hydrophobic_patches", 0)
        psh_config = self.config.surface_hydrophobic_patches
        if psh < psh_config.min or psh > psh_config.max:
            red_flags.append(
                f"surface_hydrophobic_patches ({psh:.2f}) outside valid range "
                f"[{psh_config.min}, {psh_config.max}] / "
                f"表面疏水性斑块 ({psh:.2f}) 超出有效范围 "
                f"[{psh_config.min}, {psh_config.max}]"
            )

        # Positive charge patches: REJECT if PPC > threshold
        # 正电荷斑块：如果 PPC > threshold 则拒绝
        ppc = profile.get("positive_charge_patches", 0)
        ppc_threshold = self.config.positive_charge_patches.threshold
        if ppc > ppc_threshold:
            red_flags.append(
                f"positive_charge_patches ({ppc:.2f}) > threshold ({ppc_threshold}) / "
                f"正电荷斑块 ({ppc:.2f}) > 阈值 ({ppc_threshold})"
            )

        # Negative charge patches: REJECT if PNC > threshold
        # 负电荷斑块：如果 PNC > threshold 则拒绝
        pnc = profile.get("negative_charge_patches", 0)
        pnc_threshold = self.config.negative_charge_patches.threshold
        if pnc > pnc_threshold:
            red_flags.append(
                f"negative_charge_patches ({pnc:.2f}) > threshold ({pnc_threshold}) / "
                f"负电荷斑块 ({pnc:.2f}) > 阈值 ({pnc_threshold})"
            )

        # Pass only if NO red flags were triggered
        # 仅当没有红旗被触发时才通过
        passed = len(red_flags) == 0
        return passed, red_flags

    def analyze(self, sequence: str) -> DevelopabilityResult:
        """
        Perform complete developability analysis.
        执行完整的可开发性分析。

        Sequences are REJECTED if ANY Red Region criterion is triggered.
        如果触发任何红区标准，序列将被拒绝。

        Args / 参数:
            sequence (str): The nanobody sequence to analyze.
                要分析的纳米抗体序列。

        Returns / 返回:
            DevelopabilityResult: Complete analysis result.
                - passed=True: Sequence is acceptable (no red flags)
                - passed=False: Sequence is rejected (red flags triggered)
                完整的分析结果。
                - passed=True: 序列可接受（无红旗）
                - passed=False: 序列被拒绝（红旗被触发）

        References / 参考:
            - TNP library

        Consumers / 调用方:
            - metanano/validators/developability_validator.py
        """
        # Compute TNP profile
        # 计算 TNP 分析结果
        profile = self.compute_tnp_profile(sequence)
        if not profile:
            return DevelopabilityResult(
                passed=False,
                reason="Failed to compute TNP profile. / "
                "无法计算 TNP 分析结果。",
            )

        # Check Red Region criteria (rejection conditions)
        # 检查红区标准（拒绝条件）
        passed, red_flags = self.check_red_region(profile)

        return DevelopabilityResult(
            passed=passed,
            total_cdr_length=profile.get("total_cdr_length"),
            cdr3_length=profile.get("cdr3_length"),
            cdr3_compactness=profile.get("cdr3_compactness"),
            surface_hydrophobic_patches=profile.get("surface_hydrophobic_patches"),
            positive_charge_patches=profile.get("positive_charge_patches"),
            negative_charge_patches=profile.get("negative_charge_patches"),
            red_flags=red_flags if red_flags else None,
            reason="; ".join(red_flags) if red_flags else None,
        )
