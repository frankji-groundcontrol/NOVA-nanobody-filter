# TNP deadline hardening — 2026-10-17

Previously, an asynchronous request could time out while its worker continued up to three separate 300-second TNP attempts, releasing the semaphore before computation stopped. This follow-up in [PR #4](https://github.com/frankji-groundcontrol/NOVA-nanobody-filter/pull/4) gives each profile one shared deadline across queueing, retries, parsing and A3D. Defaults are 300 seconds overall, at most three TNP attempts, and a 60-second native scoring cap within the remaining budget.

Timeout and cancellation terminate the owned POSIX process group, escalate from SIGTERM to SIGKILL after up to 0.2 seconds, and reap the direct child. The service waits for worker cleanup before releasing its semaphore slot, including repeated cancellation. Queued expiry cannot start computation or release another request's slot. A result arriving after the shared deadline cannot become a valid profile. Cleanup adds overhead beyond the compute deadline.

Single and batch Developability analysis return a typed `timeout` compute error with the sequence digest. The direct TNP-profile endpoint also preserves timeout/no-profile kinds and digests. Ordinary A3D scoring failures before the overall deadline continue to preserve valid TNP metrics without repeating prediction. TNP/A3D numerical methods, caps and the three-stage pipeline are unchanged.

The focused Python suite passes 69 tests, including real subprocess trees that ignore SIGTERM, cancellation while cleanup is active, queue expiry, total retry exhaustion, shared A3D budgets and HTTP timeout responses. The combined core suite passes 180 tests with 58 skips; the isolated suite passes 23 tests with plugin autoload disabled. Whitespace, 130 added local links/anchors, 20 new-document indexes, English additions, folder guides and tracker/history parsing pass.

The local checkpoint uses surrogate predictor/scorer processes and actual installed Rust/FreeSASA where applicable. The external-tool test directory is excluded because AbNumber is unavailable. Native Rust sources are unchanged from the previously verified checkpoint of 17 tests and two doctests. The subsequent GPU checkpoint below exercises the actual predictor.

Published hardening commit `dc9f638` to PR #4. Verified the GitHub head against the local commit and the updated PR description against its prepared text, including the PR #3 author acknowledgment. The PR remains open and non-draft; GitHub reports no status-check runs.

## Predictor-backed GPU checkpoint

Verified PR revision `1b17b9a` in an isolated Linux runtime on an authorized NVIDIA RTX 4090 D host. This uses actual TNP prediction, OpenMM refinement, native A3D and FreeSASA, without predictor/scorer substitutes. The runtime uses Python 3.12, PyTorch `2.12.1+cu130`, TNP `29dcac72f1380e8538e8870f45a699d3c6156162`, ImmuneBuilder `0df4e2ad82a1aa60f37ea9dae335d1198159ef78` (1.2), ANARCI 2020.04.23, Biopython 1.86, OpenMM 8.3.1, PDBFixer 1.12, DSSP 4.5.7 and FreeSASA 2.0.1. The service uses one TNP slot and disables the optional GPU scheduler for this isolated check. Existing environments and running services are unchanged.

The input is the 119-residue example from the [pinned public TNP README](https://github.com/oxpig/TNP/blob/29dcac72f1380e8538e8870f45a699d3c6156162/README.md):

```text
QVKLQESGAELARPGASVKLSCKASGYTFTNYWMQWVKQRPGQGLDWIGAIYPGDGNTRYTHKFKGKATLTADKSSSTAYMQLSSLASEDSGVYYCARGEGNYAWFAYWGQGTTVTVSS
```

Its exact sequence SHA-256 is `77e0a6560993952554ec331f5ed32611ce318ad07f6389b98f2f9a3a7d3ddfb2`. The normal asynchronous service run completes in 17.703 seconds on the first attempt and observes 1,254 MiB of GPU memory in its owned predictor process. All six TNP flags are green. A3D reports `status=ok`, preserves the sequence digest and returns the following measurements:

| Measurement | Value |
| --- | --- |
| Total CDR length | 28 |
| CDR3 length | 12 |
| CDR3 compactness | 0.942262659389596 |
| Surface hydrophobic patches (PSH) | 79.9864 |
| Positive charge patches (PPC) | 0.0687 |
| Negative charge patches (PNC) | 0.0 |
| A3D average | -0.6396295744221752 |
| A3D maximum | 1.3279278175289748 |

The average exceeds the cap `-0.68002724866200`; the maximum satisfies its cap `1.58023066762925`. Developability correctly returns a measured rejection attributed to `a3d_average`, rather than a compute error. These values describe this generated model, whose input-structure SHA-256 is `65cc45ab33a55164f17b023de6314e7a1956b7096e9489bd412969aff8b4c08c` and normalized-structure SHA-256 is `e7e0699f424dfca14de62570b11f4a6976d7e475da3d5de0d00f983f675d6875`; they are not a promise of identical coordinates from every predictor environment.

The same real service and predictor also pass both interruption checks:

- A 10-second shared budget returns `error=true`, `error_kind=timeout` and the exact sequence digest after one TNP attempt. The test, including 0.5 seconds of post-return process observation, finishes in 10.541 seconds. The owned predictor reaches 1,254 MiB on the GPU.
- Repeated request cancellation while the owned predictor uses the GPU propagates cancellation after 0.041 seconds of cleanup. The predictor has reached 564 MiB at cancellation; there is one attempt.
- Both checks find no active owned processes after cleanup and confirm the TNP semaphore is released. A final GPU query reports no compute processes and 1 MiB used at 0% utilization. No retry starts after timeout or cancellation.

The initial uncached run also exercises failure handling: the host cannot download NanoBodyBuilder2 weights, so three attempts finish in 16.369 seconds with typed `no_profile` and the matching digest, then release the slot. The four official weights are subsequently fetched from [Zenodo record 7258553](https://zenodo.org/records/7258553), checked against the published file sizes and MD5 checksums before and after transfer, and cached in the isolated ImmuneBuilder package. The successful prediction requires no NOVA code change or relaxed validation.

Linux verification additionally passes 23 isolated Python tests, 46 profile/native integration tests, 17 Rust tests and two doctests. The documentation update passes 133 added local links/anchors, 20 new-document indexes, English additions, folder guides, state/history parsing and whitespace checks; recorded measurements match the saved run reports. This checkpoint covers the service-to-TNP-to-A3D path and actual GPU interruption; it does not exercise a deployed HTTP server, real Diversity/Nativeness execution or a concurrent production workload. The HTTP timeout schemas and surrogate process-group escalation remain covered by the local regression suite. No service is deployed or PR merged.

This builds on the [TNP integration repair](2026-10-17-tnp-integration-repair.md). The PR description retains thanks to @thomasvangurp for PR #3. Usage: [deadline and cancellation policy](../usage/tnp-integration.md#shared-deadline-and-cancellation). Tests: [isolated suite](../../tests/README.md). State: [owned tracker](../plans/2026-10-17-aggrescan3d-rust/2026-10-17-aggrescan3d-rust.track.yaml). Parent: [changelog index](README.md). Next: review PR #4 and provision the same pinned dependencies and cached official weights on serving hosts.
