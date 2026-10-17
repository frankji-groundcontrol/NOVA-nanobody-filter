use aggrescan3d_rs::metrics::{summarize_region, summarize_vhh};

#[test]
fn whole_vhh_preserves_hotspots_without_signed_cancellation() {
    let metrics = summarize_vhh(&[-8., 4., 0., 2.]).unwrap();
    assert_eq!(metrics.residue_count, 4);
    assert_eq!(metrics.a3d_average, -0.5);
    assert_eq!(metrics.a3d_maximum, 4.);
    assert_eq!(metrics.positive_residue_count, 2);
    assert_eq!(metrics.positive_fraction, 0.5);
    assert_eq!(metrics.positive_score_sum, 6.);
    assert_eq!(metrics.positive_burden, 1.5);
}

#[test]
fn selected_region_uses_its_own_residue_count() {
    let scores = [-8., 4., 0., 2.];
    let region = summarize_region(&scores, &[false, true, true, false]).unwrap();
    assert_eq!(region.residue_count, 2);
    assert_eq!(region.a3d_average, 2.);
    assert_eq!(region.a3d_maximum, 4.);
    assert_eq!(region.positive_residue_count, 1);
    assert_eq!(region.positive_fraction, 0.5);
    assert_eq!(region.positive_score_sum, 4.);
    assert_eq!(region.positive_burden, 2.);
    assert_eq!(scores, [-8., 4., 0., 2.]);
}

#[test]
fn full_region_matches_whole_vhh() {
    let scores = [-2., 1., 0., 3.];
    assert_eq!(
        summarize_region(&scores, &[true; 4]).unwrap(),
        summarize_vhh(&scores).unwrap()
    );
}

#[test]
fn negative_and_zero_only_sets_have_no_positive_burden() {
    for scores in [&[-2., -4.][..], &[0., 0.][..]] {
        let metrics = summarize_vhh(scores).unwrap();
        assert_eq!(metrics.a3d_maximum, 0.);
        assert_eq!(metrics.positive_residue_count, 0);
        assert_eq!(metrics.positive_fraction, 0.);
        assert_eq!(metrics.positive_score_sum, 0.);
        assert_eq!(metrics.positive_burden, 0.);
    }
}

#[test]
fn empty_non_finite_and_overflowing_scores_are_rejected() {
    for scores in [
        vec![],
        vec![f64::NAN],
        vec![f64::INFINITY],
        vec![f64::NEG_INFINITY],
        vec![f64::MAX, f64::MAX],
    ] {
        assert_eq!(summarize_vhh(&scores).unwrap_err().exit_code(), 2);
    }
}

#[test]
fn invalid_masks_and_non_finite_context_are_rejected() {
    assert!(summarize_region(&[1., 2.], &[true]).is_err());
    assert!(summarize_region(&[1.], &[true, false]).is_err());
    assert!(summarize_region(&[1., 2.], &[false, false]).is_err());
    assert!(summarize_region(&[], &[]).is_err());
    assert!(summarize_region(&[1., f64::NAN], &[true, false]).is_err());
}
