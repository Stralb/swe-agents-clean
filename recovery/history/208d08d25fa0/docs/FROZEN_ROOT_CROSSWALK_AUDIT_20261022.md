# Frozen positive-cohort → producing-change → root-census audit

**Date:** 22 October 2026  
**Status:** `PASS_FROZEN_C1_TO_C5_C6_D1_MEMBERSHIP_ONLY`

This audit independently joined original source records retrieved through approved **read-only Wits research-artifact access**. It did not run the original miner, reclassify security findings, edit the cluster, or modify the historical frozen output. No case-level data were uploaded to GitHub.

## Source files and byte identities

| Frozen source | Bytes | SHA-256 |
| --- | ---: | --- |
| `matched_control_c1_v1_1/C1_POSITIVE_FEASIBILITY_192.csv` | 40,984 | `adfdd519c81e77ecef095f11ee18692510774e714fdbc48fe98cb7345b08bddc` |
| `D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/C5_PC_TO_ROOT_FINAL.csv` | 194,148 | `f28dcb3f7ed31b2dacb67ef0a449b7c25c700d7c12ff11f53a14080397302382` |
| `D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/C6_ROOT_CENSUS.csv` | 179,190 | `97e989ef8b3f86413fc821d97c78a15701bdd8e2cb4fdb020ffdc64c4554762c` |
| `D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/D1_ROOT_INDEX_342.csv` | 66,543 | `ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3` |

The C1 positive-file hash independently matches its archived `SHA256SUMS.txt`. C5, C6 and D1 file hashes were computed independently from ordered source byte chunks, with all individual chunk hashes verified against the read-only connector's SHA-256. These newly pinned file hashes are *not* independent provenance of the original annotations or the underlying scanner truth.

## Recomputed membership and integrity

| Cross-check | Result |
| --- | ---: |
| Frozen C1 positive cases | **192** |
| Unique workflow IDs in mapped root census | **191** |
| Exactly unmapped C1 positive | **17701** |
| Frozen C5 producing-change rows | **455** |
| Unique C5 producing-change IDs | **455** |
| Unique roots in C5/C6/D1 | **342/342/342** |
| Complete producing-change coverage in C6 and D1 | **455/455** |
| Root-level case / repository / membership / count mismatches | **0** |
| Duplicate producing-change assignments or cross-workflow roots | **0** |

Recomputed root size distribution: **283 singletons**, 36 two-PC roots, 9 three-PC roots, 7 four-PC roots, 3 five-PC roots, 3 six-PC roots and one twelve-PC root. This accounts for **342 distinct roots and exactly 455 PCs**.

All 191 mapped workflow IDs belong to the original 192 C1 positive roster and have matching repository strings. `17701` is the sole positive lacking a mapped root, consistently with the original known unmapped-case exception.

## Repeatable local verification

The independent fail-closed verifier checks source hashes and full C1/C5/C6/D1 row relationships from approved local copies *outside Git*:

```bash
python -m analysis.frozen_root_crosswalk_gate \
  /secure/local/C1_POSITIVE_FEASIBILITY_192.csv \
  /secure/local/C5_PC_TO_ROOT_FINAL.csv \
  /secure/local/C6_ROOT_CENSUS.csv \
  /secure/local/D1_ROOT_INDEX_342.csv
```

All CI unit tests are synthetic. The checker does not run migrations, SQL, scanners, matching optimizers, network requests, or scripts from the archived miner.

## Precisely scoped claim

**This proves:** the original frozen case roster, producing-change mapping, two independent root-membership views, and root index are *mutually consistent as stored*, with independently verified byte identities.

**This does not prove:** independent regeneration of C1's scanner-positive labels from the August 29 SQLite database, security validity/true exploitability, independent manual/LLM root-boundary adjudication, original CodeQL baseline reproduction, statistical results, or causal effects.

The final database fingerprint remains **source-declared but not authenticated against the actual final SQLite bytes**: `126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa`.