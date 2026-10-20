//! Input integrity regressions for the static A3D accessibility bridge.
use aggrescan3d_rs::parser::{normalize_pdb, parse_fasta, sha256, validate_full_atoms};

#[test]
fn insertion_codes_are_separated_without_moving_atoms() {
    let pdb = "ATOM      1  CA  LEU H 111      -1.000   2.000   3.000  1.00 20.00           C\nATOM      2  CB  LEU H 111      -2.000   2.000   3.000  1.00 20.00           C\nATOM      3  CA  VAL H 111A      1.000   2.000   3.000  1.00 20.00           C\n";
    let (normalized, mapping) = normalize_pdb(pdb).unwrap();
    let rows: Vec<_> = normalized
        .lines()
        .filter(|s| s.starts_with("ATOM"))
        .collect();
    assert_eq!(&rows[0][22..27], "   1 ");
    assert_eq!(&rows[1][22..27], "   1 ");
    assert_eq!(&rows[2][22..27], "   2 ");
    assert_eq!(&rows[2][30..54], &pdb.lines().nth(2).unwrap()[30..54]);
    assert!(mapping.contains("H,111,A,2"));
}

#[test]
fn ca_only_structure_is_rejected_before_sasa() {
    let pdb = "ATOM      1  CA  LEU H 111      -1.000   2.000   3.000  1.00 20.00           C\n";
    assert!(validate_full_atoms(pdb)
        .unwrap_err()
        .to_string()
        .contains("Missing heavy atoms"));
}

#[test]
fn fasta_identity_is_verified() {
    let hash = sha256(b"ACDE");
    assert_eq!(
        parse_fasta(&format!(">{hash}|sample\nACDE\n")).unwrap()[0].1,
        "ACDE"
    );
    assert!(parse_fasta(&format!(">{hash}\nACDF\n")).is_err());
}
