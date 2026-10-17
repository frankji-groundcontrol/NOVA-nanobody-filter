//! External FreeSASA bridge. The scientific A3D scoring itself lives in scoring.rs.
use crate::{error::Error, Result};
use std::{fs, path::Path, process::Command};

pub fn validate_version(binary: &Path) -> Result<()> {
    let output = Command::new(binary).arg("--version").output()?;
    let text = format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    if !output.status.success() || !text.contains("FreeSASA 2.0.1") {
        return Err(Error::External(format!(
            "Require pinned FreeSASA 2.0.1 for reproducible RSA, got: {text}"
        )));
    }
    Ok(())
}

pub fn run(binary: &Path, pdb: &Path, directory: &Path) -> Result<String> {
    let output = Command::new(binary)
        .args(["--resolution", "100"])
        .arg(pdb)
        .args(["--radii", "naccess", "--format", "pdb", "--format", "rsa"])
        .output()?;
    fs::write(directory.join("freesasa.stderr"), &output.stderr)?;
    if !output.status.success() {
        return Err(Error::External(format!(
            "FreeSASA failed: {}",
            String::from_utf8_lossy(&output.stderr)
        )));
    }
    let text = String::from_utf8(output.stdout)?;
    fs::write(directory.join("sasa.out"), &text)?;
    Ok(text)
}
