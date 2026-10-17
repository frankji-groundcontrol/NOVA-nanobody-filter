"""TNP structure handoff and registered A3D filtering.

See docs/usage/aggrescan3d-rust.md and metanano/utils/tnp_wrapper.py.
"""

import importlib.util
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "tnp_a3d_under_test", ROOT / "metanano" / "utils" / "tnp_wrapper.py"
)
tnp_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tnp_module)
SEQUENCE = "GGGGGGGGGG"


@pytest.fixture
def tnp_output(monkeypatch, request):
    calls = []
    original_run = subprocess.run
    model_text = getattr(request, "param", "model fixture")

    def run_tnp(command, **kwargs):
        if command[0] != "TNP":
            return original_run(command, **kwargs)
        name = command[command.index("--name") + 1]
        directory = Path(command[command.index("--output") + 1])
        calls.append(directory)
        payload = {
            name: {
                "name": name,
                "Total CDR Length": 30,
                "CDR3 Length": 10,
                "CDR3 Compactness": 1.0,
                "PSH": 100.0,
                "PPC": 0.5,
                "PNC": 0.5,
                "Flags": {"L": "green"},
            }
        }
        (directory / f"TNP_Results_SingleSeqEntry_{name}.json").write_text(
            json.dumps(payload)
        )
        models = directory / "Final_Models"
        models.mkdir()
        (models / f"{name}_NanoBodyBuilder2_Model.pdb").write_text(model_text)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(tnp_module.subprocess, "run", run_tnp)
    monkeypatch.setattr(tnp_module.TNPWrapper, "_check_tnp_available", lambda self: True)
    from metanano.utils.tnp_wrapper import TNPWrapper
    monkeypatch.setattr(TNPWrapper, "_check_tnp_available", lambda self: True)
    return calls


def test_scores_existing_tnp_model_before_temporary_cleanup(tnp_output):
    structures = []
    score = {"status": "ok", "a3d_average": -0.5}

    def score_model(sequence, structure):
        assert sequence == SEQUENCE
        assert structure.read_text() == "model fixture"
        assert structure.parent.name == "Final_Models"
        structures.append(structure)
        return score

    result = tnp_module.TNPWrapper(aggrescan3d=score_model).profile(SEQUENCE)

    assert result.to_profile_dict()["aggrescan3d"] == score
    assert len(tnp_output) == 1
    assert len(structures) == 1
    assert not structures[0].exists()


def test_scoring_error_preserves_tnp_metrics_without_repeating_prediction(tnp_output):
    error = {"status": "error", "error": "Native scorer is unavailable"}
    result = tnp_module.TNPWrapper(
        aggrescan3d=lambda sequence, structure: error
    ).profile(SEQUENCE)

    profile = result.to_profile_dict()
    assert profile["aggrescan3d"] == error
    assert profile["surface_hydrophobic_patches"] == 100.0
    assert len(tnp_output) == 1


def test_disabled_scoring_preserves_original_profile(tnp_output):
    result = tnp_module.TNPWrapper().profile(SEQUENCE)

    assert "aggrescan3d" not in result.to_profile_dict()
    assert len(tnp_output) == 1


def synthetic_model(sequence=SEQUENCE):
    lines = []
    serial = 0
    for residue, amino_acid in enumerate(sequence, start=1):
        residue_name = {"G": "GLY", "A": "ALA"}[amino_acid]
        atoms = [
            ("N", -1.2, 0.8, "N"), ("CA", 0.0, 0.0, "C"),
            ("C", 1.2, 0.8, "C"), ("O", 1.8, 1.8, "O"),
        ]
        if amino_acid == "A":
            atoms.append(("CB", 0.0, -1.5, "C"))
        for atom, offset, height, element in atoms:
            serial += 1
            position = residue * 3.8 + offset
            lines.append(
                f"ATOM  {serial:5d} {atom:>4s} {residue_name} H{residue:4d}    "
                f"{position:8.3f}{height:8.3f}{0.0:8.3f}"
                f"{1.0:6.2f}{20.0:6.2f}          {element:>2s}\n"
            )
    return "".join(lines)


@pytest.fixture
def native_config():
    from metanano.config import Aggrescan3DConfig

    executable = ROOT / ".tools" / "bin" / "aggrescan3d-rs"
    freesasa = ROOT / ".tools" / "bin" / "freesasa"
    if not executable.is_file() or not freesasa.is_file():
        pytest.skip("Run sh install/install-aggrescan3d.sh for native acceptance tests")
    return Aggrescan3DConfig(
        enabled=True, executable=str(executable), freesasa_executable=str(freesasa)
    )


def test_real_native_scoring_preserves_model_and_returns_provenance(tmp_path, native_config):
    from metanano.utils.aggrescan3d_wrapper import Aggrescan3DWrapper

    structure = tmp_path / "input.pdb"
    structure.write_text(synthetic_model())
    original = structure.read_bytes()
    result = Aggrescan3DWrapper(
        native_config.executable, native_config.freesasa_executable
    ).profile(SEQUENCE, structure)

    assert result["status"] == "ok", result
    assert result["sequence_hash"] == hashlib.sha256(SEQUENCE.encode()).hexdigest()
    assert result["input_structure_sha256"] == hashlib.sha256(original).hexdigest()
    assert len(result["normalized_structure_sha256"]) == 64
    assert result["residue_count"] == len(SEQUENCE)
    assert result["positive_residue_count"] == 0
    assert result["a3d_average"] < 0
    assert result["a3d_average"] == result["a3d_total"] / len(SEQUENCE)
    assert math.isclose(result["a3d_total"], result["a3d_average"] * len(SEQUENCE), abs_tol=1e-10)
    assert result["surface_method"] == "FreeSASA-2.0.1-NACCESS-LR100"
    assert result["citation_doi"] == "10.1093/nar/gkv359"
    assert structure.read_bytes() == original


@pytest.mark.parametrize("failure", ["sequence", "missing_atoms"])
def test_native_input_failures_are_explicit(tmp_path, native_config, failure):
    from metanano.utils.aggrescan3d_wrapper import Aggrescan3DWrapper

    structure = tmp_path / "input.pdb"
    model = synthetic_model()
    sequence = SEQUENCE
    if failure == "sequence":
        sequence = SEQUENCE[:-1] + "A"
        expected = "Structure sequence differs"
    else:
        model = "".join(line for line in model.splitlines(True) if line[12:16].strip() != "O")
        expected = "Missing heavy atoms"
    structure.write_text(model)
    result = Aggrescan3DWrapper(
        native_config.executable, native_config.freesasa_executable
    ).profile(sequence, structure)

    assert result["status"] == "error"
    assert expected in result["error"]
    assert "a3d_average" not in result


@pytest.mark.parametrize("failure", ["missing_binary", "timeout"])
def test_native_execution_failures_are_explicit_errors(tmp_path, monkeypatch, failure):
    from metanano.utils.aggrescan3d_wrapper import Aggrescan3DWrapper

    structure = tmp_path / "input.pdb"
    structure.write_text(synthetic_model())
    if failure == "timeout":
        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 60)
        monkeypatch.setattr(subprocess, "run", timeout)
    result = Aggrescan3DWrapper(str(tmp_path / "missing-scorer")).profile(SEQUENCE, structure)

    assert result["status"] == "error"
    assert result["error"]
    assert result["citation_doi"] == "10.1093/nar/gkv359"


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("sequence_hash", "0" * 64, "sequence hash"),
        ("input_structure_sha256", "0" * 64, "structure hash"),
        ("residue_count", "9", "residue counts"),
        ("a3d_average", "NaN", "non-finite"),
    ],
)
def test_native_summary_identity_and_numbers_are_validated(
    tmp_path, monkeypatch, field, value, expected
):
    from metanano.utils.aggrescan3d_wrapper import Aggrescan3DWrapper

    structure = tmp_path / "input.pdb"
    structure.write_text(synthetic_model())

    def native_summary(command, **kwargs):
        directory = Path(command[command.index("--out") + 1])
        directory.mkdir()
        row = {
            "status": "ok",
            "sequence_hash": hashlib.sha256(SEQUENCE.encode()).hexdigest(),
            "input_structure_sha256": hashlib.sha256(structure.read_bytes()).hexdigest(),
            "residue_count": "10",
            "positive_residue_count": "0",
            "a3d_total": "-10", "a3d_average": "-1", "a3d_maximum": "0",
            "a3d_minimum": "-1", "a3d_positive_auc": "0",
        }
        row[field] = value
        with (directory / "aggrescan3d.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", native_summary)
    result = Aggrescan3DWrapper().profile(SEQUENCE, structure)

    assert result["status"] == "error"
    assert expected in result["error"]


@pytest.mark.parametrize("tnp_output", [synthetic_model()], indirect=True, ids=["complete-model"])
def test_sync_validator_includes_native_scores(tnp_output, native_config):
    from metanano.config import DevelopabilityConfig
    from metanano.validators.developability_validator import DevelopabilityValidator

    validator = DevelopabilityValidator(DevelopabilityConfig(aggrescan3d=native_config))
    result = validator.validate(SEQUENCE)

    assert result.passed
    assert result.details["aggrescan3d"]["status"] == "ok"
    assert result.details["aggrescan3d"]["residue_count"] == len(SEQUENCE)
    assert len(tnp_output) == 1


@pytest.mark.parametrize("tnp_output", [synthetic_model()], indirect=True, ids=["complete-model"])
@pytest.mark.parametrize("endpoint", ["analyze", "tnp-profile", "analyze-batch"])
def test_existing_api_routes_include_native_scores(
    monkeypatch, tnp_output, native_config, endpoint
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from metanano.config import AsyncConfig, DevelopabilityConfig, GPUSchedulerConfig
    from metanano.routes import developability_routes
    from metanano.services.async_manager import AsyncServiceManager
    from metanano.services.developability_service import DevelopabilityService

    manager = AsyncServiceManager(
        AsyncConfig(gpu_scheduler=GPUSchedulerConfig(enabled=False))
    )
    service = DevelopabilityService(
        DevelopabilityConfig(aggrescan3d=native_config), manager,
    )
    monkeypatch.setattr(developability_routes, "_service", service)
    app = FastAPI()
    app.include_router(developability_routes.router)
    body = {"sequences": [SEQUENCE, SEQUENCE]} if endpoint == "analyze-batch" else {"sequence": SEQUENCE}
    with TestClient(app) as client:
        response = client.post(f"/developability/{endpoint}", json=body)

    assert response.status_code == 200, response.text
    data = response.json()
    results = data["results"] if endpoint == "analyze-batch" else [data]
    for result in results:
        assert result["aggrescan3d"]["status"] == "ok", result
        assert result["aggrescan3d"]["citation_doi"] == "10.1093/nar/gkv359"
        assert result["aggrescan3d"]["residue_count"] == len(SEQUENCE)
    assert len(tnp_output) == len(results)


@pytest.mark.parametrize(
    "sequence,tnp_output,expected_pass",
    [("G" * 50, synthetic_model("G" * 50), True), ("A" * 50, synthetic_model("A" * 50), False)],
    indirect=["tnp_output"], ids=["passing-glycine", "rejected-alanine"],
)
def test_sync_pipeline_enforces_native_filter(
    monkeypatch, tnp_output, native_config, sequence, expected_pass,
):
    from metanano.config import Config, DevelopabilityConfig
    from metanano.models.filter_result import FilterResult
    from metanano.pipeline import ValidationPipeline

    pipeline = ValidationPipeline(Config(developability=DevelopabilityConfig(aggrescan3d=native_config)))
    for validator in (pipeline._diversity_validator, pipeline._nativeness_validator):
        monkeypatch.setattr(validator, "validate", lambda *args, **kwargs: FilterResult(True))

    result = pipeline.validate(sequence)

    assert result.validation_status == ("Passed" if expected_pass else "Failed")
    assert result.failed_filters == ([] if expected_pass else ["Developability"])
    assert result.details["developability"]["aggrescan3d"]["passed"] == expected_pass
    assert len(tnp_output) == 1


@pytest.mark.parametrize(
    "sequence,tnp_output,expected_pass",
    [("G" * 50, synthetic_model("G" * 50), True), ("A" * 50, synthetic_model("A" * 50), False)],
    indirect=["tnp_output"], ids=["passing-glycine", "rejected-alanine"],
)
def test_application_developability_route_enforces_a3d(
    monkeypatch, tnp_output, native_config, sequence, expected_pass,
):
    from fastapi.testclient import TestClient
    from metanano.app import create_app
    from metanano.config import AsyncConfig, DevelopabilityConfig, GPUSchedulerConfig
    from metanano.routes import developability_routes
    from metanano.services import DevelopabilityService
    from metanano.services.async_manager import AsyncServiceManager

    manager = AsyncServiceManager(AsyncConfig(gpu_scheduler=GPUSchedulerConfig(enabled=False)))
    developability = DevelopabilityService(
        DevelopabilityConfig(aggrescan3d=native_config), manager,
    )
    monkeypatch.setattr(developability_routes, "_service", developability)
    app = create_app()
    assert "/developability/analyze" in app.openapi()["paths"]
    with TestClient(app) as client:
        response = client.post("/developability/analyze", json={"sequence": sequence})

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["passed"] == expected_pass
    assert result["aggrescan3d"]["passed"] == expected_pass
    assert result["aggrescan3d"]["status"] == "ok"
    assert len(result["aggrescan3d"]["checks"]) == 2
    assert len(tnp_output) == 1


@pytest.mark.parametrize("enabled", [True, False], ids=["unavailable-scorer", "disabled"])
@pytest.mark.parametrize("tnp_output", [synthetic_model()], indirect=True, ids=["complete-model"])
@pytest.mark.asyncio
async def test_async_pipeline_distinguishes_disabled_filter_and_scoring_error(
    monkeypatch, tnp_output, enabled,
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from metanano.config import Aggrescan3DConfig, AsyncConfig, Config, DevelopabilityConfig, GPUSchedulerConfig
    from metanano.pipeline import ValidationPipeline
    from metanano.services.async_manager import AsyncServiceManager

    async_config = AsyncConfig(gpu_scheduler=GPUSchedulerConfig(enabled=False))
    pipeline = ValidationPipeline(
        Config(
            async_config=async_config,
            developability=DevelopabilityConfig(
                aggrescan3d=Aggrescan3DConfig(enabled=enabled, executable="/unavailable/aggrescan3d-rs"),
            ),
        ),
        AsyncServiceManager(async_config),
    )
    for getter in ("_get_diversity_service", "_get_nativeness_service"):
        service = SimpleNamespace(analyze_async=AsyncMock(return_value={"passed": True}))
        monkeypatch.setattr(pipeline, getter, lambda service=service: service)
    result = await pipeline.validate_async(SEQUENCE)

    assert result.validation_status == ("Failed" if enabled else "Passed")
    assert result.failed_filters == (["Developability"] if enabled else [])
    assert result.details["developability"]["surface_hydrophobic_patches"] == 100.0
    if enabled:
        assert result.details["developability"]["aggrescan3d"]["status"] == "error"
        assert not result.details["developability"]["aggrescan3d"]["passed"]
    else:
        assert "aggrescan3d" not in result.details
        assert "aggrescan3d" not in result.details["developability"]
    assert len(tnp_output) == 1


@pytest.mark.asyncio
async def test_pipeline_honors_early_exit(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from metanano.config import AsyncConfig, Config, GPUSchedulerConfig
    from metanano.pipeline import ValidationPipeline
    from metanano.services.async_manager import AsyncServiceManager

    async_config = AsyncConfig(gpu_scheduler=GPUSchedulerConfig(enabled=False))
    pipeline = ValidationPipeline(Config(async_config=async_config), AsyncServiceManager(async_config))
    diversity = SimpleNamespace(analyze_async=AsyncMock(return_value={"passed": False}))
    nativeness = SimpleNamespace(analyze_async=AsyncMock(return_value={"passed": True}))
    developability = SimpleNamespace(
        analyze_async=AsyncMock(return_value={"passed": True}),
        compute_tnp_profile_async=AsyncMock(),
    )
    monkeypatch.setattr(pipeline, "_get_diversity_service", lambda: diversity)
    monkeypatch.setattr(pipeline, "_get_nativeness_service", lambda: nativeness)
    monkeypatch.setattr(pipeline, "_get_developability_service", lambda: developability)

    result = await pipeline.validate_async(SEQUENCE)
    assert result.failed_filters == ["Diversity"]
    nativeness.analyze_async.assert_not_awaited()
    developability.analyze_async.assert_not_awaited()

    developability.compute_tnp_profile_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_a3d_profile_fails_developability_without_refolding(monkeypatch):
    from unittest.mock import AsyncMock
    from metanano.config import AsyncConfig, DevelopabilityConfig, GPUSchedulerConfig
    from metanano.services import DevelopabilityService
    from metanano.services.async_manager import AsyncServiceManager

    service = DevelopabilityService(
        DevelopabilityConfig(),
        AsyncServiceManager(AsyncConfig(gpu_scheduler=GPUSchedulerConfig(enabled=False))),
    )
    compute = AsyncMock(return_value={
        "total_cdr_length": 30,
        "cdr3_length": 10,
        "cdr3_compactness": 1.0,
        "surface_hydrophobic_patches": 100.0,
        "positive_charge_patches": 0.5,
        "negative_charge_patches": 0.5,
    })
    monkeypatch.setattr(service, "compute_tnp_profile_async", compute)
    result = await service.analyze_async(SEQUENCE)

    assert not result["passed"]
    assert result["aggrescan3d"]["status"] == "error"
    assert result["surface_hydrophobic_patches"] == 100.0
    compute.assert_awaited_once_with(SEQUENCE)


def test_environment_enables_scoring_and_validates_flag(monkeypatch):
    from pydantic import ValidationError
    from metanano.config import Aggrescan3DConfig

    monkeypatch.setenv("AGGRESCAN3D_ENABLED", "true")
    monkeypatch.setenv("AGGRESCAN3D_EXECUTABLE", "custom-a3d")
    config = Aggrescan3DConfig()
    assert config.enabled
    assert config.executable == "custom-a3d"
    monkeypatch.setenv("AGGRESCAN3D_ENABLED", "invalid")
    with pytest.raises(ValidationError):
        Aggrescan3DConfig()


@pytest.mark.parametrize(
    "sequence,tnp_output,expected_pass",
    [("G" * 50, synthetic_model("G" * 50), True), ("A" * 50, synthetic_model("A" * 50), False)],
    indirect=["tnp_output"], ids=["passing-glycine", "rejected-alanine"],
)
@pytest.mark.parametrize("endpoint", ["", "/batch"])
def test_validation_routes_enforce_registered_native_filter(
    monkeypatch, tnp_output, native_config, endpoint, sequence, expected_pass
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from metanano.config import AsyncConfig, Config, DevelopabilityConfig, GPUSchedulerConfig
    from metanano.pipeline import ValidationPipeline
    from metanano.routes import validation_routes
    from metanano.services.async_manager import AsyncServiceManager

    async_config = AsyncConfig(gpu_scheduler=GPUSchedulerConfig(enabled=False))
    pipeline = ValidationPipeline(
        Config(
            developability=DevelopabilityConfig(aggrescan3d=native_config),
            async_config=async_config,
        ),
        AsyncServiceManager(async_config),
    )
    for getter in ("_get_diversity_service", "_get_nativeness_service"):
        service = SimpleNamespace(analyze_async=AsyncMock(return_value={"passed": True}))
        monkeypatch.setattr(pipeline, getter, lambda service=service: service)
    monkeypatch.setattr(validation_routes, "_pipeline", pipeline)
    app = FastAPI()
    app.include_router(validation_routes.router)
    body = {"sequences": [sequence, sequence]} if endpoint else {"sequence": sequence}
    with TestClient(app) as client:
        response = client.post(f"/validate{endpoint}", json=body)

    assert response.status_code == 200, response.text
    data = response.json()
    results = data["results"] if endpoint else [data]
    for result in results:
        assert result["validation_status"] == ("Passed" if expected_pass else "Failed")
        assert result["failed_filters"] == ([] if expected_pass else ["Developability"])
        assert result["details"]["developability"]["passed"] == expected_pass
        native = result["details"]["developability"]["aggrescan3d"]
        assert native["status"] == "ok", native
        assert native["passed"] == expected_pass
        assert native["checks"]["a3d_average"]["passed"] == expected_pass
        assert native["residue_count"] == 50
        assert native["sequence_hash"] == hashlib.sha256(sequence.encode()).hexdigest()
    assert len(tnp_output) == len(results)
