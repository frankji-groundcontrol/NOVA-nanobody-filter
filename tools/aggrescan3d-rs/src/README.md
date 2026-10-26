# Native scoring modules

Parent: [scorer guide](../README.md).

| File | Purpose and data flow |
| --- | --- |
| [main.rs](main.rs) | Validate CLI options and invoke the batch workflow |
| [lib.rs](lib.rs) | Export the native modules and shared result type |
| [parser.rs](parser.rs) | Validate full heavy-atom models and hash-keyed FASTA; preserve numbering while parsing accessibility |
| [accessibility.rs](accessibility.rs) | Require FreeSASA 2.0.1, invoke pinned settings and preserve raw output |
| [scoring.rs](scoring.rs) | Apply upstream matrices, exposure/spatial weights and summary conventions |
| [metrics.rs](metrics.rs) | Checked whole-VHH and caller-selected region summaries, positive fraction and normalized positive burden |
| [pipeline.rs](pipeline.rs) | Join sequence hashes to structures, score each input and write evidence |
| [report.rs](report.rs) | Escape CSV cells and emit rounded/full-precision residue scores |
| [error.rs](error.rs) | Preserve distinct input, surface-engine, filesystem and partial-batch failures |

Next: run the [regression tests](../tests/README.md) after any numerical or input-handling change.
