# D vs D7 classification disagreement: scoped audit — 22 October 2026

**Status: unresolved. No canonical label set selected.**

The existing 43-row `provenance/d_vs_d7_label_differences.csv` was re-evaluated as a **committed comparison table** (Git blob SHA `93761f8742be9e6171229d60f9498ced8ee3c555`). It contains **43 unique roots**, no duplicate identifiers, and all dispositions remain `UNRESOLVED`. This does **not** independently retrieve or re-label the original D and D7 case packets.

| Recorded transition | Number |
| --- | ---: |
| Changed tier, unchanged route M | **42** |
| Changed route M/T1 → H/NA | **1** |
| Original `INCOMPLETE` → D7 numbered tier | **5** |
| Original numbered tier → D7 `INCOMPLETE` | **12** |

The single route switch concerns `CROOT-00649-01`. The D-final published top-level totals were H=5, T=103, M=234; the D7 counts are H=6, T=103, M=233, consistent with the **single route transition**. These totals are inherited from the prior historical accounting; the 43-row table itself is a difference-only table and cannot independently reconstruct all 342 canonical root labels.

## Why this blocks reproducibility

This is **not** merely a formatting difference. At least 43 reported root-level tiers disagree; the introduction/removal of `INCOMPLETE` assignments can change subtype denominators, and the one M→H switch changes route prevalence. Do **not** silently choose D7 because it is later, or D-final because it is frozen first. Results conditioned on T1–T5 or top-level routes must name the label version, or exclude unresolved conclusions until an adjudication audit establishes the canonical mapping.

Required closure for open item `P-001`: source D and D7 complete classification CSV identities, per-root adjudication reasons, correction ledger and exact transformation script/version. The Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/07_FINAL` and `06_ADJUDICATION` directories exposed no directly inspectable files in the current read-only listing. No attempt was made to reconstruct private human labels from conjecture.

The machine-readable **difference-table-derived** distribution is in `provenance/d_vs_d7_conflict_distribution_20261022.json`. No original Wits files, jobs or classification values were modified.
