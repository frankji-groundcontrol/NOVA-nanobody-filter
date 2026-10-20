# Native regression tests

Parent: [scorer guide](../README.md).

- [cli.rs](cli.rs): unsupported modes and missing arguments must fail before surface calculation.
- [parsing.rs](parsing.rs): reject incomplete structures, verify sequence hashes and preserve atom coordinates across insertion-code normalization.
- [scoring.rs](scoring.rs): upstream matrix parity, radius/RSA boundaries, zero-center behavior and summary conventions.
- [metrics.rs](metrics.rs): whole-VHH and region-mask normalization, retained hotspots under signed cancellation, zero-only/negative inputs and validation of non-finite, empty, overflowing or mismatched inputs.

Input: [pinned upstream fixture](../fixtures/README.md). Run `cargo test --locked --manifest-path tools/aggrescan3d-rs/Cargo.toml` from the repository root. Next: use the [independent parity harness](../tools/README.md) when changing the native method.
