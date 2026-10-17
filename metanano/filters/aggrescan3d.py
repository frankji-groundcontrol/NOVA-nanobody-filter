"""Apply both whole-VHH caps to compatible, sequence-matched native A3D scores.

Inputs are the submitted sequence and Aggrescan3DWrapper's profile. The output
is a FilterResult with native provenance and an inclusive decision for each cap.
See docs/usage/aggrescan3d-rust.md, filters/developability.py and
metanano/tests/test_aggrescan3d.py. Method: doi:10.1093/nar/gkv359.
"""

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from metanano.config import Aggrescan3DConfig
from metanano.models.filter_result import FilterResult


class Aggrescan3DFilter:
    """Reject exceeded caps and report unavailable measurements as errors."""

    def __init__(self, config: Aggrescan3DConfig) -> None:
        self.config = config

    def analyze(self, sequence: str, profile: Optional[Dict[str, Any]]) -> FilterResult:
        """Evaluate a completed full-VHH profile without predicting or rescoring."""
        sequence = sequence.strip().upper()
        sequence_hash = hashlib.sha256(sequence.encode()).hexdigest()
        details: Dict[str, Any] = {
            "passed": False,
            "sequence_hash": sequence_hash,
            "citation_doi": "10.1093/nar/gkv359",
        }
        if not self.config.enabled:
            reason = "Aggrescan3D filter is disabled"
            details.update(status="disabled", reason=reason)
            return FilterResult(False, details, reason)

        try:
            if not profile or profile.get("status") != "ok":
                raise ValueError((profile or {}).get("error") or "Missing successful Aggrescan3D score")
            if not sequence or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
                raise ValueError("Expected a sequence of standard amino acids")
            if profile["sequence_hash"] != sequence_hash:
                raise ValueError("Aggrescan3D sequence hash does not match input")
            count = profile["residue_count"]
            if type(count) is not int or count != len(sequence):
                raise ValueError("Aggrescan3D residue count does not match input")
            for key in ("input_structure_sha256", "normalized_structure_sha256"):
                if not re.fullmatch(r"[0-9a-f]{64}", profile[key]):
                    raise ValueError(f"Invalid Aggrescan3D {key}")
            for key, expected in (
                ("ph_scale", "default-scale"),
                ("surface_method", "FreeSASA-2.0.1-NACCESS-LR100"),
                ("mode", "static-no-minimization"),
            ):
                if profile[key] != expected:
                    raise ValueError(f"Incompatible Aggrescan3D {key}: expected {expected}")
            if Decimal(str(profile["radius_angstrom"])) != 10:
                raise ValueError("Aggrescan3D filter requires a 10 angstrom radius")

            scores = {key: Decimal(str(profile[key])) for key in ("a3d_average", "a3d_maximum")}
            if not all(value.is_finite() for value in scores.values()):
                raise ValueError("Non-finite Aggrescan3D score")
            if scores["a3d_maximum"] < 0 or scores["a3d_average"] > scores["a3d_maximum"]:
                raise ValueError("Inconsistent Aggrescan3D mean and maximum")
        except (KeyError, ValueError, TypeError, InvalidOperation) as error:
            reason = f"Aggrescan3D scoring unavailable: {error}"
            details.update(status="error", error=str(error), reason=reason)
            return FilterResult(False, details, reason)

        checks = {
            key: {
                "value": str(scores[key]),
                "operator": "<=",
                "threshold": str(threshold),
                "passed": scores[key] <= threshold,
            }
            for key, threshold in (
                ("a3d_average", self.config.max_average),
                ("a3d_maximum", self.config.max_peak),
            )
        }
        failed = [key for key, check in checks.items() if not check["passed"]]
        reason = "; ".join(
            f"{key} ({checks[key]['value']}) > {checks[key]['threshold']}" for key in failed
        ) or None
        details.update(profile, passed=not failed, checks=checks, failed_metrics=failed)
        if reason:
            details["reason"] = reason
        return FilterResult(not failed, details, reason)
