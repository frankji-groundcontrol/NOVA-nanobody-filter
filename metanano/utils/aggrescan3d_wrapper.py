"""Run the native static scorer on TNP's existing isolated heavy-atom model.

Inputs are an exact amino-acid sequence and a PDB path. Results contain native
summary metrics, sequence/structure hashes and the original method citation.
See docs/usage/aggrescan3d-rust.md, tools/aggrescan3d-rs/README.md and
metanano/tests/utils/test_aggrescan3d_integration.py.
"""

import csv
import hashlib
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict


class Aggrescan3DWrapper:
    """Bridge TNP structure output to the pinned Rust/FreeSASA static workflow."""

    def __init__(
        self,
        executable: str = "aggrescan3d-rs",
        freesasa_executable: str = "freesasa",
    ) -> None:
        self.executable = executable
        self.freesasa_executable = freesasa_executable

    def profile(self, sequence: str, structure: Path) -> Dict[str, Any]:
        """Return scored metrics or an explicit error; never refold."""
        sequence_hash = hashlib.sha256(sequence.encode("utf-8")).hexdigest()
        result: Dict[str, Any] = {
            "status": "error",
            "sequence_hash": sequence_hash,
            "citation_doi": "10.1093/nar/gkv359",
        }
        try:
            if not sequence or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
                raise ValueError("Expected an uppercase sequence of standard amino acids")
            with tempfile.TemporaryDirectory(prefix="nova-a3d-") as temporary:
                directory = Path(temporary)
                structures = directory / "structures"
                structures.mkdir()
                pdb = structures / f"{sequence_hash}.pdb"
                shutil.copyfile(structure, pdb)
                structure_hash = hashlib.sha256(pdb.read_bytes()).hexdigest()
                fasta = directory / "sequence.fasta"
                fasta.write_text(f">{sequence_hash}\n{sequence}\n", encoding="utf-8")
                summary = directory / "summary"
                completed = subprocess.run(
                    [
                        self.executable,
                        "--fasta", str(fasta),
                        "--structures", str(structures),
                        "--out", str(summary),
                        "--residue-out", str(directory / "residues"),
                        "--freesasa", self.freesasa_executable,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                output = summary / "aggrescan3d.csv"
                rows = []
                if output.is_file():
                    with output.open(newline="", encoding="utf-8") as handle:
                        rows = list(csv.DictReader(handle))
                if completed.returncode != 0:
                    detail = rows[0].get("error") if len(rows) == 1 else None
                    raise ValueError(
                        detail or completed.stderr.strip()[-1000:]
                        or f"Native scorer exited with code {completed.returncode}"
                    )
                if len(rows) != 1 or rows[0].get("status") != "ok":
                    raise ValueError("Native scorer did not return one successful summary")
                row = rows[0]
                if row["sequence_hash"] != sequence_hash:
                    raise ValueError("Native summary sequence hash does not match input")
                if row["input_structure_sha256"] != structure_hash:
                    raise ValueError("Native summary structure hash does not match input")
                residue_count = int(row["residue_count"])
                positive_count = int(row["positive_residue_count"])
                if residue_count != len(sequence) or not 0 <= positive_count <= residue_count:
                    raise ValueError("Native summary residue counts do not match input")
                metrics = {
                    key: float(row[key])
                    for key in (
                        "a3d_total", "a3d_average", "a3d_maximum",
                        "a3d_minimum", "a3d_positive_auc",
                    )
                }
                if not all(math.isfinite(value) for value in metrics.values()):
                    raise ValueError("Native scorer returned a non-finite score")
                result.update(
                    status="ok",
                    input_structure_sha256=structure_hash,
                    normalized_structure_sha256=row["normalized_structure_sha256"],
                    residue_count=residue_count,
                    positive_residue_count=positive_count,
                    radius_angstrom=float(row["radius_angstrom"]),
                    ph_scale=row["ph_scale"],
                    surface_method=row["surface_method"],
                    mode=row["mode"],
                    **metrics,
                )
        except subprocess.TimeoutExpired:
            result["error"] = "Aggrescan3D scoring timed out after 60 seconds"
        except (OSError, ValueError, KeyError, csv.Error) as error:
            result["error"] = str(error)
        return result
