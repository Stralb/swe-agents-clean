# SHA-authenticated D evidence-export readiness versus unresolved D/D7 labels

**Research checkpoint:** 23 October 2026  
**Status:** original Wits 342-root source-byte crosswalk **PASS**, scientific adjudication **NOT DONE**

**Original source:** Wits read-only `D_COMPLETE_ROOT_PROVENANCE_v1_0/04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_INDEX_342.csv`.  
**Original archival manifest:** Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/04_EVIDENCE_EXPORT/SHA256SUMS.txt`.  
**Existing version-difference source:** [43-row frozen D/D7 ledger](../provenance/d_vs_d7_label_differences.csv).  
**Derived private, source-pinned result:** [43-root channel projection](../provenance/d7_original_evidence_export_channel_crosswalk_20261023.json).  
**Reproducible audit module:** [analysis/d7_evidence_export_channel_gate.py](../analysis/d7_evidence_export_channel_gate.py).

## 1. Independently authenticated original evidence index

Using read-only AServerV6 file reads, the full **47,826-byte** original `D_EVIDENCE_INDEX_342.csv` was reassembled and SHA-256-hashed (with the hashing implementation checked against the `abc` known-answer vector). SHA-256:

`cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6`

This **exactly matches** Wits's archived `SHA256SUMS.txt`. The CSV parses as **342 distinct root evidence-index rows**. Every one of the **43** disputed root IDs from the existing private Git difference ledger maps to exactly one original Wits evidence-index row. These are **authenticated source-index evidence metadata**, not authenticated original D-final and D7 classification files. The 43-row difference ledger's separate pinned Git blob SHA-1 is `93761f8742be9e6171229d60f9498ced8ee3c555`.

The separate archived D evidence-export QC reports **455 producing changes, 342 roots, 191 positive workflows**, with both pass-A and pass-B evidence packets assembled (342 each), no identity leaks, and explicitly `semantic_analysis_performed=false`, `llm_used=false`. Successful export **does not** mean semantic route/tier adjudication was completed.

## 2. Crosswalk: exporter evidence status is not the semantic explanation label

| Status | All 342 original export roots | Among 43 D/D7 disputed roots | Other 299 roots |
| --- | ---: | ---: | ---: |
| `channel_chronology=INCOMPLETE` | **41** | **0** | **41** |
| `channel_chronology=COMPLETE` | **301** | **43** | **258** |
| `channel_external_guidance=URLS_PRESENT_UNFETCHED` | **134** | **18** | **116** |
| `channel_external_guidance=NOT_APPLICABLE` | **208** | **25** | **183** |

**Key correction to earlier narrative:** the **17** disputes that involve the semantic label `INCOMPLETE` all have **exported chronology status COMPLETE**. Hence it is **invalid** to explain those semantic labels as direct translations of an exporter `channel_chronology=INCOMPLETE` value. The latter pertains to evidence retrieval/readiness at a different analysis stage, whereas the former concerns an explanation-tier judgment.

Among the 17 semantic-INCOMPLETE disputes, **six** are associated with unfetched external-guidance URLs and **eleven** with `NOT_APPLICABLE` external guidance. Of the remaining 26 disputes (25 completed-tier differences plus one H/M route difference), twelve have unfetched external URLs and fourteen do not.

In particular, **all four `CROOT-05267-01/02/04/07` D-final T5 → D7 INCOMPLETE roots** have original exporter flags `chronology=COMPLETE` and `external_guidance=NOT_APPLICABLE`. These exported channel flags alone **neither prove T5 is valid nor prove D7's INCOMPLETE is valid**. They narrow the possible explanations for disagreement and show the original coder rationale is indispensable.

The **41 chronology-INCOMPLETE evidence-index roots outside the 43 known disputes** are a separate potential validity issue, not a reason to declare the other 299 labels correct. Until their original tier/route assignments are authenticated, it is unknown whether any were assigned T5 in violation of the frozen codebook or appropriately classified with a lower explanatory grade.

## 2a. Direct test of exporter COMPLETE versus linked-issue availability

A targeted second original-index read found **all 14 root decisions** from the **four scanner-positive workflows whose GitHub issue was created after the PR was opened**. Their source-export statuses are:

| Linked positive workflow | Original D1 roots | Exported chronology | External guidance | Independent issue/root scope |
| --- | ---: | --- | --- | --- |
| Case 5264, LAN-peer feature with later approvals issue | 5 | **5/5 COMPLETE** | All NOT_APPLICABLE | Five roots serve a different feature workstream |
| Case 5267, version-preview feature with later migration issue | 7 | **7/7 COMPLETE** | All NOT_APPLICABLE | Seven roots serve a different feature workstream |
| Case 7682, runtime upgrade and later installer issue | 1 | **1/1 COMPLETE** | NOT_APPLICABLE | Root scope not yet resolved |
| Case 12334, ACP capabilities | 1 | **1/1 COMPLETE** | URLS_PRESENT_UNFETCHED | Issue goal and root are related, but issue postdates PR opening |
| **Total** | **14** | **14/14 COMPLETE** | **1 unfetched** | **12 roots in demonstrably separate PR workstreams** |

This comparison combines the authenticated Wits index with the [four-case issue/PR source inspection](FOUR_LATE_ISSUE_ROOT_GOAL_COVERAGE_20261022.md). The issue-after-PR timestamps came from the later continuation SQLite and public GitHub creation metadata, **not a freshly SHA-authenticated final August SQLite**.

**Methodological interpretation:** an exported `channel_chronology=COMPLETE` is a provenance/readiness field, **not** a signed claim that the issue was available when the agent made the root choice, nor that the issue text covers the root's workstream. All 14 original root packets can have a COMPLETE chronology channel while a later linked issue is not the PR's originating instruction. This is not necessarily a data-export error: chronology collection might be complete even when it establishes an ordering that *rules out* influence from the linked issue at PR start. The relevant root's individual commit may occur after issue creation, so do not extend this into a claim that none of the four late-created issues influenced any later code.

Consequently, D0 semantic H/T/M mechanism classification, T1–T5 explanation sufficiency, and C6 issue-specificity/goal-alignment analyses require **separately source-checked issue existence at the root-introduction time and issue-to-root semantic coverage**, not a boolean exporter COMPLETE filter. The [proposed independent coverage codebook](PROPOSED_ISSUE_TO_ROOT_COVERAGE_CODEBOOK_20261023.md) remains proposed, **not executed**.

## 3. Frozen D0 controls the meaning of T5

The original Wits `D0_PRODUCTION_ROUTE_CODEBOOK_FROZEN_v1.0.md` (archival SHA-256 `d8ad00d3d4903597dcd91a4568e0ca77a3bee1f8951d9f9789d0e10d95e557f4`) requires all materially applicable sources to be checked before `T5` (no independent public explanation found) can be assigned. It expressly distinguishes missing evidence (`INCOMPLETE`) from a completed bounded search producing no explanatory precursor (`T5`).

The Wits deterministic export README also states that `URLS_PRESENT_UNFETCHED` is **not automatically T5-complete**; relevance must be assessed. Conversely, an unfetched URL may be irrelevant, so its presence does not automatically invalidate T5. Export chronology `COMPLETE` is **not** evidence that an issue's exact wording as of every root-producing commit was independently recovered or that a linked issue described the relevant PR workstream.

Thus no canonical adjudication decision follows from the status columns alone.

## 4. Pipeline-stage provenance is distinct from final study-level annotation

Read-only Wits exploration also uncovered:

- `02_PACKETS/D2_PACKET_BUILD_QC.json` and `04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_BUILD_QC.json`: **PASS** for packet/export construction and accounting.
- `02_1_ENRICHED_PACKETS/D21_BUILD_FAIL`: one **earlier, scoped enrichment attempt** failed to locate `STEP2_EVIDENCE_AUDIT_455`; this does not mean the later v1.1 export was unsuccessful.
- `03_D3/D3_BUILD_FAIL`: a **separate proposed D3 execution stage** was blocked by a missing vLLM `.sif` container image. The immediately associated coder-A, coder-B and agreement result directories are empty in the accessible archive.
- `06_ADJUDICATION` and `07_FINAL` directories likewise contain no directly accessible classification output files in this research-artifact tree.

**These scoped failure markers do not prove that no coding or adjudication occurred elsewhere.** They do establish that the public/recovery-facing Wits evidence-export branch is **not an authenticated source of the final 342 semantic labels**. The historical H/T/M and T1–T5 counts must be reported as *source-reported*, version-named results pending original label and adjudication-file recovery.

## 5. Scientific release and recovery priorities

1. Recover both complete 342-root D-final and D7 semantic label datasets and original coder/adjudication rationale, with their raw-byte manifests. Independently regenerate all 43 differences rather than trusting a constructed difference-only ledger.
2. For the **eleven** semantic-INCOMPLETE disputes with exporter `chronology=COMPLETE` and `external_guidance=NOT_APPLICABLE`, inspect root-specific chronology, source applicability, original code and reviewer rationale. Do not guess which tier is correct.
3. Review the **six** semantic-INCOMPLETE disputes with unfetched external guidance for source relevance, date of availability and whether it could have constrained the mechanism. Do not fetch post-change hindsight guidance as if it were prospective instructions.
4. Independently determine explanation-tier assignments for the **41 exporter chronology-INCOMPLETE roots among the otherwise unchanged 299**, specifically whether any were assigned T5. Label agreement does not substitute for evidence sufficiency.
5. Reconcile the four workflow-5267 T5→INCOMPLETE roots with the independently established **issue-to-workstream mismatch** and exact root-introduction chronology. The later migration issue does not describe the preview-update code that supplies these roots.
6. Only then rebuild H/T/M route prevalence, T1–T5 explanation counts and subtype-stratified findings for a manuscript. Retain frozen originals; write any consensus decisions to a separate versioned adjudication ledger.

## 6. Reproducibility commands

Run on the private Git branch using the committed derived projection:

~~~bash
python -m analysis.d7_evidence_export_channel_gate
python -m unittest tests.test_d7_evidence_export_channel_gate -v
~~~

When the authorized **complete original** index CSV is staged outside Git, additionally authenticate raw bytes and all 43 projected channel fields:

~~~bash
python -m analysis.d7_evidence_export_channel_gate --original-index "/absolute/private/D_EVIDENCE_INDEX_342.csv"
~~~

Without `--original-index`, CI checks the committed provenance projection and exact SHA of the private 43-difference ledger; it **does not independently reread the original Wits file**. This Wits original has, however, already been independently reassembled and SHA-verified in the current research session. The fail-closed implementation must not convert an unavailable source into an authenticated CI replay.

**No historical Wits artifacts, Slurm jobs, C1/C2/C6 data, scanner results or D/D7 labels have been modified.**
