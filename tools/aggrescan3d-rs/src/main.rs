//! Thin CLI for the static pipeline; dynamic sampling/FoldX mutation are not implemented.
use aggrescan3d_rs::{
    pipeline::{self, Options},
    Result,
};
use std::{collections::HashMap, path::PathBuf};

fn main() {
    if let Err(error) = run() {
        eprintln!("aggrescan3d-rs: {error}");
        std::process::exit(error.exit_code());
    }
}
fn run() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let mut values = HashMap::new();
    while let Some(key) = args.next() {
        if key == "--help" || key == "-h" {
            println!("aggrescan3d-rs --fasta HASH_FASTA --structures PDB_DIR --out SUMMARY_DIR --residue-out BULK_DIR --freesasa BINARY [--radius 10] [--ph PH]\nStatic isolated-chain scoring only. Dynamic, mutation and FoldX minimization are unsupported.");
            return Ok(());
        }
        if ![
            "--fasta",
            "--structures",
            "--out",
            "--residue-out",
            "--freesasa",
            "--radius",
            "--ph",
        ]
        .contains(&key.as_str())
        {
            return Err(
                format!("Unsupported option {key}; only static scoring is implemented").into(),
            );
        }
        let value = args
            .next()
            .ok_or_else(|| format!("Missing value for {key}"))?;
        if values.insert(key.clone(), value).is_some() {
            return Err(format!("Duplicate option {key}").into());
        }
    }
    let path = |key: &str| -> Result<PathBuf> {
        values
            .get(key)
            .map(PathBuf::from)
            .ok_or_else(|| format!("Required option: {key}").into())
    };
    pipeline::run(&Options {
        fasta: path("--fasta")?,
        structures: path("--structures")?,
        out: path("--out")?,
        residue_out: path("--residue-out")?,
        freesasa: path("--freesasa")?,
        radius: values
            .get("--radius")
            .map(|s| s.parse())
            .transpose()?
            .unwrap_or(10.),
        ph: values.get("--ph").map(|s| s.parse()).transpose()?,
    })
}
