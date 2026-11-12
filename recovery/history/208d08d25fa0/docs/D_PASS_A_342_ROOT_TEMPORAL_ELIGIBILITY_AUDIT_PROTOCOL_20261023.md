# Pass-A root-introduction chronology: 342-root offline audit protocol

**Date:** 23 October 2026  
**Status:** **AUDITOR IMPLEMENTED + SYNTHETIC CI PASS; ORIGINAL FULL COHORT NOT RUN**.  
**Target:** original Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/04_EVIDENCE_EXPORT/PASS_A/D_PASS_A_EVIDENCE_342.jsonl` (**25,549,416 bytes**).  
**Original exporter's archived SHA-256:** `4510cd4dacf218c918b82d4dfde4afefee270ba5b147a5558e7dbe87e486e8c0`.  
**Checker:** [`analysis/d_pass_a_chronology_cohort_audit.py`](../analysis/d_pass_a_chronology_cohort_audit.py).  
**Unit tests:** [`tests/test_d_pass_a_chronology_cohort_audit.py`](../tests/test_d_pass_a_chronology_cohort_audit.py).

## Why this check is needed

The original D2 packet index was SHA-256 authenticated and covers 342 roots, 455 producing changes in 191 workflows. Its `explicit_chronology_fields_available` indicator is `False` for **all 342** roots. In the later deterministic v1.1 D evidence export, **301** chronology channels are marked `COMPLETE` and **41** `INCOMPLETE`. The later export's own README says only individual evidence items with `eligible_prechange=YES` may be invoked to explain an original implementation choice; `NO` and `UNKNOWN` cannot.

An immutable-source audit of **case 154, root `CROOT-00154-01`**, identified a material timestamp-attribution error: the first `cumulative_diff_anchor` commit is recorded at **02:38:57 UTC on 2025-11-04**, making the linked issue created at **02:39:26** appear post-change and `ORIGINAL_ISSUE` incorrectly marked `eligible_prechange=NO` for that line. Public GitHub source snapshots show that the exact scanner-primary `phpTagRegex` line only appeared in the next relevant commit **at 02:55:56**, **990 seconds after** issue creation. No historical Wits records were changed; the incorrect inference was retracted in the separate [case-154 chronology audit](CASE154_FALSE_EARLY_ROOT_INTRO_ANCHOR_20261023.md).

One counterexample is a validity problem, not a measured error **rate**. Before reconstructing any prospective issue→mechanism inference, the complete original Pass-A file should be systematically triaged.

## What the auditor will compute (once actual source is staged)

The verifier reads the exact original JSONL **without network or writes**, incrementally SHA-256 hashes every raw byte and rejects any file not matching the archived digest. It parses the 342 `D_ROOT_EVIDENCE_PASS_A_v1.1` records, requiring 342 unique root IDs, **455 PC memberships** and **191 root-bearing workflows**.

The output aggregates **two different levels**:

1. **Exporter stage metadata**: `evidence_completeness.chronology` and counts of item-level `eligible_prechange = YES / NO / UNKNOWN / N/A`; distinguishes evidence-item status from full-root source-channel completeness.
2. **Source-reported event ordering**: `ORIGINAL_ISSUE.created_at` versus `INTRODUCTION_CHRONOLOGY.timestamp` for each root. Reports `ISSUE_CREATED_NO_LATER_THAN_ALL_EXPORTED_ANCHORS`, `ISSUE_CREATED_AFTER_ALL_EXPORTED_ANCHORS`, `MIXED_ANCHORS_OR_SAME_ROOT_MULTIPLE_PCS` and `INDETERMINATE`, preserving multi-PC and unresolved timestamp cases.

It also counts introduction attribution *methods*, *confidence* and *resolution*; counts issue-created-after-PR cases separately; and flags (a) source eligibility `NO` despite issue creation before every exported anchor, (b) `YES` despite some earlier exported anchors, and (c) **all `cumulative_diff_anchor` roots requiring target-code Git inspection**. Root IDs are only emitted when `--list-flagged` is explicitly requested; raw original issue bodies are never output.

**Critical scope:** this is **triage of source-reported timestamps only**. A source `COMPLETE` flag, an `eligible_prechange` item value or a method label is **not** an independently authenticated first scanner-line introduction commit. An issue creation date before a commit is not proof that its exact issue body was available, read by the agent, used in the implementation or security-preventative.

The audit does **not** assign, edit or justify D-final/D7 H/T/M or T1–T5 labels, prove CodeQL warning validity, or use future security advisories as if they were available to the historical agent.

## Reproducible execution using an approved original source copy

Source file remains on Wits unless the owner explicitly stages an **authorized, read-only original copy** in a local environment. The following commands apply to such a separate staged copy; they do not change the original research tree.

~~~bash
python -m analysis.d_pass_a_chronology_cohort_audit \
  --pass-a-jsonl "/absolute/private/D_PASS_A_EVIDENCE_342.jsonl"
~~~

For root IDs of *source-reported* review candidates (not labels or inferred truth):

~~~bash
python -m analysis.d_pass_a_chronology_cohort_audit \
  --pass-a-jsonl "/absolute/private/D_PASS_A_EVIDENCE_342.jsonl" \
  --list-flagged
~~~

Regression tests in CI use **synthetic records**, so a passing CI run does not claim the original 25.5 MB file was available:

~~~bash
python -m unittest tests.test_d_pass_a_chronology_cohort_audit -v
~~~

## Scientific steps following the real 342-root audit

1. **First classify the reported-anchor methods.** Keep resolved, missing and mixed-PC cases separately. Do not assume `cumulative_diff_anchor` means the scanner-primary target line was present in the earliest feature commit.
2. **Review high-impact contradictions first**, especially records whose issue eligibility changes interpretation and those in the 190 matched-positive workflows.
3. **Replay exact code introductions at individual Git commits** for a predeclared, stratified sample or the complete cohort, using scanner-primary source locations, old/new target blobs and Git ancestry; independently verify source-line attribution. Record evidence that a warning's *particular causal mechanism* was first introduced, not simply that a broader feature existed.
4. **Verify issue versions as-of candidate commits** when possible. GitHub issue creation timestamps alone do not authenticate text edits, private agent message receipt or instruction salience.
5. **Quantify the resulting root- and workflow-clustered prevalence** with explicit unknown cases. Only after this step consider rerunning scientifically relevant C6 pathway comparisons and mechanism-selection claims.

### Completion status

- **Completed:** archived SHA pin, full offline reader/validator and failure-focused synthetic tests, source-specific case-154 proof.
- **Not completed:** 342-root original Pass-A file replay, full introduction-timing truth audit, any causal/prompts-evidence reclassification.
- **No original files, D labels, C1/C2/C6 observations, Slurm jobs or scanner outputs were modified.**
