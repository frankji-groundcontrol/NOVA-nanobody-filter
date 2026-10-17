//! Boundary and scientific regression tests; see ../README.md and upstream parity fixtures.
use aggrescan3d_rs::{
    parser::Residue,
    scoring::{score, summarize},
};

fn res(aa: char, rsa: f64, x: f64) -> Residue {
    Residue {
        chain: "A".into(),
        number: format!("{x}"),
        aa,
        ca: [x, 0., 0.],
        rsa,
    }
}

#[test]
fn buried_centers_and_strict_radius_preserve_upstream_behavior() {
    let input = vec![res('I', 55., 0.), res('D', 9.9, 2.), res('I', 55., 10.)];
    let scores = score(&input, 10., None).unwrap();
    assert_eq!(scores[1], 0.);
    assert!((scores[0] - 1.9136 * 0.0599 * (0.0521_f64 * 55.).exp()).abs() < 1e-12);
    assert_eq!(scores[0], scores[2]);
}

#[test]
fn exposure_cap_and_nonzero_neighbor_effect() {
    let input = vec![res('I', 55., 0.), res('D', 80., 5.)];
    let scores = score(&input, 10., None).unwrap();
    let factor = 0.0599 * (0.0521_f64 * 55.).exp();
    let weight = 1.2915 * (-2.56_f64 * 0.5).exp();
    assert!((scores[0] - factor * (1.9136 - 1.7014 * weight)).abs() < 1e-12);
    assert!((scores[1] - factor * (-1.7014 + 1.9136 * weight)).abs() < 1e-12);
}

#[test]
fn summary_preserves_upstream_zero_extrema_and_zero_skipping_auc() {
    let result = summarize(&[-2., 0., -1.]);
    assert_eq!(result.total, -3.);
    assert_eq!(result.average, -1.);
    assert_eq!(result.maximum, 0.);
    assert_eq!(result.minimum, -2.);
    assert_eq!(result.positive_auc, 0.);
    assert_eq!(summarize(&[1., 0., 3.]).positive_auc, 2.);
}

#[test]
fn invalid_radius_ph_or_residue_rejected() {
    assert!(score(&[res('I', 55., 0.)], 0., None).is_err());
    assert!(score(&[res('I', 55., 0.)], 10., Some(0.)).is_err());
    assert!(score(&[res('X', 55., 0.)], 10., None).is_err());
}

#[test]
fn ph_zero_intrinsic_glycine_does_not_receive_neighbor_scores() {
    let residues = vec![res('G', 55., 0.), res('I', 55., 1.)];
    assert_eq!(score(&residues, 10., Some(7.)).unwrap()[0], 0.);
    assert_ne!(score(&residues, 10., None).unwrap()[0], 0.);
}

#[test]
fn upstream_all_amino_acid_fixture_matches_default_and_ph_scales() {
    let rows: Vec<_> = include_str!("../fixtures/upstream-scoring.csv")
        .lines()
        .skip(1)
        .map(|line| line.split(',').collect::<Vec<_>>())
        .collect();
    for batch in rows.chunks(20) {
        let radius = batch[0][0].parse().unwrap();
        let ph = if batch[0][1] == "default" {
            None
        } else {
            Some(batch[0][1].parse().unwrap())
        };
        let residues: Vec<_> = batch
            .iter()
            .enumerate()
            .map(|(i, row)| Residue {
                chain: "A".into(),
                number: (i + 1).to_string(),
                aa: row[2].chars().next().unwrap(),
                rsa: row[3].parse().unwrap(),
                ca: [
                    row[4].parse().unwrap(),
                    row[5].parse().unwrap(),
                    row[6].parse().unwrap(),
                ],
            })
            .collect();
        for (actual, row) in score(&residues, radius, ph).unwrap().iter().zip(batch) {
            let expected: f64 = row[7].trim().parse().unwrap();
            assert!(
                (actual - expected).abs() < 1e-12,
                "residue {} pH {} radius {}",
                row[2],
                row[1],
                row[0]
            );
        }
    }
}
