# Isolated TNP integration tests

These tests load the wrapper directly or isolate the service class so they can run without importing GPU and application dependencies.

| File | Coverage |
| --- | --- |
| [test_tnp_wrapper_retry.py](test_tnp_wrapper_retry.py) | Retry limits, per-call diagnostics, concurrent correlation, sanitized traceback locations, invalid JSON and shared-budget exhaustion |
| [test_developability_execution.py](test_developability_execution.py) | Shared execution context, digest-linked compute errors, batch timeout classification and preservation of biological rejection |
| [test_tnp_deadline.py](test_tnp_deadline.py) | Actual process-tree termination/reaping, shared retry and queue budgets, repeated cancellation, semaphore ownership and prevention of cancelled launches |

Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q`. The combined suite is `python -m pytest metanano/tests tests --ignore=metanano/tests/tools -q`; external-tool tests additionally need their installed dependencies.

The complementary [profile-boundary and API tests](../metanano/tests/utils/test_tnp_profile_validation.py) verify recovery to a complete finite profile and preservation of compute-error metadata through HTTP responses. [Native A3D tests](../metanano/tests/utils/test_aggrescan3d_integration.py) verify the model handoff and combined Developability decisions.

Parent: [project guide](../README.md). Next: rerun these tests when changing retries, parsing, logging or service execution.
