"""Whole-VHH A3D decision boundaries, method compatibility and explicit failures.

See docs/usage/aggrescan3d-rust.md and filters/aggrescan3d.py.
Native model handoff and API execution are checked in utils/test_aggrescan3d_integration.py.
"""

import hashlib
from decimal import Decimal

import pytest

from metanano.config import Aggrescan3DConfig
from metanano.filters import Aggrescan3DFilter


SEQUENCE = "EVQLV" * 10


@pytest.fixture
def profile():
    return {
        "status": "ok",
        "sequence_hash": hashlib.sha256(SEQUENCE.encode()).hexdigest(),
        "input_structure_sha256": "a" * 64,
        "normalized_structure_sha256": "b" * 64,
        "residue_count": len(SEQUENCE),
        "radius_angstrom": 10.0,
        "ph_scale": "default-scale",
        "surface_method": "FreeSASA-2.0.1-NACCESS-LR100",
        "mode": "static-no-minimization",
        "a3d_average": -0.68002724866200,
        "a3d_maximum": 1.58023066762925,
    }


@pytest.mark.parametrize(
    "average,peak,failed",
    [
        ("-0.68002724866200", "1.58023066762925", []),
        ("-0.680027248662001", "1.580230667629249", []),
        ("-0.680027248661999", "1.58023066762925", ["a3d_average"]),
        ("-0.68002724866200", "1.580230667629251", ["a3d_maximum"]),
        ("0", "2", ["a3d_average", "a3d_maximum"]),
    ],
)
def test_both_caps_are_inclusive_and_use_unrounded_values(profile, average, peak, failed):
    profile.update(a3d_average=average, a3d_maximum=peak)
    result = Aggrescan3DFilter(Aggrescan3DConfig()).analyze(SEQUENCE, profile)

    assert result.passed == (not failed)
    assert result.details["status"] == "ok"
    assert result.details["failed_metrics"] == failed
    assert result.details["checks"]["a3d_average"]["threshold"] == "-0.68002724866200"
    assert result.details["checks"]["a3d_maximum"]["threshold"] == "1.58023066762925"
    assert profile["a3d_average"] == average


@pytest.mark.parametrize(
    "key,value",
    [
        ("a3d_average", float("nan")),
        ("a3d_maximum", float("inf")),
        ("a3d_average", None),
        ("a3d_maximum", -1),
        ("sequence_hash", "c" * 64),
        ("residue_count", 1),
        ("input_structure_sha256", "missing"),
        ("normalized_structure_sha256", ""),
        ("radius_angstrom", 5),
        ("ph_scale", "7.4"),
        ("mode", "dynamic"),
        ("surface_method", "FreeSASA-2.2.1"),
    ],
)
def test_invalid_or_incompatible_measurement_cannot_pass(profile, key, value):
    profile[key] = value
    result = Aggrescan3DFilter(Aggrescan3DConfig()).analyze(SEQUENCE, profile)

    assert not result.passed
    assert result.details["status"] == "error"
    assert result.reason
    assert "checks" not in result.details


@pytest.mark.parametrize("profile", [None, {}, {"status": "error", "error": "Native tool unavailable"}])
def test_missing_or_failed_scoring_is_explicit(profile):
    result = Aggrescan3DFilter(Aggrescan3DConfig()).analyze(SEQUENCE, profile)

    assert not result.passed
    assert result.details["status"] == "error"
    assert result.details["reason"] == result.reason
    if profile and "error" in profile:
        assert profile["error"] in result.reason


def test_default_registration_and_explicit_disable(monkeypatch, profile):
    from metanano.config import Config

    monkeypatch.delenv("AGGRESCAN3D_ENABLED", raising=False)
    assert Config().developability.aggrescan3d.enabled
    assert Config().developability.aggrescan3d.max_average == Decimal("-0.68002724866200")
    assert Config().developability.aggrescan3d.max_peak == Decimal("1.58023066762925")
    result = Aggrescan3DFilter(Aggrescan3DConfig(enabled=False)).analyze(SEQUENCE, profile)
    assert not result.passed
    assert result.details["status"] == "disabled"


@pytest.mark.parametrize("field", ["max_average", "max_peak"])
def test_nonfinite_policy_is_rejected(field):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Aggrescan3DConfig(**{field: "NaN"})


def test_passing_a3d_does_not_override_tnp_red_region(profile):
    from metanano.config import DevelopabilityConfig
    from metanano.filters.developability import DevelopabilityFilter

    result = DevelopabilityFilter(DevelopabilityConfig()).analyze_profile(
        SEQUENCE,
        {
            "total_cdr_length": 10,
            "cdr3_length": 10,
            "cdr3_compactness": 1.0,
            "surface_hydrophobic_patches": 100.0,
            "positive_charge_patches": 0.5,
            "negative_charge_patches": 0.5,
            "aggrescan3d": profile,
        },
    )

    assert not result.passed
    assert result.aggrescan3d["passed"]
    assert "total_cdr_length" in result.reason
    assert result.red_flags
