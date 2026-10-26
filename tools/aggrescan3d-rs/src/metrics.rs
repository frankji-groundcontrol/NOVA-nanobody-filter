//! Whole-VHH and regional reporting over scores from [`crate::scoring::score`].
//! Uses [`crate::scoring::summarize`] for upstream mean and zero-anchored maximum.
//! Region masks select residue centers in the original full-VHH score order.
//! Method and interpretation: ../README.md; boundary checks: ../tests/metrics.rs.

use crate::{scoring, Result};

#[derive(Debug, PartialEq)]
pub struct VhhMetrics {
    pub residue_count: usize,
    pub a3d_average: f64,
    pub a3d_maximum: f64,
    pub positive_residue_count: usize,
    pub positive_fraction: f64,
    pub positive_score_sum: f64,
    pub positive_burden: f64,
}

fn validate_scores(scores: &[f64]) -> Result<()> {
    if scores.is_empty() {
        return Err("Cannot summarize an empty residue set".into());
    }
    if scores.iter().any(|score| !score.is_finite()) {
        return Err("Residue scores must be finite".into());
    }
    Ok(())
}

/// Summarize precomputed full-VHH scores, including zero-valued buried residues.
/// Positive burden is the sum of positive scores divided by the residue count.
/// Empty/non-finite inputs and overflowing aggregates return an input error.
///
/// ```
/// use aggrescan3d_rs::metrics::summarize_vhh;
/// let metrics = summarize_vhh(&[-8.0, 4.0, 0.0, 2.0]).unwrap();
/// assert_eq!(metrics.a3d_average, -0.5);
/// assert_eq!(metrics.positive_burden, 1.5);
/// ```
pub fn summarize_vhh(scores: &[f64]) -> Result<VhhMetrics> {
    validate_scores(scores)?;
    let upstream = scoring::summarize(scores);
    let positive_residue_count = scores.iter().filter(|&&score| score > 0.).count();
    let positive_score_sum: f64 = scores.iter().copied().filter(|&score| score > 0.).sum();
    if !upstream.average.is_finite() || !positive_score_sum.is_finite() {
        return Err("Score aggregation overflowed; expected finite summaries".into());
    }
    Ok(VhhMetrics {
        residue_count: scores.len(),
        a3d_average: upstream.average,
        a3d_maximum: upstream.maximum,
        positive_residue_count,
        positive_fraction: positive_residue_count as f64 / scores.len() as f64,
        positive_score_sum,
        positive_burden: positive_score_sum / scores.len() as f64,
    })
}

/// Summarize selected residue centers without recalculating their full-VHH scores.
/// The mask must match score order and length; caller-supplied annotations define
/// CDRs, framework regions or custom interfaces. The region must be nonempty.
///
/// ```
/// use aggrescan3d_rs::metrics::summarize_region;
/// let metrics = summarize_region(&[-8.0, 4.0, 0.0, 2.0],
///                                &[false, true, true, false]).unwrap();
/// assert_eq!(metrics.residue_count, 2);
/// assert_eq!(metrics.positive_burden, 2.0);
/// ```
pub fn summarize_region(scores: &[f64], region_mask: &[bool]) -> Result<VhhMetrics> {
    validate_scores(scores)?;
    if scores.len() != region_mask.len() {
        return Err("Region mask length must match the full-VHH score count".into());
    }
    let selected: Vec<f64> = scores
        .iter()
        .zip(region_mask)
        .filter_map(|(&score, &include)| include.then_some(score))
        .collect();
    summarize_vhh(&selected)
}
