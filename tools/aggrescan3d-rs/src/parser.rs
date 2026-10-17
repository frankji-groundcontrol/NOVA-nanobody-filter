//! Parse FreeSASA PDB+RSA output and hash-keyed FASTA; feeds scoring and pipeline.
use crate::Result;
use sha2::{Digest, Sha256};
use std::collections::HashSet;

#[derive(Clone, Debug)]
pub struct Residue {
    pub chain: String,
    pub number: String,
    pub aa: char,
    pub ca: [f64; 3],
    pub rsa: f64,
}

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

/// Reject incomplete/CA-only structures before estimating solvent accessibility.
pub fn validate_full_atoms(text: &str) -> Result<()> {
    let mut residues: std::collections::HashMap<String, (char, HashSet<String>)> =
        std::collections::HashMap::new();
    for line in text.lines().filter(|line| line.starts_with("ATOM ")) {
        let atom = field(line, 12, 16)?.trim();
        let element = line.get(76..78).unwrap_or("").trim();
        if element == "H"
            || element == "D"
            || atom
                .trim_start_matches(|c: char| c.is_ascii_digit())
                .starts_with(['H', 'D'])
        {
            return Err("Hydrogen/deuterium input is unsupported; provide a heavy-atom structure to avoid silent atom loss".into());
        }
        let aa = one_letter(field(line, 17, 20)?)?;
        let id = field(line, 21, 27)?.to_string();
        let entry = residues
            .entry(id.clone())
            .or_insert_with(|| (aa, HashSet::new()));
        if entry.0 != aa || !entry.1.insert(atom.to_string()) {
            return Err(format!("Conflicting or duplicate atom in residue {id}").into());
        }
    }
    if residues.is_empty() {
        return Err("No standard ATOM residues".into());
    }
    for (id, (aa, atoms)) in residues {
        let side = match aa {
            'A' => "CB",
            'R' => "CB CG CD NE CZ NH1 NH2",
            'N' => "CB CG OD1 ND2",
            'D' => "CB CG OD1 OD2",
            'C' => "CB SG",
            'E' => "CB CG CD OE1 OE2",
            'Q' => "CB CG CD OE1 NE2",
            'G' => "",
            'H' => "CB CG ND1 CD2 CE1 NE2",
            'I' => "CB CG1 CG2 CD1",
            'L' => "CB CG CD1 CD2",
            'K' => "CB CG CD CE NZ",
            'M' => "CB CG SD CE",
            'F' => "CB CG CD1 CD2 CE1 CE2 CZ",
            'P' => "CB CG CD",
            'S' => "CB OG",
            'T' => "CB OG1 CG2",
            'W' => "CB CG CD1 CD2 NE1 CE2 CE3 CZ2 CZ3 CH2",
            'Y' => "CB CG CD1 CD2 CE1 CE2 CZ OH",
            'V' => "CB CG1 CG2",
            _ => unreachable!(),
        };
        let missing: Vec<_> = "N CA C O"
            .split_whitespace()
            .chain(side.split_whitespace())
            .filter(|name| !atoms.contains(*name))
            .collect();
        if !missing.is_empty() {
            return Err(format!(
                "Missing heavy atoms in residue {id} ({aa}): {}",
                missing.join(" ")
            )
            .into());
        }
    }
    Ok(())
}

/// FreeSASA 2.0.1 merges insertion codes; use a coordinate-identical sequential copy.
pub fn normalize_pdb(text: &str) -> Result<(String, String)> {
    let mut output = String::new();
    let mut mapping =
        "source_chain,source_residue_number,source_insertion_code,normalized_residue\n".to_string();
    let mut ids = std::collections::HashMap::new();
    let mut ca_ids = HashSet::new();
    let mut count = 0;
    for line in text.lines() {
        if line.starts_with("MODEL ") || line.starts_with("HETATM") {
            return Err("Multi-model and HETATM inputs are unsupported; prepare an isolated standard-AA model".into());
        }
        if !line.starts_with("ATOM ") {
            continue;
        }
        if !line.is_ascii() || line.len() < 54 {
            return Err("Truncated/non-ASCII PDB ATOM".into());
        }
        if field(line, 16, 17)? != " " {
            return Err("Alternate conformers are unsupported; select one conformation".into());
        }
        let key = (
            field(line, 21, 22)?.to_string(),
            field(line, 22, 27)?.trim().to_string(),
        );
        let new_id = *ids.entry(key.clone()).or_insert_with(|| {
            count += 1;
            mapping.push_str(&format!(
                "{},{},{},{}\n",
                key.0,
                line[22..26].trim(),
                line[26..27].trim(),
                count
            ));
            count
        });
        if new_id > 9999 {
            return Err("PDB residue numbering capacity exceeded".into());
        }
        if field(line, 12, 16)?.trim() == "CA" && !ca_ids.insert(key) {
            return Err("Duplicate CA atom".into());
        }
        output.push_str(&format!("{}{:>4} {}\n", &line[..22], new_id, &line[27..]));
    }
    if count == 0 || ca_ids.len() != count {
        return Err("Missing CA atoms or empty structure".into());
    }
    output.push_str("END\n");
    Ok((output, mapping))
}

pub fn one_letter(name: &str) -> Result<char> {
    let aa = match name.trim() {
        "ALA" => 'A',
        "ARG" => 'R',
        "ASN" => 'N',
        "ASP" => 'D',
        "CYS" => 'C',
        "GLU" => 'E',
        "GLN" => 'Q',
        "GLY" => 'G',
        "HIS" => 'H',
        "ILE" => 'I',
        "LEU" => 'L',
        "LYS" => 'K',
        "MET" => 'M',
        "PHE" => 'F',
        "PRO" => 'P',
        "SER" => 'S',
        "THR" => 'T',
        "TRP" => 'W',
        "TYR" => 'Y',
        "VAL" => 'V',
        _ => return Err(format!("Unsupported residue: {name}").into()),
    };
    Ok(aa)
}

fn field(line: &str, start: usize, end: usize) -> Result<&str> {
    line.get(start..end)
        .ok_or_else(|| format!("Truncated/non-ASCII PDB/RSA line: {line}").into())
}

/// Deliberately consumes upstream's rounded RSA text, not unrounded raw SASA.
pub fn parse_sasa(text: &str) -> Result<Vec<Residue>> {
    let mut residues: Vec<Residue> = Vec::new();
    let mut assigned = 0;
    let mut ids = HashSet::new();
    for line in text.lines() {
        if line.starts_with("ATOM ") && field(line, 12, 16)?.trim() == "CA" {
            let chain = field(line, 21, 22)?.replace(' ', "-");
            let number = field(line, 22, 29)?.trim().to_string();
            if !ids.insert((chain.clone(), number.clone())) {
                return Err(format!(
                    "Duplicate CA residue {chain}:{number}; select one model/alternate location"
                )
                .into());
            }
            let mut ca: [f64; 3] = [0.; 3];
            for (index, start) in [30, 38, 46].iter().enumerate() {
                ca[index] = field(line, *start, start + 8)?.trim().parse()?;
                if !ca[index].is_finite() {
                    return Err("Non-finite CA coordinate".into());
                }
            }
            residues.push(Residue {
                chain,
                number,
                aa: one_letter(field(line, 17, 20)?)?,
                ca,
                rsa: f64::NAN,
            });
        } else if line.starts_with("RES") {
            let residue = residues
                .get_mut(assigned)
                .ok_or("RSA row has no matching CA")?;
            let chain = field(line, 8, 9)?.replace(' ', "-");
            let aa = one_letter(field(line, 3, 8)?.trim())?;
            let number = field(line, 9, 16)?.trim();
            if residue.chain != chain || residue.aa != aa || residue.number != number {
                return Err(format!("CA/RSA identity mismatch at residue {}", assigned + 1).into());
            }
            residue.rsa = field(line, 22, 28)?.trim().parse()?;
            if !residue.rsa.is_finite() || residue.rsa < 0. {
                return Err("Invalid RSA".into());
            }
            assigned += 1;
        }
    }
    if residues.is_empty() || assigned != residues.len() {
        return Err("Empty or incomplete CA/RSA data".into());
    }
    Ok(residues)
}

pub fn parse_fasta(text: &str) -> Result<Vec<(String, String)>> {
    let mut rows: Vec<(String, String)> = Vec::new();
    let mut seen = HashSet::new();
    for line in text.lines().map(str::trim).filter(|s| !s.is_empty()) {
        if let Some(header) = line.strip_prefix('>') {
            let hash = header.split(['|', ' ', '\t']).next().unwrap_or("");
            if hash.len() != 64
                || !hash
                    .bytes()
                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
                || !seen.insert(hash.to_string())
            {
                return Err(
                    format!("FASTA IDs must be unique lowercase SHA256 hashes: {hash}").into(),
                );
            }
            rows.push((hash.to_string(), String::new()));
        } else {
            rows.last_mut()
                .ok_or("Sequence before FASTA header")?
                .1
                .push_str(line);
        }
    }
    for (hash, seq) in &rows {
        if sha256(seq.as_bytes()) != *hash {
            return Err(format!("Sequence/hash mismatch: {hash}").into());
        }
    }
    if rows.is_empty() {
        return Err("Empty FASTA".into());
    }
    Ok(rows)
}
