# Frozen positive-to-root lineage verification — 22 October 2026

**Result:** PASS for *stored artifact consistency*, not independent scanner-result reproduction.

## Frozen inputs and verified identities

| Original file | Bytes | SHA-256 |
| --- | ---: | --- |
| C1_POSITIVE_FEASIBILITY_192.csv | 40,984 | `adfdd519c81e77ecef095f11ee18692510774e714fdbc48fe98cb7345b08bddc` |
| C5_PC_TO_ROOT_FINAL.csv | 194,148 | `f28dcb3f7ed31b2dacb67ef0a449b7c25c700d7c12ff11f53a14080397302382` |
| C6_ROOT_CENSUS.csv | 179,190 | `97e989ef8b3f86413fc821d97c78a15701bdd8e2cb4fdb020ffdc64c4554762c` |
| D1_ROOT_INDEX_342.csv | 66,543 | `ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3` |

These digests were independently computed from complete read-only Wits byte-range retrieval on 22 October 2026, verifying each returned chunk's hash as well. The C1 roster hash also matches the historical C1 `SHA256SUMS.txt`. None of the private case-level data is committed.

## Independently checked memberships

- C1 positive roster: **192 unique cases**.
- **191** are represented in the D1 root index; exactly one is unmapped, case **17701**, as expected.
- Every mapped root's repository agrees exactly with the corresponding C1 positive repository.
- C5: **455 distinct producing-change IDs** across **191 workflows**, assigned to **342 roots**.
- C6 and D1 independently include exactly those **342 roots** and the same **455 producing-change IDs**, with no duplicate assignments, missing IDs, cross-workflow roots, wrong repository IDs, or size inconsistencies.
- Root-size distribution: **283 × 1**, **36 × 2**, **9 × 3**, **7 × 4**, **3 × 5**, **3 × 6**, **1 × 12**; weighted count = **455**.
- The previous complete C1-to-C2 audit identified **190 paired positives** and **190 paired negatives**, and exactly **13918, 17460** as the two unmatched positives. This is a *different* exclusion criterion from case **17701**, which is scanner-positive but not mapped to an exact producing change.

## Repeatable read-only gate

The standalone gate is available in the staged companion files `analysis/frozen_root_lineage_gate.py` and `tests/test_frozen_root_lineage_gate.py`. It verifies all four pre-registered byte lengths and full SHA-256 digests, validates schemas, cross-file memberships and root sizes, and emits aggregate counts only. Its **12 synthetic-only unit tests passed** in the development container on 22 October 2026. Those two files are not asserted to be present in this GitHub branch until committed separately and CI-verified.

## Still outstanding

The exact August 29 final SQLite snapshot has **not** been byte-authenticated against the source-declared SHA-256 `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`. The available read-only database tools only expose earlier named snapshots from the miner data directory. Likewise, the 14 missing original CodeQL baseline SARIF files are not recovered.

This cross-artifact audit does **not** rerun the historical scanner pipeline, validate the positive labels or producing-change *semantics*, independently redo human/LLM root-boundary annotation, recompute matched statistics, or establish causal intervention effects. Do not promote aggregate consistency into scientific replication.
