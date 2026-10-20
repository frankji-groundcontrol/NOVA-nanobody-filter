# Surface builder and upstream verification

Parent: [scorer guide](../README.md).

- [build-freesasa.sh](build-freesasa.sh): fetch and verify Aggrescan3D revision `afd8a9da1f44f7b702aceb5a80abe67dde74ca00`, then compile its bundled FreeSASA 2.0.1 without optional JSON/XML/thread/check dependencies. Input: ignored source/build destination. Output: the pinned native executable.
- [upstream_parity.py](upstream_parity.py): load original upstream modules without changing scoring source, verify source/matrix checksums and compare saved FreeSASA residue identities, geometry, scores and all five summaries. Inputs: checkout, Rust summary and raw residue evidence. Output: parity CSV; nonzero on any mismatch. Residue tolerance is `1e-10`; summaries match at upstream four-decimal precision.

Next: rerun both after changing the surface engine or scoring method. Keep downloaded payloads under `.tools/` and preserve their notices.
