# Original 36-root/131-finding dependency evidence census for workflow 13918

**Research checkpoint:** 23 October 2026  
**Status:** original 36 D2 packet-byte manifests and all canonical-finding memberships recovered; advisory publication census **incomplete**; historical D-final/D7 labels **unrecovered**.  
**Original workflow:** [Pimzino/spec-workflow-mcp PR #173](https://github.com/Pimzino/spec-workflow-mcp/pull/173), merged **19 December 2025 at 13:54:38 UTC**.  
**Scientific reproducibility:** [Original source packet SHA-256 and finding-ID ledger](../provenance/case13918_original_D2_36_packets_131_findings_20261023.json), [fail-closed checker](../analysis/case13918_d2_131_finding_source_gate.py), [tests](../tests/test_case13918_d2_131_finding_source_gate.py).

## 1. Exact observational units and provenance

The 36 original Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/by_root_A/CROOT-13918-01.json` through `...-36.json` files were read in their entirety through AServerV6, without mutation. We extracted each packet's exact `root_id`, `pc_count`, `root_summary`, `Canonical Finding ID(s)` and `Rule ID(s)`. Each separate D2 JSON file was subsequently retrieved as one **complete binary chunk** (each file is under 32 KiB); its **full-file SHA-256 as returned by the Wits source reader**, its byte length, original package name/version and exact canonical finding IDs are pinned in the private provenance ledger.

The corresponding original Wits `D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/SHA256SUMS.txt` was subsequently read in full (**63,478 bytes**), independently SHA-256 hashed (digest `5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b`; SHA-256 implementation checked against the standard `abc` test vector), and parsed as **690 unique archived checksum records**. **All 36** source-returned full-packet SHA-256 values **exactly match the original archived by-root-A packet checksums: 36/36, zero mismatches**. Thus the packet hashes are corroborated by an archived exporter-side manifest, not merely self-consistent with current SSH reads. This is file-identity evidence, **not** semantic route adjudication, prospective warning availability or independent vulnerability validation.

Together the 36 JSON files comprise **319,315 original bytes**. The chunk-level reported SHA values cover each entire D2 file, because `chunk_bytes == total_bytes` for all 36. Those individual D2 hashes are server-returned full-source digests; this checkpoint does **not** claim 36 separate client-side independent SHA rehashes. The optional checker can independently SHA-256 each approved local original JSON file before re-parsing all canonical finding IDs. **The 36 original JSON bytes themselves are not committed to GitHub.**

The distinct original [D1 root-index](D_41_CHRONOLOGY_INCOMPLETE_LOCKFILE_ROOTS_20261023.md) file's complete 66,543 bytes and the original D export-index file's complete 47,826 bytes **were** independently SHA-256 rehashed in earlier checks. The original D1 `A4/B2` root construction fields are **not** D-final/D7 route classification.

| Unit of analysis in this case | Original count | Meaning |
| --- | ---: | --- |
| Linked PR/workflow | **1** | One merged change-set with a genuine issue-specific approvals fix and a large dependency-lockfile diff |
| D1/D2 frozen roots | **36** | Different resolved npm package/version root summaries |
| Producing changes/PCs | **36** | One PC attached to each frozen D2 root |
| Canonical scanner findings | **131** | Original **distinct** `CF-0929` through `CF-1059` labels represented in the original D2 evidence |
| Distinct npm package names | **33** | Three package names each occur in two root/version records |
| Independent verified vulnerabilities | **Not established** | Scanner/advisory records do not prove reachability, independent defects or exploitability |
| Independently verified discretionary agent choices | **Not established** | One lockfile resolution can produce multiple version entries and root records |

The **131 canonical finding IDs cover every integer from `CF-0929` through `CF-1059` exactly once**, without a missing or repeated canonical identifier. This is an exact *original source-index membership count*, not a newly run scanner finding count.

## 2. Scanner multiplicity is highly clustered within the 36 roots

| Root / dependency | Canonical scanner findings |
| --- | ---: |
| `CROOT-13918-09` — `hono@4.11.1` | **34** |
| `CROOT-13918-06` — `dompurify@3.3.1` | **17** |
| `CROOT-13918-07` and `-08` — separate `fast-uri` versions | **5 each** |
| `CROOT-13918-19` — `vite@7.3.0` | **5** |
| Other 31 roots | **65 combined** |
| **All 36 roots** | **131** |

The top two roots alone account for **51/131 = 38.9%** of recorded scanner findings. Ten of the 36 roots have only one canonical finding.

This shows why finding-level, producing-change-level, root-level and workflow-level frequencies are **not interchangeable**. Counting multiple advisories on one npm version as separate independently preventable coding decisions would create pseudo-replication. Conversely, the frozen D1/C6 convention deliberately represents each of the 36 package-version changes as a separate *singleton-PC root*; we preserve those root identities and do not merge or recode historical research records.

## 3. Ten CVE identifiers recur across different lockfile-version roots

The original D2 `Rule ID(s)` fields identify **the same CVEs on two distinct root packets** for each of the following three npm packages:

| Package | Two resolved versions / original roots | Repeated CVE identifiers |
| --- | --- | ---: |
| `fast-uri` | `3.1.0` (`-07`) and `2.4.0` (`-08`) | **5** |
| `minimatch` | `9.0.5` (`-29`) and `10.1.1` (`-30`) | **3** |
| `picomatch` | `4.0.3` (`-32`) and `2.3.1` (`-33`) | **2** |
| **Total** | **Six root packets** | **10 distinct CVE IDs, each repeated across two roots** |

The duplicate-CVE check is based on **explicit CVE strings**, not on guesses that different GHSA IDs refer to the same defect. It establishes at least this much nonindependence: **canonical finding IDs can differ across roots while referencing the same CVE**. That does not mean the two resolved versions are duplicates of one source location or that both represent the same exploit exposure. It means the **unique-CF count of 131 must not be labelled 131 unique vulnerabilities**.

## 4. Even three CVE-2025 designations postdate the original 2025 PR

The complete source-backed `Rule ID(s)` census contains **three explicitly CVE-2025-labelled advisory associations**. Their **specific public GitHub GHSA publication dates** are all after the PR merge:

| Original root/package | CVE and public GHSA | Advisory published | UTC calendar-day gap from PR merge |
| --- | --- | --- | ---: |
| `-05`, `ajv@8.17.1` | [CVE-2025-69873 / GHSA-2g4f-4pwh-qvx6](https://github.com/advisories/GHSA-2g4f-4pwh-qvx6) | **11 Feb 2026** | **54 days** |
| `-11`, `lodash-es@4.17.22` | [CVE-2025-13465 / GHSA-xxjr-mmjv-4gpg](https://github.com/lodash/lodash/security/advisories/GHSA-xxjr-mmjv-4gpg) | **21 Jan 2026** | **33 days** |
| `-35`, `qs@6.14.0` | [CVE-2025-15284 / GHSA-6rw7-vpxm-498p](https://github.com/ljharb/qs/security/advisories/GHSA-6rw7-vpxm-498p) | **30 Dec 2025** | **11 days** |

For chronology comparisons, a CVE's numeric **year is not a disclosure date**. It can reflect reservation/identifier allocation and is neither proof of public availability nor defect introduction in that calendar year. A public GHSA publication date after PR merge does not rule out earlier private disclosure or independent earlier guidance, and does not establish actual exploitability.

Do not infer that all 131 findings were first published after merge from their CVE-number years. The **all-advisory-date census remains unfinished**, including GHSA references without a CVE, multiple advisories for the same package root, and private/public embargo considerations.

The [previous seven-advisory audit](RETROSPECTIVE_DEPENDENCY_ADVISORY_TEMPORAL_VALIDITY_20261023.md) covers selected examples in **six workflows** (five of them in the original C2 matched-positive cohort). This 36-packet audit is a **complete source-membership census for one unmatched workflow**, not a retrospective warning-publication census for all 190 matched workflows.

## 5. Consequences for the statistical and causal claims

**A. Full historical case accounting:** Retain `13918` and its original 36 root IDs in the 342-root study; describe its unusually large dependency-lockfile role. It was originally **one of two unmatched positives** under the frozen 190-pair C2 selection and therefore **does not contribute directly to the original C6 paired 190 comparisons**. Do not subtract it again from historical C6 statistics.

**B. Root/tier semantics:** The 36 dependency-version roots are plausible D0 **T (toolchain/mechanical)** candidates, but npm lockfile syntax does not prove resolver inevitability. An agent may have chosen a package or version deliberately. Do not recode these as T, M or T5 without original complete D-final/D7 classifications and source-level mechanism evidence.

**C. Dependence:** In any full-root prevalence analysis, explicitly contrast `342 roots`, `191 root-bearing positive workflows`, `455 producing changes` and the *correctly measured scanner-finding denominator*. Group findings by root and roots by workflow/repository, rather than treating 131 findings from one lockfile update as iid. The global scanner-finding denominator cannot be reconstructed just from this particular 131-ID subset.

**D. Retrospective versus prospective intervention:** Any condition inserting a later published advisory into a 2025 issue is a **hindsight oracle**, not an as-of-2025 warning retrieval process. An observed warning disappearing after patch regeneration is not proof of exploit elimination or equivalent target functionality.

## 5a. Adversarial root-prevalence robustness (conditional on historical totals)

The original **D-final** (`H=5,T=103,M=234`) and **D7** (`H=6,T=103,M=233`) top-level counts each sum to **342** roots. We do **not** know the actual complete D-final/D7 labels of the **36** roots in case 13918 or the **five** other exporter-chronology-incomplete roots, and the original full label files are not independently authenticated.

For each exclusion scope of size `k`, allow *any* allocation of the excluded roots among H/T/M consistent with the source-reported global totals. If `M` is the original number of mechanism-selection roots and `N=342`, the remaining mechanism-selection proportion must lie within

\[
\left[
\frac{M-\min(M,k)}{N-k},\ 
\frac{M-\max(0,k-(N-M))}{N-k}
\right].
\]

These are **deterministic partial-identification bounds**; no labels were imputed, no historical observations deleted and no sampling-based confidence intervals calculated.

| Historical version | Exclude 36 original case-13918 roots | Exclude all 41 chronology-incomplete roots |
| --- | ---: | ---: |
| D-final (`M=234`) | **198/306–234/306 = 64.7%–76.5%** | **193/301–234/301 = 64.1%–77.7%** |
| D7 (`M=233`) | **197/306–233/306 = 64.4%–76.1%** | **192/301–233/301 = 63.8%–77.4%** |

**Robust descriptive conclusion:** under **either historical reported labeling version**, the **M-route majority** cannot disappear merely by excluding any 36 or 41 roots of these sizes—even if *all* removed roots were originally M. The overall exact M percentage is nonetheless **sensitive** to which category these roots truly occupy, and the missing individual route labels must still be recovered.

This is **not** evidence that the original T1–T5 explanation tiers are stable, that all M mechanisms were discretionary, that the linked issue was an agent's actual instruction, or that scanner warnings were real exploitable vulnerabilities. The 36/41 exclusions are hypothetical sensitivity checks only. They do not change the original 190 matched C6 pairs and should not be described as a valid exclusion criterion established before study analysis.

See [the exact integer-bound implementation](../analysis/d_lockfile_outlier_prevalence_bounds.py) and its unit tests. The result is conditional on the *source-reported* full historical H/T/M totals and would need recomputation if a new adjudicated classification disagrees.

## 6. Reproduce source membership

Default CI runs against only the private committed ledger, its source full-file checksum manifest and previously source-verified chronology/paired-control manifests:

~~~bash
python -m analysis.case13918_d2_131_finding_source_gate
python -m unittest tests.test_case13918_d2_131_finding_source_gate -v
~~~

To **independently re-SHA and re-parse all 36 original source files**, stage approved exact original Wits JSON files `CROOT-13918-01.json` through `CROOT-13918-36.json` together outside Git, then run:

~~~bash
python -m analysis.case13918_d2_131_finding_source_gate --d2-root-dir "/absolute/private/original_Wits_D2_root_JSON" \
  --archived-sha-manifest "/absolute/private/original_Wits_D2_SHA256SUMS.txt"
~~~

The checker refuses missing or symlinked original files, wrong byte lengths/individual hashes, changed canonical IDs, changed package versions, missing/duplicated canonical findings, inconsistent original C1/C2 membership, unverified route labels, or attempts to promote this 131-finding source count into a vulnerability count.

**Wits original files, Slurm jobs, scanner results, C1/C2/C6/D1 root IDs and all historical D-final/D7 labels remain unchanged.**
