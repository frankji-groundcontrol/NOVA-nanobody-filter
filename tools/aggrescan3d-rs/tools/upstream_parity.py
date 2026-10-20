"""Run the unmodified pinned upstream A3D core on saved SASA; compare Rust residue scores.

Inputs: upstream checkout, Rust summary and residue output. Output: parity CSV.
Also generates a small all-amino-acid regression fixture for tests/scoring.rs.
The only import adaptation is explicit file loading for Python 2 absolute imports;
no source rewrites or substitute scoring formulas are used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
from pathlib import Path
import sys


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture(core, matrix: dict[str, str], target: Path) -> None:
    three = "ALA ARG ASN ASP CYS GLU GLN GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL".split()
    with target.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["radius", "ph", "aa", "rsa", "x", "y", "z", "expected_score"])
        for radius in [5, 10]:
            for ph in [None, 4, 7, 10]:
                protein = core.Protein("fixture", [], ".", radius)
                for i, name in enumerate(three):
                    coords = (i * 3 % 17, i * 7 % 13, i * 11 % 19)
                    rsa = [0, 9.9, 10, 54.9, 55, 55.1, 80][i % 7]
                    residue = core.Residue("A", str(i + 1), name, coords, 0, matrix, ph)
                    residue.set_rsa(rsa)
                    protein.add_residue(residue)
                protein.calc_agg_fin()
                for i, residue in enumerate(protein.residues):
                    rsa = [0, 9.9, 10, 54.9, 55, 55.1, 80][i % 7]
                    writer.writerow([radius, "default" if ph is None else ph, residue.resn, rsa, *residue.coords, repr(residue.agg_fin)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--residue-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    source = args.upstream / "aggrescan"
    for relative, expected in {
        "aggrescan_3d.py": "f707dbc94e8d75c101fa62b1f9305b6fd2f120faa3bd26208925ccf382912061",
        "data/matrices/aggrescan.mat": "f60933b62ab86cbf0760666808031047ca035cc6bb762070c2aa4f1dd0039a5f",
    }.items():
        actual = hashlib.sha256((source / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"Upstream reference bytes differ from pinned source: {relative}")
    load("logger", source / "logger.py")
    core = load("aggrescan_3d", source / "aggrescan_3d.py")
    matrix = core.parse_matrix(str(source / "data/matrices/aggrescan.mat"))
    if args.fixture:
        fixture(core, matrix, args.fixture)
    if not args.summary:
        return
    fields = ["sequence_hash", "status", "residue_count", "max_abs_residue_difference", "summary_4dp_equal", "source_checksum_matches", "normalized_checksum_matches", "atom_identity_geometry_equal", "upstream_commit"]
    reports = []
    for row in csv.DictReader(args.summary.open()):
        if row["status"] != "ok":
            reports.append(dict(sequence_hash=row["sequence_hash"], status="not_scored"))
            continue
        directory = args.residue_dir / row["sequence_hash"]
        original = Path(row["source_pdb"]).read_bytes()
        normalized = (directory / "input-normalized.pdb").read_bytes()
        source_checksum_matches = hashlib.sha256(original).hexdigest() == row["input_structure_sha256"]
        normalized_checksum_matches = hashlib.sha256(normalized).hexdigest() == row["normalized_structure_sha256"]
        original_atoms = [line[:22] + line[27:] for line in original.decode().splitlines() if line.startswith("ATOM ")]
        normalized_atoms = [line[:22] + line[27:] for line in normalized.decode().splitlines() if line.startswith("ATOM ")]
        atom_identity_geometry_equal = original_atoms == normalized_atoms
        ph = None if row["ph_scale"] == "default-scale" else float(row["ph_scale"])
        protein = core.parse_freesasa(row["sequence_hash"], str(directory), "sasa.out", matrix, float(row["radius_angstrom"]), ph)
        protein.calc_agg_fin()
        rust = list(csv.DictReader((directory / "residue-scores.csv").open()))
        assert len(rust) == len(protein.residues) == int(row["residue_count"])
        differences = []
        for observed, expected in zip(rust, protein.residues):
            assert (observed["chain"], observed["residue"], observed["residue_name"]) == (expected.chain, expected.resi, expected.resn)
            differences.append(abs(float(observed["score_full_precision"]) - expected.agg_fin))
        upstream_summary = [float(x) for x in protein.short_summary().split()[1:]]
        rust_summary = [float(f"{float(row[key]):.4f}") for key in ["a3d_total", "a3d_average", "a3d_maximum", "a3d_minimum", "a3d_positive_auc"]]
        equal = upstream_summary == rust_summary
        difference = max(differences)
        passed = difference < 1e-10 and equal and source_checksum_matches and normalized_checksum_matches and atom_identity_geometry_equal
        reports.append(dict(sequence_hash=row["sequence_hash"], status="pass" if passed else "FAIL", residue_count=len(rust), max_abs_residue_difference=difference, summary_4dp_equal=equal, source_checksum_matches=source_checksum_matches, normalized_checksum_matches=normalized_checksum_matches, atom_identity_geometry_equal=atom_identity_geometry_equal, upstream_commit="afd8a9da1f44f7b702aceb5a80abe67dde74ca00"))
    with args.out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reports)
    print(f"Upstream parity: {sum(r['status'] == 'pass' for r in reports)}/{len(reports)} structures; {sum(int(r.get('residue_count', 0)) for r in reports)} residues")
    if any(r["status"] != "pass" for r in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
