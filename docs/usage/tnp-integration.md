# TNP integration and profile recovery

NOVA's Developability stage obtains one validated TNP profile and then combines TNP criteria with enabled Aggrescan3D caps. The TNP integration accepts a profile only when the named JSON entry is an object containing all six finite descriptors: total CDR length, CDR3 length, CDR3 compactness, PSH, PPC and PNC.

Null/non-object entries, missing descriptors, invalid numeric values and non-finite scores invalidate that attempt. The wrapper recomputes within its existing three-attempt limit. A3D consumes only the successful attempt's model before temporary cleanup. Missing measurements are never replaced with zero. TNP's numerical methods and screening thresholds are unchanged.

## Computation and screening results

`/developability/analyze` and `/developability/analyze-batch` preserve these fields:

| Field | Meaning |
| --- | --- |
| `passed` | Combined TNP/A3D screening decision; unavailable computation cannot pass |
| `error` | True when a TNP profile was unavailable or a batch computation raised an exception |
| `error_kind` | `no_profile`, `timeout` or `profile_exception` for compute failures |
| `sequence_sha256` | Exact input sequence digest associated with a compute failure |
| `reason` | Public failure explanation without raw subprocess streams or exception text |
| `aggrescan3d` | Native A3D result and cap checks when the TNP profile was successfully computed |

An exhausted computation is an unmeasured result. A completed profile outside TNP ranges or A3D caps is a screening rejection. Full validation retains these details under `details.developability` and attributes failure to `Developability`.

## Diagnostics and execution

Structured `TNP_DIAGNOSTIC` events correlate each profile and attempt using a generated profile ID, sequence SHA-256, sequence length and attempt number. They include fixed failure categories, return codes, elapsed time and up to 16 allowlisted scientific component/line locations. They omit raw sequence, CLI streams, source paths, source lines and arbitrary exception text.

These changes incorporate [PR #3 at e912789](https://github.com/frankji-groundcontrol/NOVA-nanobody-filter/pull/3/changes/e912789a03ca5ec90b9ccb58d37a89adbfb0b84b). The integration additionally requires complete finite profiles and declares compute-error fields in HTTP schemas. The per-attempt CLI timeout remains 300 seconds; the service retains its configured asynchronous timeout and existing worker-thread cancellation behavior. Diagnostics identify observed failures without establishing a cause inside a third-party predictor.

## Verification

Run the [isolated TNP tests](../../tests/README.md) and [profile/API recovery tests](../../metanano/tests/utils/test_tnp_profile_validation.py). Recovery tests feed invalid first-attempt output followed by valid output, require a second TNP computation, and verify that A3D runs once on the valid model. Existing native integration tests also exercise successful and rejected Developability results.

Parent: [usage index](README.md). Related: [A3D policy and native setup](aggrescan3d-rust.md). Next: reproduce failures with the correlated diagnostic events and the installed tool versions before attributing them to a predictor or GPU.
