# TNP integration repair — 2026-10-17

Reviewed [PR #3](https://github.com/frankji-groundcontrol/NOVA-nanobody-filter/pull/3) at `e912789a03ca5ec90b9ccb58d37a89adbfb0b84b` and incorporated its per-call diagnostics, traceback sanitization, malformed-JSON retry handling and digest-linked compute errors. The merge preserves A3D scoring inside the successful TNP model's lifetime and the shared Developability evaluator.

Eight failing regressions demonstrated additional integration defects: null/list entries and invalid numeric values escaped the retry loop, missing measurements became zero, non-finite values were accepted, and response validation removed compute-error fields. The repair requires complete finite descriptors, recomputes invalid attempts within the existing retry budget, and preserves error kind/digest through single and batch HTTP responses.

The focused integration run passes 54 tests, including real Rust/FreeSASA A3D paths. The 17 isolated tests from PR #3 pass with plugin autoload disabled. Scope is NOVA's wrapper, service and API integration; model-prediction methods and timeout policy retain their existing behavior. No third-party predictor root cause or GPU execution is claimed.

The combined core suite passes 165 tests with 58 skips, excluding the external-tool directory because AbNumber is unavailable. Whitespace, 118 added local links/anchors, 19 new-document incoming links, folder guides, English additions and tracker/history parsing pass. Final review confirms that PR #3's diagnostics and the stricter profile contract preserve A3D scoring and combined screening decisions.

Published in [PR #4](https://github.com/frankji-groundcontrol/NOVA-nanobody-filter/pull/4). The PR description thanks @thomasvangurp for PR #3, and commit `a35ae64` records co-author credit.

Usage and fields: [TNP guide](../usage/tnp-integration.md). Tests: [isolated suite](../../tests/README.md) and [profile recovery/API regressions](../../metanano/tests/utils/test_tnp_profile_validation.py). State: [owned integration plan](../plans/2026-10-17-aggrescan3d-rust/2026-10-17-aggrescan3d-rust.md). Parent: [changelog index](README.md).
