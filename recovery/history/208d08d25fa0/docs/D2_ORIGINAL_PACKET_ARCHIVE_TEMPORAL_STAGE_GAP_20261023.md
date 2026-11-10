# Source-authenticated D2 packet index and chronology-evidence stage boundary

**Checkpoint:** 23 October 2026  
**Audit status:** exact original D2 index raw-byte SHA-256 **PASS**; original archived 690-entry checksum manifest SHA-256 **PASS**; later D evidence-export index full SHA-256 **PASS**; final D-final/D7 semantic label authentication **OPEN**.

[Derived private crosswalk](../provenance/d2_packet_index_342_archived_stage_coverage_20261023.json) · [Source-locked replay gate](../analysis/d2_packet_index_archival_stage_gate.py) · [Tests](../tests/test_d2_packet_index_archival_stage_gate.py)

## 1. Three authenticated sources, three distinct claims

| Original Wits source | Bytes | Independently confirmed SHA-256 | What it establishes |
| --- | ---: | --- | --- |
| `02_PACKETS/D2_PACKET_INDEX_342.csv` | **35,656** | `2e525ebb3af2a30a2276d4cc306a7c5eb92b42df93b2e11d078eb911ba633305` | Root-to-blinded-coder-alias mapping and **D2-era availability flags** |
| `02_PACKETS/SHA256SUMS.txt` | **63,478** | `5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b` | Archived per-file **source fingerprints**, not coder outputs |
| `04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_INDEX_342.csv` | **47,826** | `cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6` | Subsequent v1.1 **export channel completeness statuses**, not semantic labels |

The complete first file was retrieved in two original binary chunks and independently SHA-256 rehashed, matching the digest in the original second file. The D2 checksum archive has **690 unique entries**: **342 `by_root_A/CROOT-xxxxx-xx.json`**, **342 `by_root_B/DRxxxx.json`** and exactly six exporter/control files (`D2_CODER_A_PACKETS_342.jsonl`, `D2_CODER_B_PACKETS_342.jsonl`, `D2_LEAKAGE_AUDIT.json`, `D2_PACKET_BUILD_QC.json`, `D2_PACKET_INDEX_342.csv`, `D2_SEALED_B_ALIAS_MAP.csv`).

**Every one** of the 342 D2 index root IDs has an A-packet path in the archived manifest; **every one** of the 342 unique blind B aliases has a B-packet path; and the 342 root IDs exactly match those in the later export index. No alias collisions or missing checksum paths were found.

**Limit:** merely recording all 684 packet paths in the historical archive does **not** mean all 684 JSON byte bodies were newly read and independently rehashed. The separate [case-13918 audit](CASE13918_D2_ORIGINAL_36_ROOT_131_FINDING_CENSUS_20261023.md) has verified all **36** original A packet digests against this archive. The other A and blind B JSON payloads remain archived-file records, not newly authenticated bytes, and **none** of this authenticates later D-final/D7 coding decisions.

## 2. The D2 index and later export do not use interchangeable chronology measures

| Data flag | Original 342-root record count |
| --- | ---: |
| D2 packet `issue_title_available=True` | 342 |
| D2 packet `requested_goal_evidence_available=True` | 342 |
| D2 packet `exact_producing_diff_available=True` | 342 |
| D2 packet `repository_search_evidence_available=True` | 342 |
| D2 packet `dependency_toolchain_evidence_available=True` | 342 |
| D2 packet `counterfactual_evidence_available=True` | 342 |
| D2 packet `phase2_source_reference_available=True` | 342 |
| **D2 packet `explicit_chronology_fields_available=True`** | **0** |
| **D2 packet `explicit_phase7_correction_evidence_available=True`** | **18** |
| Later v1.1 export `chronology=COMPLETE` | **301** |
| Later v1.1 export `chronology=INCOMPLETE` | **41** |

The D2 QC and independent audit both report 342 A/B evidence packets, 455 producing-change memberships and no identity leaks, while explicitly tracking only **18** original D2 packets with Phase-7 correction evidence. Those archived QC files do not claim a completed semantic D-final/D7 classification run.

**Interpretation:** `explicit_chronology_fields_available=False` in the D2 packet index means the D2 exporter did **not flag explicitly serialized chronology fields as available**. It does **not** establish that no dates, source links or temporal clues existed *anywhere* inside longer text fields or external GitHub histories. Separately, the later exporter uses a `chronology` *channel-status* field. The **301 complete flags** could reflect a different set of source materials or completeness criteria. Without original, independently traced issue/commit events, `COMPLETE` alone cannot establish that the linked issue was available before a specific mechanism decision.

The [four issue-after-PR positive workflows](D_EXPORT_SHA_AUTHENTICATED_D7_CHANNEL_CROSSWALK_20261023.md) already demonstrate why this is not academic: **14/14 source evidence-export roots** have `chronology=COMPLETE`, despite those linked issues being created after PR opening; **12** roots serve workstreams different from the later issue-specific fix. Issue-to-root prospective availability requires its own source-timed check.

## 3. Phase-7 correction evidence is not the D-final versus D7 disagreement population

The 18 original D2 packets whose index marks `explicit_phase7_correction_evidence_available=True` overlap the frozen 43-row unresolved D/D7 difference ledger in **only six roots**:

`CROOT-00181-01`, `CROOT-04309-01`, `CROOT-05264-03`, `CROOT-08147-01`, `CROOT-15703-01`, `CROOT-18777-01`.

The other **37/43** disputed roots have no explicit Phase-7 correction flag in the **earlier D2 packet index**, while **12/18** flagged roots show no label change between those two historical versions. Every one of the 18 flagged roots happens to have `chronology=COMPLETE` in the later export index.

**Interpretation:** the flag only says that a particular source correction was explicitly available to this earlier evidence-building process. It is **not a universal reconciliation marker, independent second-coder agreement, temporal validity test or proof that the eventual semantic classification is correct**. Conversely, absence of a disagreement is not evidence of correct labeling.

The difference ledger is a comparison of two historical versions, not an original exhaustive human adjudication artifact; the full source D-final and D7 342-root labels remain unavailable through the restricted research-artifact tree.

## 4. Original later-export policy makes prospective eligibility a separate field

The original Wits `04_EVIDENCE_EXPORT/README_D_EVIDENCE_EXPORT.md` states the operative evidence rule: **only evidence items explicitly marked `eligible_prechange=YES` may support explanations of the original implementation choice**. Items marked `NO` may not; `UNKNOWN` requires caution and cannot establish a chronology-safe cause. The same README explicitly says **the export performs no semantic H/T/M or T1–T5 classification**.

A *limited spot inspection* of the original **25.5 MB Pass-A evidence JSONL** corroborated the distinction between export completeness and *item-specific* eligibility. Its leading packet schema `D_ROOT_EVIDENCE_PASS_A_v1.1` includes `analysis_rules.only_prechange_yes_may_support_H_or_T1_T4=true`, alongside evidence items independently marked `eligible_prechange=YES`, `NO` and `N/A`; for example, the producing change/diff evidence item is marked `NO`. The complete Pass-A 25.5 MB payload was **not** streamed and audited here, so this is a schema/example check only, **not** a measured whole-corpus count of `eligible_prechange` classifications.

A post-change warning or an observed producing diff may be essential for identifying what *happened*; under this codebook it must not be re-described as information known to the agent *before implementation*. For paper claims about issue clarity causing mechanism selection, the prospective root-to-issue timing/coverage check remains independent.

## 5. Reproducibility and release priority

Default CI checks the private, source-recorded crosswalk, original D/D7 difference-ledger Git blob and explicit nonclaims:

~~~bash
python -m analysis.d2_packet_index_archival_stage_gate
python -m unittest tests.test_d2_packet_index_archival_stage_gate -v
~~~

When the user authorizes **exact staged original bytes outside Git** for all three files, the checker can independently rehash their SHA-256 and rebuild every A/B alias and disputed-source overlap:

~~~bash
python -m analysis.d2_packet_index_archival_stage_gate \
  --d2-index "/absolute/private/D2_PACKET_INDEX_342.csv" \
  --later-export-index "/absolute/private/D_EVIDENCE_INDEX_342.csv" \
  --archived-sha-manifest "/absolute/private/D2_SHA256SUMS.txt"
~~~

**Pending scientific release gates:** recover original complete D-final and D7 labels/coding rationales; reconcile the 43 disagreements; check issue existence and exact root-purpose alignment at root-producing commit time; verify `eligible_prechange` provenance; recover original C6 paired master, final frozen SQLite and historical scanner baseline SARIFs. These are not closed by verified source packet inventory.

**No Wits original files or jobs, historical root IDs, matching pairs, scanner evidence, or semantic label assignments were modified.**
