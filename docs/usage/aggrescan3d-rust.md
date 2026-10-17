# Aggrescan3D Rust integration

Aggrescan3D (A3D) is a registered subfilter within NOVA's **Developability** stage. The pipeline is **Diversity → Nativeness → Developability**, with Developability requiring both TNP criteria and the enabled A3D caps. A3D scores the isolated heavy-atom model already produced by TNP. The adapter consumes `Final_Models/<name>_NanoBodyBuilder2_Model.pdb` before cleanup, checks the exact submitted sequence and preserves SHA-256 provenance without another prediction.

## Filter policy

The subfilter is enabled by default. Both whole-VHH conditions must pass alongside TNP criteria:

| Metric | Inclusive pass boundary | Purpose |
| --- | --- | --- |
| `a3d_average` | `<= -0.68002724866200` | Limit the signed global average |
| `a3d_maximum` | `<= 1.58023066762925` | Limit the strongest positive local environment |

These are fixed screening caps, not universal physical boundaries or aggregation probabilities. The native paper defines the method; the numerical cutoffs are NOVA policy. Incoming batches do not recalculate them. Comparisons use decimal values and the native scores before display rounding. Total, minimum, positive AUC and regional/derived descriptors remain annotations.

The policy requires successful static scoring, the default intrinsic scale without pH correction, a 10 Å radius and `FreeSASA-2.0.1-NACCESS-LR100`. Missing/non-finite scores, sequence/count mismatches, invalid provenance or incompatible settings cannot pass. The pipeline returns `validation_status = "Failed"` and `failed_filters = ["Developability"]` when A3D rejects or cannot score. The nested result `details.developability.aggrescan3d.status = "error"` distinguishes an unavailable calculation from a completed calculation that exceeds a cap (`status = "ok", passed = false`). Earlier filter failures still stop validation before Developability.

## Install and enable

The native build needs Rust/Cargo, Git, a C compiler and Make. From the repository root:

```sh
sh install/install-aggrescan3d.sh
export PATH="$PWD/.tools/bin:$PATH"
python -m uvicorn metanano.app:app --port 5000
```

The installer builds the [vendored Rust scorer](../../tools/aggrescan3d-rs/README.md) and **FreeSASA 2.0.1** from a pinned upstream revision. Downloads and binaries stay in gitignored `.tools/`. A different FreeSASA version fails explicitly.

`AGGRESCAN3D_EXECUTABLE` and `FREESASA_EXECUTABLE` can specify absolute executable paths. Defaults are `aggrescan3d-rs` and `freesasa` on `PATH`. Set these variables before starting the server; invalid enable flags fail configuration validation. Native scoring has a 60-second subprocess timeout. Existing installations need the native build for the default Developability policy. `AGGRESCAN3D_ENABLED=false` explicitly disables A3D checks and leaves the TNP criteria active.

Programmatic configuration uses the same fields:

```python
from metanano.config import Aggrescan3DConfig, Config, DevelopabilityConfig
from metanano.pipeline import ValidationPipeline

config = Config(
    developability=DevelopabilityConfig(
        aggrescan3d=Aggrescan3DConfig(
            enabled=True,
            max_average="-0.68002724866200",
            max_peak="1.58023066762925",
        ),
    ),
)
pipeline = ValidationPipeline(config)
```

Existing TNP and structure-prediction dependencies are still required for sequence-based validation. For an existing model, use `Aggrescan3DWrapper().profile(sequence, pdb_path)` from `metanano.utils.aggrescan3d_wrapper`; `pdb_path` is a `pathlib.Path`. Apply the same A3D decision with `Aggrescan3DFilter(config.developability.aggrescan3d).analyze(sequence, profile)` from `metanano.filters`. These direct calls do not invoke TNP.

## Results and interpretation

Developability's nested `aggrescan3d` result contains native scores, provenance and both cap decisions in:

- `/validate` and `/validate/batch` under `details.developability.aggrescan3d`, after the earlier filters pass.
- `/developability/analyze` and `/developability/analyze-batch`.
- `DevelopabilityValidator.validate(sequence).details` and `DevelopabilityService.analyze_async(sequence)`.

The parent Developability `passed` field requires both TNP criteria and A3D caps. TNP `red_flags` retain their source meaning; the combined `reason` includes any A3D rejection or scoring error. `/developability/tnp-profile` returns the raw native scores and provenance beside TNP metrics; its `success` field indicates profile computation rather than the combined screening decision.

The usual sequence request body is unchanged:

```sh
curl -X POST http://localhost:5000/developability/analyze \
  -H 'Content-Type: application/json' \
  -d '{"sequence":"YOUR_UPPERCASE_NANOBODY_SEQUENCE"}'
```

| Field | Meaning |
| --- | --- |
| `passed` | Both inclusive caps passed; false for exceeded caps, errors or explicit disablement |
| `checks` | Each metric's decimal value, `<=` operator, configured threshold and Boolean decision |
| `failed_metrics` | Names of exceeded caps for a completed calculation |
| `status` | `ok` for a completed calculation; `error` for unavailable/incompatible scoring. Direct calls to a disabled subfilter return `disabled`; Developability omits A3D when disabled. |
| `sequence_hash` | SHA-256 of the exact uppercase sequence, used to join native inputs and output |
| `input_structure_sha256`, `normalized_structure_sha256` | Supplied heavy-atom model and coordinate-preserving sequential analysis copy |
| `residue_count`, `positive_residue_count` | Total scored residues and residues with a positive score |
| `a3d_total` | Sum of residue scores; depends on sequence length and is most useful for closely matched variants |
| `a3d_average` | Mean residue score; a length-normalized global comparison, with lower values more favorable |
| `a3d_maximum` | `max(0, residue scores)`: strongest positive hotspot, or zero when none exists |
| `a3d_minimum` | `min(0, residue scores)`: most negative score, or zero when none exists |
| `a3d_positive_auc` | Upstream sequence-profile statistic over successive nonzero scores; secondary to localized hotspot review |
| `radius_angstrom`, `ph_scale` | Default 10 Å neighborhood and `default-scale`, without pH correction |
| `surface_method` | `FreeSASA-2.0.1-NACCESS-LR100` |
| `mode` | `static-no-minimization`: no additional minimization is performed by this scorer |
| `citation_doi` | `10.1093/nar/gkv359` |
| `error` | Diagnostic text when scoring fails; numeric scores are omitted |

A3D describes aggregation propensity of the supplied model. Scores are dimensionless; they are not an experimental solubility measurement. A failed A3D calculation preserves valid TNP metrics and does not trigger a second TNP prediction. When TNP itself fails, no A3D calculation is attempted.

The API adapter returns summaries and removes temporary scoring files. For retained raw RSA output, residue scores and numbering maps, use the [native CLI](../../tools/aggrescan3d-rs/README.md). Only isolated, complete, standard-amino-acid heavy-atom PDB input is supported; multi-chain/models, alternate conformers, hydrogens and incomplete structures fail explicitly. Mutation scanning, FoldX and CABS dynamics are not implemented.

## Whole-VHH and regional evaluation

Use the whole-VHH summary together with localized surface-hotspot review. A favorable signed average can coexist with an aggregation-prone CDR or framework patch. Positive residue scores indicate aggregation-promoting environments; negative scores indicate solubility-promoting environments. Residues with RSA below 10% receive zero. Scores are dimensionless and have no fixed 0–1 range. These interpretations follow the [original A3D method](https://doi.org/10.1093/nar/gkv359).

The Rust CLI writes `residue-scores.csv` with chain, analysis residue number, amino-acid identity, `rsa_percent`, rounded `score` and `score_full_precision`. `residue-mapping.csv` maps analysis numbering back to source chain, residue number and insertion code. The current NOVA API returns the whole-chain summaries; regional metrics can be computed with the public Rust helpers below.

| Review scope | Recommended metrics and purpose |
| --- | --- |
| Whole VHH | `a3d_average`, `a3d_maximum`, positive fraction and normalized positive burden: combine global context with hotspot severity and prevalence |
| CDR1, CDR2 and CDR3 separately | The same panel for each annotated loop; inspect localized risk that the global mean can hide |
| FR1–FR4 separately | The same panel for framework surface risk and comparison of framework/humanization variants |
| FR2 and the nearby interface | Prioritize FR2 (IMGT 39–55), CDR3 and interface residue IMGT 118; inspect their spatial relationship and exposed positive scores |
| Spatial surface patches | Review positive-score residues that cluster in 3D, including residues far apart in sequence; patch discovery requires a defined geometric rule or structural inspection |

FR2 is an inspection priority because CDR3 can shield its exposed interface. The VHH-specific work of [Geyer et al. (2025)](https://doi.org/10.3390/antib14030073) highlights FR2 and IMGT 118. That paper's aggregation model is separate from A3D; it motivates regional inspection and does not validate the derived A3D reporting metrics here. Known antigen-contact annotations should also inform any subsequent hotspot engineering because exposed CDR residues may support binding, as discussed in the [A3D 2.0 paper](https://doi.org/10.1093/nar/gkz321).

For a nonempty residue set `R`, define the following derived reporting metrics using the full-VHH residue scores `s_i`:

```text
positive_residue_count = count(s_i > 0)
positive_fraction     = positive_residue_count / N_R
positive_score_sum    = sum(max(s_i, 0))
positive_burden       = positive_score_sum / N_R
```

`N_R` counts all residues assigned to the region, including zero-scored buried residues. Positive fraction lies between 0 and 1; positive score sum and positive burden remain score-based quantities. Positive burden avoids cancellation by negative scores and normalizes for differing loop or VHH lengths. It is a derived screening descriptor, with no calibrated experimental cutoff.

`a3d_positive_auc` follows a different rule: the upstream implementation skips zero scores and adds `max((previous + current) / 2, 0)` for successive nonzero values in sequence order. It is distinct from positive score sum, normalized positive burden, contiguous segment length and physical patch surface area.

**Score the intact isolated VHH once, then group residue centers by their annotations.** Cropping a CDR before scoring changes its solvent exposure and spatial neighbors. Each regional score retains contributions from nearby residues in other regions, so a regional summary describes the location of risk rather than a unique causal contribution. Map IMGT annotations through the original residue mapping, including insertion codes; normalized PDB residue numbers are not automatically IMGT positions.

Compare candidates and variants using consistent structure preparation, accessibility settings and scoring scale. Use a matched reference panel and experimental aggregation data to calibrate any later screening policy. Automatic IMGT assignment, spatial patch detection and API-level regional summaries are not part of these helpers.

## Reusable Rust functions

Use `tools/aggrescan3d-rs` as a Cargo path dependency. The existing numerical functions and the new reporting helpers are public library calls:

| Function | Input and output |
| --- | --- |
| `scoring::score(&residues, radius, ph)` | Prepared Cα coordinates and RSA values to a full-context per-residue A3D score vector |
| `scoring::summarize(&scores)` | Nonempty finite score vector to the original total, average, maximum, minimum and positive AUC |
| `metrics::summarize_vhh(&scores)` | Checked score vector to the recommended whole-VHH reporting panel |
| `metrics::summarize_region(&scores, &region_mask)` | Full-VHH scores plus a same-length Boolean mask to the selected region's reporting panel |

The checked helpers return `VhhMetrics`: `residue_count`, `a3d_average`, `a3d_maximum`, `positive_residue_count`, `positive_fraction`, `positive_score_sum` and `positive_burden`. They reject empty/non-finite score inputs, overflowing aggregates, mask-length mismatches and empty selections. Each call operates on already-computed scores. Separate masks can represent each CDR/framework region or a custom interface such as FR2 plus IMGT 118; custom masks may overlap, so regional results need not form a disjoint partition.

This is a synthetic score example; construct real masks from the VHH's numbering annotations:

```rust
use aggrescan3d_rs::metrics::{summarize_region, summarize_vhh};
use aggrescan3d_rs::Result;

fn main() -> Result<()> {
    let full_vhh_scores = [-8.0, 4.0, 0.0, 2.0];
    let region_mask = [false, true, true, false];
    let whole = summarize_vhh(&full_vhh_scores)?;
    let region = summarize_region(&full_vhh_scores, &region_mask)?;

    assert_eq!(whole.a3d_average, -0.5);
    assert_eq!(whole.positive_burden, 1.5);
    assert_eq!(region.residue_count, 2);
    assert_eq!(region.positive_burden, 2.0);
    Ok(())
}
```

For newly computed native scores, pass the result of `scoring::score` to these same helpers. Both helpers reuse the native mean and zero-anchored maximum conventions. The existing CLI/HTTP summary schema remains as described above; the new derived metrics are returned by the library helpers.

## Verification

After installing the native tools and project test dependencies:

```sh
cargo test --locked --manifest-path tools/aggrescan3d-rs/Cargo.toml
python -m pytest tests metanano/tests/test_aggrescan3d.py metanano/tests/utils -q
```

[Integration tests](../../metanano/tests/utils/test_aggrescan3d_integration.py) exercise actual Rust/FreeSASA scoring, source preservation, invalid structures, sequence mismatches, subprocess errors, summary validation, sync/async rejection within Developability, batch validation, explicit disablement and the full application's developability route. They stub the expensive TNP predictor with synthetic full-heavy-atom models and verify one prediction per sequence. [Filter tests](../../metanano/tests/test_aggrescan3d.py) check inclusive decimal boundaries, both required caps, method compatibility, missing/non-finite measurements and preservation of TNP rejection. Native tests skip explicitly if `.tools/bin` has not been built. Existing native fixtures independently compare all 20 amino acids with pinned upstream scores. [Metric helper tests](../../tools/aggrescan3d-rs/tests/metrics.rs) cover normalization, signed cancellation, zero-anchored maxima, full/partial masks, invalid inputs and overflow; Rust documentation examples are also executable tests.

## Paper citation

Zambrano R, Jamroz M, Szczasiuk A, Pujols J, Kmiecik S, Ventura S. **AGGRESCAN3D (A3D): server for prediction of aggregation properties of protein structures.** *Nucleic Acids Research*. 2015;43(W1):W306–W313. [doi:10.1093/nar/gkv359](https://doi.org/10.1093/nar/gkv359).

```bibtex
@article{Zambrano2015Aggrescan3D,
  author = {Zambrano, Rafael and Jamroz, Michal and Szczasiuk, Agata and
            Pujols, Jordi and Kmiecik, Sebastian and Ventura, Salvador},
  title = {{AGGRESCAN3D} ({A3D}): server for prediction of aggregation
           properties of protein structures},
  journal = {Nucleic Acids Research},
  year = {2015},
  volume = {43},
  number = {W1},
  pages = {W306--W313},
  doi = {10.1093/nar/gkv359}
}
```

Related update: Kuriata A et al. **Aggrescan3D (A3D) 2.0: prediction and engineering of protein solubility.** *Nucleic Acids Research*. 2019;47(W1):W300–W307. [doi:10.1093/nar/gkz321](https://doi.org/10.1093/nar/gkz321).

VHH regional context: Geyer FK et al. **Computational Prediction of Single-Domain Immunoglobulin Aggregation Propensities Facilitates Discovery and Humanization of Recombinant Nanobodies.** *Antibodies*. 2025;14(3):73. [doi:10.3390/antib14030073](https://doi.org/10.3390/antib14030073).

Parent: [usage index](README.md). Implementation scope and state: [integration plan](../plans/2026-10-17-aggrescan3d-rust/2026-10-17-aggrescan3d-rust.md). Next: install native tools on each serving host and verify a predictor-backed request with the configured policy.
