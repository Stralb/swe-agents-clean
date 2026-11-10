# Case 154: a high-confidence cumulative-diff anchor is too early for the scanner-targeted line

**Date:** 23 October 2026  
**Decision:** *Verified root-introduction timing conflict.* Preserve the original Wits records; mark the derived 29-second issue-after-root interpretation **RETRACTED** for this root. Do **not** automatically change the historical `eligible_prechange` item or semantic H/T/M labels.

**Original source:** `CAPHTECH/kiri` [issue #25](https://github.com/CAPHTECH/kiri/issues/25) → [PR #26](https://github.com/CAPHTECH/kiri/pull/26), case `154`, root `CROOT-00154-01`, producing change `P50-PC-0070`.  
[Machine-checkable chronology record](../provenance/case154_original_anchor_vs_target_line_timeline_20261023.json) · [Read-only local Git replay gate](../analysis/case154_root_introduction_timing_gate.py) · [Tests](../tests/test_case154_root_introduction_timing_gate.py)

## 1. Original study source is authenticated; its interpretation is the problem

The complete original **5,023-byte** Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/by_root_A/CROOT-00154-01.json` was read in a single full-file AServerV6 chunk. Its SHA-256

`002e258d355ecd4ffcf63ecdc7bb2e2aa4d414cb11e1807283c0f0be2c9b1558`

matches its entry in the original source `02_PACKETS/SHA256SUMS.txt` **exactly**. The latter 690-entry archive manifest was itself independently SHA-256 rehashed in the previous audit.

The original D2 root summary identifies the scanner-primary changed line in `src/indexer/codeintel.ts`:

~~~typescript
const phpTagRegex = /^(?:\s*|#!\/.*?\n|\uFEFF)*<\?(?:php|=)?/i;
~~~

The original later Wits Pass-A evidence export `D_PASS_A_EVIDENCE_342.jsonl` (total original file **25,549,416 bytes**) begins with case 154. The **entire first JSONL record (79,159 bytes)** was reconstructed from three bounded original Wits byte chunks and parsed. It explicitly records:

- `evidence_completeness.chronology=COMPLETE`.
- `INTRODUCTION_CHRONOLOGY` evidence: **02:38:57 UTC**, `method=cumulative_diff_anchor`, `status=resolved`, `confidence=high`.
- `ORIGINAL_ISSUE` evidence `eligible_prechange=NO`, with issue creation **02:39:26 UTC**.
- Of its 21 item-level evidence records, **11 `YES`, 4 `NO`, 3 `UNKNOWN`, 3 `N/A`** for `eligible_prechange`.
- The export explicitly says `semantic_labels_present=false`, `only_prechange_yes_may_support_H_or_T1_T4=true` and `T5_requires_complete_required_channels=true`.

The **complete 25.5 MB Pass-A JSONL source file was not independently rehashed in this audit**. This source-specific observation is based on the first fully reconstructed item, not an exhaustive 342-root Pass-A eligibility census.

## 2. GitHub target-file snapshots independently refute the recorded target-line timestamp

GitHub's actual issue creation, PR creation, and commit timestamps, together with immutable Git source file blobs, establish:

| Event | UTC on 4 Nov 2025 | Source `phpTagRegex` present? |
| --- | --- | --- |
| True PR base `56c07dc` | Earlier base (time not used) | **No** |
| Initial PHP feature commit [`ffe8f6f`](https://github.com/CAPHTECH/kiri/commit/ffe8f6fee30164d7e0e0a6d52c435d93ce8fbeb4) | **02:38:57** | **No** |
| Issue [#25](https://github.com/CAPHTECH/kiri/issues/25) created | **02:39:26** | Not a commit |
| PR [#26](https://github.com/CAPHTECH/kiri/pull/26) opened | **02:40:13** | Not a commit |
| Intermediate feature commit [`23f2db3`](https://github.com/CAPHTECH/kiri/commit/23f2db3c2e91373b70fb3d7a923c0f0f7842d1e5) | **02:45:52** | **No** |
| Robust PHP-regex commit [`8af3a29`](https://github.com/CAPHTECH/kiri/commit/8af3a292202668f2d3e254fee60cc959a7c126dd) | **02:55:56** | **Yes**, exact matching code |
| PR head `a5024f8` | **03:02:16** | **Yes** |
| PR merged | **03:05:24** | Yes in PR head |

Actual original blob SHA-1 fingerprints for the target file at these five source states are pinned in the [chronology provenance ledger](../provenance/case154_original_anchor_vs_target_line_timeline_20261023.json). GitHub compare endpoints independently show exactly **one commit** between the initial-feature and intermediate snapshots, and exactly **one commit** between the intermediate and regex-introduction snapshots. The `8af3a29` commit message also explicitly says it adds robust regex-based PHP tag detection.

Thus the **source-reported early timestamp (02:38:57) is 17 minutes minus 1 second before the exact target-line commit**. The issue is created **29 seconds after the erroneous early anchor**, but **16 minutes 30 seconds before the actual target-line commit**.

**Crucial reversal:** We initially treated this case as an issue created after its scanner-producing root. That was **incorrect** when the claim is about the particular scanner-targeted `phpTagRegex` line. It is instead a case where *a mechanism-level root-introduction time has been erroneously inherited from an earlier feature-level cumulative-diff anchor*. The original Wits Pass-A `ORIGINAL_ISSUE eligible_prechange=NO` follows the wrong anchor and is **not justified by root-specific publication timing alone**.

The Git commit timestamps are public repository timestamps, not direct recordings of every edit operation. The target line first appears in the fully inspected contiguous feature commit sequence. This is sufficient to refute the original file-line *commit introduction* timestamp; it does not establish precisely when the agent internally considered or typed that line.

## 3. Why this affects the scientific estimand

Issue created **before PR creation** is not a sufficient proxy for issue availability **before every producing change** (different roots may enter the PR at different times). But there is a second, independent failure mode now verified: a producing-change dataset's "introduction commit" may reflect a **feature-level anchor rather than the first commit of the actual scanner-targeted line**. Applying `issue.created_at <= exported_intro_timestamp` as a filter can create false *post-root issue* labels.

Case 154 is **not** one of the two unmatched positives `13918` and `17460`; it belongs to the frozen set of **190 matched positives** by original C1/C2 membership accounting. It is therefore possible for this temporal classification error to affect the empirical interpretation of **matched issue specificity and alignment**, even if no original paired contingency count changes merely by correcting source metadata. The actual size and direction of cohort-wide effects are **not** established from this one root.

The original issue existing **before** the target-code commit is a **necessary temporal condition**, not proof that the agent read it, that the issue body at `02:55:56` matched the current body, or that the issue actually caused the regex. An as-of-commit issue-body snapshot and instruction attestation remain open.

## 4. Release action and exact minimal correction

1. **Do not rewrite frozen labels.** Preserve the exporter timestamp `02:38:57` and its `eligible_prechange=NO` record as historical evidence, adding the corrected target-line attribution to a separate, versioned chronology challenge ledger.
2. **Mark case 154 prospectivity unsettled at the issue-body level,** with *source-event ordering* corrected: issue creation preceded the target-line commit by 990 seconds. Do **not** automatically switch `NO` to `YES`.
3. **Audit actual root-introduction timestamps across the full 342 roots**, stratifying by `cumulative_diff_anchor` and related attribution methods. At minimum, trace exact scanner-primary diff lines or semantic mechanisms through sequential PR commit snapshots to determine when each specific change first entered the patch. Record explicit `UNKNOWN` when no reliable source-introduction commit can be established.
4. For study outcomes, separate (a) issue created before PR, (b) issue body available as-of root, (c) root purpose aligned to that issue, (d) agent received the issue, and (e) retrospective scanner report. Only (a) is measured by the coarse event-ordering study.
5. Preserve all original scanner findings, 190 C2 matches, 342 root IDs, 455 PCs and existing H/T/M/T1–T5 source-reported counts; **recompute** any claim depending on issue-before-root eligibility **only after** root-level chronology is repaired.

## 5. Reproduce

Default CI checks the pinned Wits D2 SHA source metadata, five immutable Git blob references, exact event ordering and nonclaims. It does not reach GitHub or alter Wits:

~~~bash
python -m analysis.case154_root_introduction_timing_gate
python -m unittest tests.test_case154_root_introduction_timing_gate -v
~~~

Optional **read-only independent** replay with an existing local `CAPHTECH/kiri` Git checkout and an authorized exact D2 packet outside GitHub:

~~~bash
python -m analysis.case154_root_introduction_timing_gate \
  --repo-dir "/absolute/local/kiri" \
  --wits-d2-root "/absolute/private/CROOT-00154-01.json"
~~~

This rehashes the original D2 byte file and all five source Git blobs and checks the exact target line at each immutable commit. The separate large Pass-A JSONL has not been copied to the private reproducibility repository.

**Original Wits data, Slurm jobs, GitHub PRs, D-final/D7 labels and scanner datasets remain unchanged.**
