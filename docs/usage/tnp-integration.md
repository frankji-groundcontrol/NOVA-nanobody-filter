# TNP integration and profile recovery

NOVA's Developability stage obtains one validated TNP profile and then combines TNP criteria with enabled Aggrescan3D caps. The TNP integration accepts a profile only when the named JSON entry is an object containing all six finite descriptors: total CDR length, CDR3 length, CDR3 compactness, PSH, PPC and PNC.

Null/non-object entries, missing descriptors, invalid numeric values and non-finite scores invalidate that attempt. The wrapper recomputes within its three-attempt limit and one shared time budget. A3D consumes only the successful attempt's model before temporary cleanup. Missing measurements are never replaced with zero. TNP's numerical methods and screening thresholds are unchanged.

## Computation and screening results

`/developability/analyze` and `/developability/analyze-batch` preserve these fields:

| Field | Meaning |
| --- | --- |
| `passed` | Combined TNP/A3D screening decision; unavailable computation cannot pass |
| `error` | True when the complete computation was unavailable, exceeded its deadline or a batch computation raised an exception |
| `error_kind` | `no_profile`, `timeout` or `profile_exception` for compute failures |
| `sequence_sha256` | Exact input sequence digest associated with a compute failure |
| `reason` | Public failure explanation without raw subprocess streams or exception text |
| `aggrescan3d` | Native A3D result and cap checks when the TNP profile was successfully computed |

An exhausted computation is an unmeasured result. A completed profile outside TNP ranges or A3D caps is a screening rejection. Full validation retains these details under `details.developability` and attributes failure to `Developability`.

`/developability/tnp-profile` also returns `success=false`, `error_kind` (`no_profile` or `timeout`) and the sequence digest when no complete profile is available. Deadline errors use these structured responses with HTTP 200, including single and batch analysis; they do not expose raw exception text.

## Shared deadline and cancellation

Each asynchronous profile gets one `config.async_config.task_timeout` budget, default 300 seconds. It begins before manager initialization and waiting for the TNP semaphore. Queueing, all TNP attempts, parsing and A3D consume that same budget. Retries do not reset it. A TNP command can use at most 300 seconds and A3D at most 60 seconds, each further limited by the remaining budget. A direct synchronous `TNPWrapper.profile(sequence)` also defaults to 300 seconds total. Standalone `Aggrescan3DWrapper.profile(sequence, structure)` defaults to 60 seconds.

For example, with a 300-second budget, 40 seconds in the queue and 200 seconds in a failed attempt leave at most 60 seconds for another attempt and A3D together. Three fast invalid attempts still exhaust the attempt limit; one attempt consuming the remaining budget ends computation immediately. Neither case loops indefinitely.

TNP and the Rust scorer run in their own POSIX process groups. On timeout or cancellation, the runner signals the entire group with SIGTERM, allows up to 0.2 seconds for the direct child to exit, then sends SIGKILL to remaining group members and reaps the direct child. This also stops normal descendant processes such as FreeSASA. The service signals the worker and holds its TNP semaphore slot until the worker finishes cleanup, including on repeated request cancellation. Cancelling a queued request does not launch a process or release another request's slot.

The compute deadline permits termination, child reaping and temporary-file cleanup overhead. It is not a hard real-time response guarantee. A result finishing after the shared deadline is discarded and reported as `timeout`. A3D's own 60-second cap can fail scoring earlier while preserving valid TNP descriptors; an exhausted shared deadline makes the complete computation unavailable.

Python callers can supply a `ProfileExecution(timeout)` from `metanano.utils.tnp_wrapper` via `TNPWrapper.profile(sequence, execution=execution)` or `Aggrescan3DWrapper.profile(sequence, structure, execution)`. An injected TNP structural-scoring callback receives `(sequence, structure, execution)` so it uses the same context.

## Diagnostics and execution

Structured `TNP_DIAGNOSTIC` events correlate each profile and attempt using a generated profile ID, sequence SHA-256, sequence length and attempt number. They include fixed failure categories, return codes, elapsed time and up to 16 allowlisted scientific component/line locations. They omit raw sequence, CLI streams, source paths, source lines and arbitrary exception text.

These changes incorporate [PR #3 at e912789](https://github.com/frankji-groundcontrol/NOVA-nanobody-filter/pull/3/changes/e912789a03ca5ec90b9ccb58d37a89adbfb0b84b). The integration additionally requires complete finite profiles, declares compute-error fields in HTTP schemas and enforces the shared deadline described above. Diagnostics identify observed failures without establishing a cause inside a third-party predictor. Deadline exhaustion records the number of attempts actually started.

## Verification

Run the [isolated TNP tests](../../tests/README.md) and [profile/API recovery tests](../../metanano/tests/utils/test_tnp_profile_validation.py). Recovery tests feed invalid first-attempt output followed by valid output, require a second TNP computation, and verify that A3D runs once on the valid model. [Deadline tests](../../tests/test_tnp_deadline.py) launch actual parent/child processes that ignore SIGTERM and verify timeout, cancellation, reaping and semaphore ownership. Native integration tests cover the shared TNP/A3D context, a shorter native deadline, and successful and rejected Developability results.

Parent: [usage index](README.md). Related: [A3D policy and native setup](aggrescan3d-rust.md). Next: reproduce failures with the correlated diagnostic events and the installed tool versions before attributing them to a predictor or GPU.
