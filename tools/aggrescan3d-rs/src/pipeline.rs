//! Batch static workflow: frozen hash-keyed FASTA + isolated PDBs -> scored CSV and raw evidence.
use crate::{accessibility, parser, report, scoring, Result};
use std::{
    fs,
    path::{Path, PathBuf},
};

pub struct Options {
    pub fasta: PathBuf,
    pub structures: PathBuf,
    pub out: PathBuf,
    pub residue_out: PathBuf,
    pub freesasa: PathBuf,
    pub radius: f64,
    pub ph: Option<f64>,
}

fn one(hash: &str, sequence: &str, options: &Options, directory: &Path) -> Result<String> {
    let pdb = options.structures.join(format!("{hash}.pdb"));
    let bytes = fs::read(&pdb)?;
    let checksum = parser::sha256(&bytes);
    parser::validate_full_atoms(std::str::from_utf8(&bytes)?)?;
    let (normalized, mapping) = parser::normalize_pdb(std::str::from_utf8(&bytes)?)?;
    let normalized_checksum = parser::sha256(normalized.as_bytes());
    let normalized_pdb = directory.join("input-normalized.pdb");
    fs::write(&normalized_pdb, normalized)?;
    fs::write(directory.join("residue-mapping.csv"), mapping)?;
    let text = accessibility::run(&options.freesasa, &normalized_pdb, directory)?;
    let residues = parser::parse_sasa(&text)?;
    let observed: String = residues.iter().map(|r| r.aa).collect();
    if observed != sequence {
        return Err("Structure sequence differs from frozen FASTA".into());
    }
    let chains: std::collections::HashSet<_> = residues.iter().map(|r| &r.chain).collect();
    if chains.len() != 1 {
        return Err("Expected isolated single-chain structure".into());
    }
    let scores = scoring::score(&residues, options.radius, options.ph)?;
    let summary = scoring::summarize(&scores);
    report::residues(
        &directory.join("residue-scores.csv"),
        hash,
        &residues,
        &scores,
    )?;
    fs::write(directory.join("README.md"), format!("# Static Aggrescan3D evidence: {hash}\n\nInput is the exact isolated heavy-atom structure identified by source SHA256 `{checksum}`; normalized SHA256 `{normalized_checksum}`.\n\n- [input-normalized.pdb](input-normalized.pdb): original atom coordinates/chain with sequential residue numbers for FreeSASA2.0.1.\n- [residue-mapping.csv](residue-mapping.csv): original chain/number/insertion code to sequential index.\n- [sasa.out](sasa.out): pinned FreeSASA PDB/RSA output, NACCESS radii and Lee–Richards100 slices.\n- [freesasa.stderr](freesasa.stderr): surface-engine diagnostics.\n- [residue-scores.csv](residue-scores.csv): per-residue RSA and Rust A3D score, rounded and full precision.\n\nParent: [evidence guide](../README.md). Next: compare against upstream core and review protein summary; geometry is a computational model.\n"))?;
    let positive = scores.iter().filter(|&&s| s > 0.).count();
    Ok(format!("{hash},ok,{},{checksum},{},{},{},{},{},{},{positive},{},{},FreeSASA-2.0.1-NACCESS-LR100,static-no-minimization,,{normalized_checksum}\n",
        report::csv_cell(&pdb.display().to_string()), residues.len(), summary.total, summary.average, summary.maximum, summary.minimum, summary.positive_auc,
        options.radius, options.ph.map(|p| p.to_string()).unwrap_or_else(|| "default-scale".into())))
}

pub fn run(options: &Options) -> Result<()> {
    // Validate all options before creating outputs or invoking a surface tool.
    scoring::score(&[], options.radius, options.ph)?;
    accessibility::validate_version(&options.freesasa)?;
    let sequences = parser::parse_fasta(&fs::read_to_string(&options.fasta)?)?;
    fs::create_dir_all(&options.out)?;
    fs::create_dir_all(&options.residue_out)?;
    let mut text = "sequence_hash,status,source_pdb,input_structure_sha256,residue_count,a3d_total,a3d_average,a3d_maximum,a3d_minimum,a3d_positive_auc,positive_residue_count,radius_angstrom,ph_scale,surface_method,mode,error,normalized_structure_sha256\n".to_string();
    let mut failed = 0;
    let mut guide = "# Aggrescan3D raw evidence\n\nInputs are exact sequence hashes and isolated full-atom PDBs. Each hash folder preserves the sequential analysis copy, original numbering map, FreeSASA output/log and native Rust residue scores. The source models remain unchanged. Method: [Zambrano et al. (2015)](https://doi.org/10.1093/nar/gkv359), static scoring without additional minimization. Next: inspect the summary CSV and compare saved per-residue scores with the upstream parity harness.\n\n| Sequence hash | Evidence |\n| --- | --- |\n".to_string();
    for (index, (hash, seq)) in sequences.iter().enumerate() {
        let directory = options.residue_out.join(hash);
        fs::create_dir_all(&directory)?;
        guide.push_str(&format!(
            "| `{hash}` | [per-residue evidence]({hash}/README.md) |\n"
        ));
        eprintln!("[{}/{}] {}", index + 1, sequences.len(), hash);
        match one(hash, seq, options, &directory) {
            Ok(row) => text.push_str(&row),
            Err(error) => {
                failed += 1;
                fs::write(directory.join("README.md"), format!("# Aggrescan3D pending/error: {hash}\n\nThis sequence has no valid completed score from the current run: {error}. Partial raw files, if present, are diagnostic only. Next: resolve this failure and rerun. Parent: [A3D evidence](../README.md).\n"))?;
                text.push_str(&format!(
                    "{hash},error,{},,,,,,,,,,,,,{},\n",
                    report::csv_cell(
                        &options
                            .structures
                            .join(format!("{hash}.pdb"))
                            .display()
                            .to_string()
                    ),
                    report::csv_cell(&error.to_string())
                ));
                eprintln!("  error: {error}");
            }
        }
    }
    fs::write(options.out.join("aggrescan3d.csv"), text)?;
    fs::write(options.residue_out.join("README.md"), guide)?;
    if failed > 0 {
        return Err(crate::error::Error::Batch(format!(
            "{failed} structures failed; see aggrescan3d.csv"
        )));
    }
    Ok(())
}
