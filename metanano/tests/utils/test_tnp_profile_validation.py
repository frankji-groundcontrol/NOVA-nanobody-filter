"""Recover valid TNP output after malformed, incomplete or non-finite profiles.

Exercise the CLI JSON boundary and the A3D handoff in utils/tnp_wrapper.py.
Invalid attempts must never reach the structural scorer or become measurements.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "utils" / "tnp_wrapper.py"
SPEC = importlib.util.spec_from_file_location("tnp_profile_validation", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
SEQUENCE = "G" * 60


@pytest.mark.parametrize("failure", ["null", "wrong_shape", "missing_metric", "invalid_number", "nan", "infinity"])
def test_invalid_attempt_is_recomputed_before_a3d(monkeypatch, failure):
    attempts = []
    scored = []

    def run_tnp(command, **kwargs):
        attempts.append(command)
        name = command[command.index("--name") + 1]
        output = Path(command[command.index("--output") + 1])
        values = {
            "Total CDR Length": 30,
            "CDR3 Length": 10,
            "CDR3 Compactness": 1.0,
            "PSH": 100.0,
            "PPC": 0.5,
            "PNC": 0.5,
            "Flags": {"L": "green"},
        }
        if len(attempts) == 1:
            if failure == "null":
                values = None
            elif failure == "wrong_shape":
                values = []
            elif failure == "missing_metric":
                del values["PSH"]
            elif failure == "invalid_number":
                values["CDR3 Length"] = "invalid"
            else:
                values["PSH"] = float("nan" if failure == "nan" else "inf")
        (output / f"TNP_Results_SingleSeqEntry_{name}.json").write_text(json.dumps({name: values}))
        models = output / "Final_Models"
        models.mkdir()
        (models / f"{name}_NanoBodyBuilder2_Model.pdb").write_text("model fixture")
        return subprocess.CompletedProcess(command, 0, "", "")

    def score(sequence, structure):
        assert sequence == SEQUENCE
        assert structure.read_text() == "model fixture"
        scored.append(structure)
        return {"status": "ok"}

    monkeypatch.setattr(module.shutil, "which", lambda executable: "/usr/bin/TNP")
    monkeypatch.setattr(module.subprocess, "run", run_tnp)
    result = module.TNPWrapper(aggrescan3d=score).profile(SEQUENCE)

    assert result is not None
    assert result.psh == 100.0
    assert len(attempts) == 2
    assert len(scored) == 1
    assert not scored[0].exists()


@pytest.mark.parametrize("endpoint", ["analyze", "analyze-batch"])
def test_developability_api_preserves_typed_compute_errors(monkeypatch, endpoint):
    import hashlib
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from metanano.routes import developability_routes

    digest = hashlib.sha256(SEQUENCE.encode()).hexdigest()
    failure = {
        "passed": False,
        "error": True,
        "error_kind": "no_profile",
        "sequence_sha256": digest,
        "reason": "Failed to compute TNP profile.",
    }
    service = SimpleNamespace(
        analyze_async=AsyncMock(return_value=failure),
        analyze_batch_async=AsyncMock(return_value=[failure]),
    )
    monkeypatch.setattr(developability_routes, "_service", service)
    app = FastAPI()
    app.include_router(developability_routes.router)
    body = {"sequence": SEQUENCE} if endpoint == "analyze" else {"sequences": [SEQUENCE]}
    with TestClient(app) as client:
        response = client.post(f"/developability/{endpoint}", json=body)

    assert response.status_code == 200
    result = response.json() if endpoint == "analyze" else response.json()["results"][0]
    assert not result["passed"]
    assert result["error"] is True
    assert result["error_kind"] == "no_profile"
    assert result["sequence_sha256"] == digest
