//! CSV output of sequence-keyed protein and per-residue results; consumed by profiling joins.
use crate::{parser::Residue, Result};
use std::{fs, path::Path};

pub fn csv_cell(value: &str) -> String {
    if value.contains([',', '"', '\n', '\r']) {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.into()
    }
}

pub fn residues(path: &Path, hash: &str, residues: &[Residue], scores: &[f64]) -> Result<()> {
    let mut text =
        "sequence_hash,chain,residue,residue_name,rsa_percent,score,score_full_precision\n"
            .to_string();
    for (r, s) in residues.iter().zip(scores) {
        text.push_str(&format!(
            "{},{},{},{},{:.1},{:.4},{}\n",
            hash,
            csv_cell(&r.chain),
            csv_cell(&r.number),
            r.aa,
            r.rsa,
            s,
            s
        ));
    }
    fs::write(path, text)?;
    Ok(())
}
