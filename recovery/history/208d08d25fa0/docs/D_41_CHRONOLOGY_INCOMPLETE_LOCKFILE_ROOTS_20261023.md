# Chronology-INCOMPLETE roots: 41 dependency-lockfile observations across six workflows

**Research checkpoint:** 23 October 2026  
**Classification status:** source-accounting **verified**; original H/T/M and T1–T5 *not adjudicated*  
**Source manifest:** [41-root original D source-index crosswalk](../provenance/d_chronology_incomplete_41_lockfile_census_20261023.json)  
**Fail-closed staged-source checker:** [analysis/d_chronology_lockfile_concentration_gate.py](../analysis/d_chronology_lockfile_concentration_gate.py)

## 1. An apparently substantial 41-root gap is concentrated in one lockfile

The original, independently SHA-authenticated [D evidence export](D_EXPORT_SHA_AUTHENTICATED_D7_CHANNEL_CROSSWALK_20261023.md) counts 41/342 (12.0%) root evidence records as `channel_chronology=INCOMPLETE`. Joining the full original index to its `case_id`, then inspecting D1 root summaries and source D2 mechanism packets, resolves their actual observational types:

| Original scanner-positive workflow | Evidence roots with incomplete chronology | Source-supported producing mechanism |
| --- | ---: | --- |
| `13918` — `Pimzino/spec-workflow-mcp` | **36** | 36 individual package/version updates in `package-lock.json` |
| `00664` — `vercel-labs/skills` | 1 | `rollup@4.56.0` lockfile version |
| `09942` — `getgauge/taiko` | 1 | `adm-zip@0.5.17` lockfile version |
| `12898` — `yagop/node-telegram-bot-api` | 1 | `fast-uri@3.1.2` lockfile version |
| `12925` — `ericblade/quagga2` | 1 | `systeminformation@5.29.1` lockfile version |
| `16311` — `less/less.js` | 1 | `lodash@4.17.23` lockfile version |
| **Total** | **41** | **All 41 are one-PC `package-lock.json` dependency-version roots** |

The five non-13918 cases each have original blind-A D2 root packets explicitly identifying `Finding Family = Dependency vulnerability` and source `package-lock.json` changes. The **36/41 = 87.8%** concentration comes from a single PR; those 36 roots represent **36 distinct package entries/producing changes**, not 36 independent workflows or automatically 36 discretionary agent decisions.

The source-index's 41 flags span **six of the 191** mapped positive workflows (3.1% of those workflows), a fundamentally different population from 41/342 roots. All 41 have `pc_count=1`, and none appears in the frozen [43-row D-final versus D7 classification difference ledger](../provenance/d_vs_d7_label_differences.csv).

Of the 41, exactly **three** have external-guidance URLs present but unfetched. The other 38 have `NOT_APPLICABLE`; project instructions are recorded `COMPLETE` for three and `NOT_APPLICABLE` for 38. These evidence-channel flags describe export readiness; they are **not** semantic H/T/M classifications.

## 2. Primary evidence was authenticated independently

**D-export index:** original Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_INDEX_342.csv`; 47,826 bytes; independent SHA-256:

`cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6`

**D1 full root index:** original Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/D1_ROOT_INDEX_342.csv`; **66,543 bytes**, retrieved in three raw binary chunks, decoded without relying on broken partial UTF-8 byte boundaries, then SHA-256-checked independently with an implementation passing the `abc` known-answer vector:

`ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3`

The D1 digest matches the independently recorded [C1→C5/C6/D1 provenance audit](../provenance/c1_c5_c6_d1_crosswalk_readonly_audit_20261022.json). Its actual original rows `CROOT-13918-01` through `CROOT-13918-36` were all inspected. Each `Root Summary` explicitly says **include a named dependency version in `package-lock.json`**, and every one has `PC Count=1`. The D1 source's effective **A4/B2** labels are *earlier C-stage annotation labels*, **not** the later D0 route `T` or a T1–T5 explanation tier. Do **not** reinterpret A4/B2 as an independently recovered D classification.

For the other five roots, the original D2 packets were read directly and their mechanism and package/version inspected separately. The three export/index population sources together establish the 41-row membership and mechanism family. The underlying npm-resolver execution, advisory database and original semantic D-route labels have **not** been independently replayed.

### C6 root-construction confirmation

The **original Wits `C6_ROOT_CENSUS.csv`** was independently read for all **36** case-13918 records. Their *root-boundary construction* (a different stage from D0 route/explanation classification) is uniform:

| Original C6 field | Verified for all 36 |
| --- | --- |
| PC Count | `1` |
| Merge Rationale | `singleton PC` |
| Final Source | `A_B_AGREEMENT` |
| Subproblem | Dependency resolution / version selection |
| Root Summary | Named version in `package-lock.json` |

The original C6 source had **previously attested** full-file SHA-256 `97e989ef8b3f86413fc821d97c78a15701bdd8e2cb4fdb020ffdc64c4554762c`; this focused C6 read **did not rehash its complete 179,190-byte file**. The C6 source shows the 36 one-PC boundaries are intentional in the frozen root grouping, rather than a clerical duplicate; `A_B_AGREEMENT` is evidence of *root construction agreement*, **not** independent semantic D-route adjudication, C6 matched-effect agreement, or 36 independent agent choices.

This reinforces two compatible reporting obligations: **preserve all 36 original root records** for reproducibility, and **add workflow-/lockfile-event-aware sensitivity analysis** rather than implying 36 independent prompt-to-decision events.

## 3. Case 13918 is a lockfile-heavy PR with a legitimate issue-specific application fix

The linked [issue #172](https://github.com/Pimzino/spec-workflow-mcp/issues/172), created **19 December 2025 at 06:14:52 UTC**, reports `PathUtils.translatePath is not a function` in approvals tooling. [PR #173](https://github.com/Pimzino/spec-workflow-mcp/pull/173) opened at **12:30:23 UTC** and merged at **13:54:38 UTC** that day, implementing defensive `safeTranslatePath` handling and regression tests. Its public PR description contains a `COPILOT ORIGINAL PROMPT` issue-description section, corroborating that the issue was deliberately referenced in PR task context. This alone does not provide authenticated private model messages or prove every added dependency had a deliberate security rationale.

GitHub's read-only **base-to-head comparison**, `ee931da4b577e8893191b8f1fb6b1a9612f640a9` to `45d7cd565c5b540643ef7470bfd08209e99681f2`, reports exactly three changed files:

| Changed file | Additions | Deletions | Changed lines |
| --- | ---: | ---: | ---: |
| `package-lock.json` | 2,225 | 8,226 | **10,451** |
| `src/tools/__tests__/projectPath.test.ts` | 49 | 0 | 49 |
| `src/tools/approvals.ts` | 24 | 3 | 27 |

The lockfile's **10,451 changed lines** are not all security findings and are not evidence of 10,451 independent bug-producing decisions. The frozen dataset identifies 36 particular version changes as scanner-producing roots within that much larger patch. **Whether the 36 resolved dependency versions are truly mechanically entailed by an npm install or were chosen through higher-level package/configuration decisions remains to be proven.** Only original repo manifests, true-base/head resolver inputs, tool versions and installation history can resolve it.

## 4. Matched C6 analysis: the 36-root outlier is outside the 190-pair design

The independently source-crosswalked [original C1/C2 membership audit](C1_C2_CROSSFILE_RECONCILIATION_20261022.md) records **two** unmatched C1 scanner-positive workflows: **13918** and **17460**. Consequently, the **36-root outlier from case 13918 does not appear on the positive side of the 190 C2 matched pairs**. It must not be "excluded" again as though it contributed to the original nine paired C6 comparisons.

The remaining **five** chronology-incomplete-root workflows are not among those two unmatched positives. This does not by itself identify all their paired control labels or demonstrate that original C6 issue-specificity coding was valid. A matched workflow observation still differs from a root decision.

This also means the 36-root concentration poses primarily a **root-level prevalence, source completeness and mechanism-selection estimand** concern rather than explaining the observed matched-C6 omnibus findings.

## 5. Scientific implications and next adjudication gate

The **frozen D0 production-route codebook** defines `T` as toolchain/mechanical when root behavior follows from dependency resolution, lockfile generation or equivalent tooling **without a meaningful mechanism choice at that root**. All 41 source-observed lockfile version changes are thus **plausible T candidates**, but `package-lock.json` syntax alone does **not** prove that a particular package/version was mechanically inevitable: an agent can intentionally pin, upgrade or replace a dependency. The recovered D1 A4/B2 codes do not resolve this.

**Do not unilaterally assign `T`.** Recover the original complete D-final and D7 classifications, exact mechanism-level rationale, and dependency-resolution circumstances before selecting a canonical route or computing M-conditional T1–T5 denominators. A `T5` classification is relevant **only if** a root was genuinely classified M; the mere evidence-export flag `chronology=INCOMPLETE` does not independently establish a T5 violation.

Recommended ordered checks:

1. Recover D-final and D7 H/T/M route labels for **all 41** and list any unexpected M/T5 or H assignments. If all are correctly T, the 41 chronology flags should not automatically block M-specific T5 conclusions, although other codebook evidence gaps may.
2. Treat 13918 as **one influential workflow** with 36 distinct dependency-location roots when describing prevalence. Report both root- and workflow-level denominators, and a sensitivity that removes or isolates case 13918 **from root-level distributions only**, preserving the frozen 342-root census.
3. Verify each dependency/version's true-base/head manifest and resolver provenance before calling it *agent-selected*, *mechanically implied*, *security-failing* or *independently preventable*.
4. Preserve the five other root-level dependency examples and their source-missingness statuses; do not generalize an npm lockfile case to application control-flow choices.
5. Reassess the 43 separate D/D7 semantic discrepancies in their own adjudication process, since **none overlaps** these 41 exporter chronology flags. Source exporting and semantic annotation are separate verification layers.

## 6. Reproduce without leaking private originals

Commit-only consistency gate (checks stored independent source observations and frozen C1/C2, D/D7 ledgers):

~~~bash
python -m analysis.d_chronology_lockfile_concentration_gate
python -m unittest tests.test_d_chronology_lockfile_concentration_gate -v
~~~

With **explicitly approved, separately staged original copies** outside Git, also re-SHA and recompute all 41 missing-chronology root IDs, their exact one-PC D1 summaries and evidence flags:

~~~bash
python -m analysis.d_chronology_lockfile_concentration_gate \
  --d1 "/absolute/private/D1_ROOT_INDEX_342.csv" \
  --evidence-index "/absolute/private/D_EVIDENCE_INDEX_342.csv"
~~~

The checker refuses mismatched source SHA-256, partial sources, absent or mutated 41-root membership, duplicate IDs, incorrect case-13918 data, unmatched-pair drift, or a false claim of original H/T/M adjudication. CI without private inputs cannot claim an independent live Wits reread.

**No Wits research files, Slurm jobs, original D/D7 labels, C1/C2/C6 observations or scanner findings were modified.**
