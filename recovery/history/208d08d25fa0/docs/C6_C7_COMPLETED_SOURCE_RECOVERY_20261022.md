# C4–C7 completed-output recovery: catalog-level only

**Date:** 22 October 2026  
**Status:** `CATALOG_AND_PRIOR_REPORT_RECOVERED_RAW_STATISTICAL_REPLAY_BLOCKED`

The previous C3 audit found its *initial annotation templates* blank. Those templates do **not** represent the final matched-control coding. A later study workflow produced: C4 first-pass blind semantics, C5 corrected/frozen control coding, C6 positive-versus-negative paired comparisons, and C7 pathway integration. The researcher's connected Library now lists the **actual historical filenames and byte lengths**, including:

| Frozen stage | Located original result | Library-catalog bytes |
| --- | --- | ---: |
| C4 | `C4_CONTROL_SEMANTIC_MASTER_190_FIRST_PASS.csv` | 129,302 |
| C5 | `C5_CONTROL_MASTER_190_FROZEN.csv` | 171,522 |
| C6 | `C6_MATCHED_PAIR_MASTER_190.csv` | 98,431 |
| C6 | `C6_PAIRED_CONTINGENCY_LONG.csv` | 14,591 |
| C6 | `C6_PRIMARY_OMNIBUS_RESULTS.csv` | 2,397 |
| C6 | `C6_MATCHED_POSITIVE_VS_CONTROL_v1.0.tar.gz` | 117,528 |
| C7 | `C7_MATCHED_PATHWAY_MASTER_190.csv` | 112,254 |
| C7 | `C7_PATHWAY_STRATA_COMPARISON.csv` | 5,831 |
| C7 | `C7_CONTROL_PATHWAY_INTEGRATION_v1.0.tar.gz` | 106,359 |

**These are a file-catalog recovery, not a byte-identical authentication.** Current file-access policy did not authorize raw-byte materialization of the Library-backed Project files. Do not retry denied routes, invent sandbox links to prior-turn generated outputs, commit case-level source material, or claim the library file hashes were recomputed.

## Historic analytical decisions to preserve

The preserved C6 handoff describes **190 matched workflow pairs**, **nine** prespecified primary comparisons, repository-blocked uncertainty estimation and Tier-A (115 same-repository pairs) sensitivity. Its *source-reported*, **not newly reproduced**, results include:

| Comparison | Historic p-value |
| --- | ---: |
| Issue instruction specificity | 0.00052 |
| Issue purpose | 0.097 |
| PR goal alignment | 0.001 |
| Implementation category | 0.120 |
| Human review | 0.419 |
| Issue-to-PR delay | 0.241 |
| Same issue/PR author | 1.000 |
| Any prior observed repository activity | 0.336 |
| Primary agent/tool | 0.219 |

The same-repository source reports `p=0.00645` for instruction specificity and `p=0.077` for alignment. **Do not claim these are independently recalculated here.** The original C6 QC corrected a failed GitHub review retrieval: one control with review data unavailable must be **missing**, not `No review`. Hence **human-review analysis uses 189 complete pairs**, not 190. Do not impute review status. The original study intentionally did not backfill unblinded F1–F5 controls or fit a post-selection conditional logistic model. Retain these boundaries.

The historical C7 report identifies **190 pairs** and **416 mapped producing changes** in its pathway integration, *not* a newly reproduced change count. C7's source-reported aggregate archive SHA-256 is `976b523c3df347c82a81998a31585536e5dc826c9b61f55220190fa75b5f8273`; this needs a fresh full-byte comparison against the original 106,359-byte package before it can serve as a verified immutable input.

## Safe, reproducible next gate

`analysis/frozen_c6_c7_intake.py` provides an **offline read-only** source inventory and future `verify-staged-c7` command. The latter requires the exact source-declared SHA-256 and file length, parses the tar stream **without extraction**, rejects path traversal/links/duplicates/oversized members, checks the known five deliverable byte lengths, and verifies a complete unique 190-case positive/control roster. Tests use purely fabricated archives and records. The CLI does **not** calculate issue-specificity contingency tests or C7 PC-level pathway validity.

~~~bash
python -m analysis.frozen_c6_c7_intake audit-recorded
python -m unittest tests.test_frozen_c6_c7_intake -v
python -m analysis.frozen_c6_c7_intake verify-staged-c7 \
  "/secure/approved/original/C7_CONTROL_PATHWAY_INTEGRATION_v1.0.tar.gz"
~~~

Only run the third command on a separately approved original archive **outside the Git repository**. Its gate may fail at source-schema verification if the real historical C7 column names differ; do not guess or silently relabel scientific variables to pass.

## What remains substantively open

1. Authenticate frozen C4/C5/C6 per-pair semantic labels and the original C6/C7 archive bytes from an authorized copy.
2. Replay each original *paired* contingency table, the correct exact/asymptotic tests, effect sizes and repository-blocked confidence intervals, maintaining the nine frozen comparisons and 189-review denominator.
3. Independently reconstruct C7's 190-pair / 416-PC pathway crosswalk and check pathway-specific estimates.
4. Keep scanner validity, C2 optimizer Tier-A/distance optimality, final August 29 SQLite authentication, missing 14 historical baseline SARIF, and counterfactual causality as separate gates.

**No completed historical annotations were regenerated after unblinding; no research labels were changed.**
