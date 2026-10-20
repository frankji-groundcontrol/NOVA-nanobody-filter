//! Aggrescan3D static scoring port from aggrescan_3d.py at afd8a9d; see LICENSE.
//! Input: CA coordinates + NACCESS-relative ASA (%); output: scores and summary.
use crate::{parser::Residue, Result};

pub fn intrinsic(aa: char, ph: Option<f64>) -> Result<f64> {
    let index = "IFVLYWMCATSPGKHQRNED"
        .find(aa)
        .ok_or("Unsupported amino acid")?;
    let base = [
        1.9136, 1.8456, 1.6856, 1.4716, 1.2506, 1.1286, 1.0016, 0.6956, 0.0556, -0.0674, -0.2024,
        -0.2424, -0.4434, -1.6164, -0.9414, -1.1394, -1.7534, -1.2104, -1.7304, -1.7014,
    ][index];
    let Some(ph) = ph else { return Ok(base) };
    let data: Option<(f64, f64, f64, f64)> = match aa {
        'R' => Some((12.5, 0.857546950885663, -3.66, -7.38)),
        'D' => Some((3.5, 0.622376926398327, -3.18, -8.54)),
        'E' => Some((4.2, 0.940369170156725, -3.79, -6.2)),
        'H' => Some((6.6, 0.812212007706225, -4.67, -5.97)),
        'K' => Some((10.5, 0.9093172437, -2.19, -6.81)),
        _ => None,
    };
    if let Some((pka, r, pn, pi)) = data {
        let exponent = 10_f64.powf((pka - ph).abs());
        Ok(
            (10_f64.powf(pn) + 10_f64.powf(pi) * exponent).log10() * r - (1. + exponent).log10()
                + 3.13,
        )
    } else {
        let index = "ANCQGILMFPSTWYV".find(aa).ok_or("Unsupported pH residue")?;
        Ok([
            0.66, -0.84, 1.66, -0.87, 0., 2.75, 1.77, 1.30, 3.99, 1.69, -0.99, 0.12, 3.29, 1.33,
            1.45,
        ][index])
    }
}

pub fn score(residues: &[Residue], radius: f64, ph: Option<f64>) -> Result<Vec<f64>> {
    if !radius.is_finite() || radius <= 0. {
        return Err("Radius must be finite and positive".into());
    }
    if ph.is_some_and(|p| !p.is_finite() || p <= 0. || p > 14.) {
        return Err("pH must be in (0,14]".into());
    }
    let surface: Vec<f64> = residues
        .iter()
        .map(|res| {
            let scale = intrinsic(res.aa, ph)?;
            if !res.rsa.is_finite() || res.rsa < 0. {
                return Err("Invalid RSA".into());
            }
            Ok(if res.rsa < 10. {
                0.
            } else {
                scale * 0.0599 * (0.0521 * res.rsa.min(55.)).exp()
            })
        })
        .collect::<Result<_>>()?;
    Ok(residues
        .iter()
        .enumerate()
        .map(|(i, central)| {
            let mut sum = 0.;
            if surface[i] != 0. {
                for (j, neighbor) in residues.iter().enumerate() {
                    let distance = central
                        .ca
                        .iter()
                        .zip(neighbor.ca)
                        .map(|(a, b)| (a - b).powi(2))
                        .sum::<f64>()
                        .sqrt();
                    if distance < radius && distance != 0. {
                        sum += surface[j] * 1.2915 * (-2.56 / radius * distance).exp();
                    }
                }
            }
            surface[i] + sum
        })
        .collect())
}

#[derive(Debug)]
pub struct Summary {
    pub total: f64,
    pub average: f64,
    pub maximum: f64,
    pub minimum: f64,
    pub positive_auc: f64,
}

/// Upstream initializes extrema at zero and skips zero scores in AUC integration.
pub fn summarize(scores: &[f64]) -> Summary {
    let mut summary = Summary {
        total: 0.,
        average: 0.,
        maximum: 0.,
        minimum: 0.,
        positive_auc: 0.,
    };
    let mut previous = 0.;
    for &value in scores {
        summary.total += value;
        summary.maximum = summary.maximum.max(value);
        summary.minimum = summary.minimum.min(value);
        if value != 0. {
            if previous != 0. {
                summary.positive_auc += ((value + previous) / 2.).max(0.);
            }
            previous = value;
        }
    }
    summary.average = summary.total / scores.len() as f64;
    summary
}
