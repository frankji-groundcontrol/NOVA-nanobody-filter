# Aggrescan3D static scoring in Rust

This is the existing MetaNova `aggrescan3d-rs` 0.1.0 port, imported from manual-review workspace commit `c5925c0e8b6a206d842bef4d2eee240c020229ef`. Its numerical scoring, input validation and pinned fixtures are preserved. NOVA adds reusable metric-reporting functions, round-trip decimal score output and a portable generated evidence guide.

The reference implementation is [LCBio Aggrescan3D](https://bitbucket.org/lcbio/aggrescan3d/src/afd8a9da1f44f7b702aceb5a80abe67dde74ca00/), revision `afd8a9da1f44f7b702aceb5a80abe67dde74ca00`. Scoring is native Rust; solvent accessibility uses its bundled **FreeSASA 2.0.1** C executable. Python is used by NOVA's subprocess adapter and the independent upstream verification harness, not the numerical Rust scorer.

## Method and citation

Zambrano R, Jamroz M, Szczasiuk A, Pujols J, Kmiecik S, Ventura S. **AGGRESCAN3D (A3D): server for prediction of aggregation properties of protein structures.** *Nucleic Acids Research*. 2015;43(W1):W306–W313. [doi:10.1093/nar/gkv359](https://doi.org/10.1093/nar/gkv359).

Related web-server update: Kuriata A et al. **Aggrescan3D (A3D) 2.0: prediction and engineering of protein solubility.** *Nucleic Acids Research*. 2019;47(W1):W300–W307. [doi:10.1093/nar/gkz321](https://doi.org/10.1093/nar/gkz321).

The default uses the original matrix without pH correction, a 10 Å Cα neighborhood and FreeSASA Lee–Richards accessibility at 100 slices, a 1.4 Å probe and NACCESS radii. RSA is the total-relative field printed to one decimal place. A residue below 10% RSA contributes zero; otherwise its exposed intrinsic contribution is `matrix[aa] × 0.0599 × exp(0.0521 × min(RSA,55))`. A nonzero center sums neighbors at `0 < d < radius`, weighted by `1.2915 × exp(-2.56 × d/radius)`. A zero center remains zero.

Summaries preserve upstream zero-initialized extrema and positive AUC that skips zero residues. Scores are dimensionless. Static inputs must be isolated, complete, standard-amino-acid heavy-atom PDB models. Sequential analysis numbering prevents FreeSASA 2.0.1 from merging IMGT insertion codes; original coordinates, source checksums and residue mapping are retained. Unsupported input or dynamic/FoldX options fail explicitly.

NOVA reuses TNP's model and performs no additional minimization, mutation prediction or dynamics. Its Developability stage registers an A3D subfilter requiring both whole-VHH mean `<= -0.68002724866200` and peak `<= 1.58023066762925` alongside TNP criteria. These are NOVA screening caps; model-based scores do not establish experimental solubility. See the [policy and method requirements](../../docs/usage/aggrescan3d-rust.md#filter-policy).

## Whole-VHH and segment reporting

The [VHH metric guide](../../docs/usage/aggrescan3d-rust.md#whole-vhh-and-regional-evaluation) explains each native summary, the per-residue score/RSA output, CDR/framework inspection priorities and proposed positive burden. Score the intact VHH first, then aggregate scores with region masks built from numbering annotations and the original residue mapping.

Public functions `metrics::summarize_vhh(&scores)` and `metrics::summarize_region(&scores, &region_mask)` return the mean, zero-anchored maximum, positive count/fraction, positive score sum and normalized positive burden. They accept existing scores and reject empty, non-finite, overflowing or mismatched inputs. See the [copyable Rust example](../../docs/usage/aggrescan3d-rust.md#reusable-rust-functions), [implementation](src/metrics.rs) and [tests](tests/metrics.rs). Original numerical APIs `scoring::score` and `scoring::summarize` remain available.

Region annotation and patch discovery are caller responsibilities. The helpers expose derived reports; the application gates only whole-VHH mean and peak. Regional metrics do not add further rejection conditions.

## Contents

| Item | Purpose |
| --- | --- |
| [src](src/README.md) | CLI, validation, external accessibility, native scoring and CSV evidence |
| [tests](tests/README.md) | CLI, structural integrity and scientific boundary regressions |
| [fixtures](fixtures/README.md) | Pinned upstream values covering all 20 residues and default/pH scales |
| [tools](tools/README.md) | Pinned FreeSASA builder and independent upstream parity harness |
| [Cargo.toml](Cargo.toml), [Cargo.lock](Cargo.lock) | Crate metadata and locked SHA-256 dependency |
| [LICENSE](LICENSE) | Original MIT notice retained for this derivative port |

Upstream's root `LICENCE` is MIT, while its `setup.py` metadata says “free for non-commercial users.” That provenance discrepancy is retained here. FreeSASA retains its own MIT notice in the downloaded source tree.

## Build, run and verify

From the NOVA repository root:

```sh
sh install/install-aggrescan3d.sh
cargo test --locked --manifest-path tools/aggrescan3d-rs/Cargo.toml
.tools/bin/aggrescan3d-rs \
  --fasta sequences.fasta --structures structures \
  --out results/summary --residue-out results/residues \
  --freesasa .tools/bin/freesasa
python tools/aggrescan3d-rs/tools/upstream_parity.py \
  --upstream .tools/aggrescan3d-source/upstream \
  --summary results/summary/aggrescan3d.csv \
  --residue-dir results/residues --out results/upstream-parity.csv
```

FASTA identifiers must be SHA-256 hashes of the exact uppercase ungapped sequence. Structures are `<sequence_hash>.pdb`. The CLI retains per-residue scores, normalized structures, original residue mapping and FreeSASA output. Every input gets a summary row; partial batches exit 5. Other exits are 2 for input/options, 3 for the surface engine and 4 for filesystem errors. Named outputs are overwritten on a deliberate rerun.

Next: use [NOVA's integration guide](../../docs/usage/aggrescan3d-rust.md), and rerun numerical parity when changing scoring or the surface engine. Parent: [native tools](../README.md).
