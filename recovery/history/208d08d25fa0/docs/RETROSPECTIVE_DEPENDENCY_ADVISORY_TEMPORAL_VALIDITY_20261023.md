# Retrospective dependency advisories versus PR-time security knowledge

**Audit checkpoint:** 23 October 2026  
**Status:** `SEVEN_SOURCE_LINKED_POSTMERGE_ADVISORY_EXAMPLES` — **not a census of all warnings, not a prospective scanner replay, and not an adjudication of H/T/M.**

[Machine-checkable seven-case ledger](../provenance/seven_postmerge_advisory_publication_cases_20261023.json) · [Fail-closed audit](../analysis/seven_advisory_temporal_replay_gate.py) · [41-root original-source study](D_41_CHRONOLOGY_INCOMPLETE_LOCKFILE_ROOTS_20261023.md)

## 1. Why the distinction matters

An advisory-linked dependency exposure identified by a modern scanner in a historical base→PR patch can be genuine **retrospective risk evidence**, even when the vulnerability's **specific public advisory did not exist when the PR was merged**. These two observations are not contradictory.

However, a historical task, agent or developer cannot be assumed to have possessed a specific GHSA/CVE warning *before that advisory's publication date*. An experiment that injects the actual later warning into a historical issue is explicitly **hindsight-oracle information**; such an intervention may test whether additional security knowledge could have changed the patch, but does **not** establish that the historical agent could have retrieved that particular warning as-of implementation.

The timing of **public advisory publication** is distinct from (a) the latent defect's first presence, (b) any earlier private disclosure, (c) other publicly available security guidance, (d) source-code exploitability, (e) detector coverage at PR time and (f) the actual prompt supplied to the agent. None of these six questions is resolved solely by the publication date.

## 2. Original Wits D2 → public PR merge → upstream advisory cross-check

Seven *specifically identified* source-advisory pairs were selected from the 41 roots marked exporter chronology `INCOMPLETE`. Each original Wits D2 root packet explicitly associates the package/version and named GHSA/CVE. The corresponding PR's actual merge timestamp was retrieved from public GitHub PR metadata. The named advisory's publication date was checked against the upstream/GitHub-reviewed advisory page.

| Original root | Source package/version | Original PR merge (UTC date) | Specific advisory and public date | Date gap |
| --- | --- | --- | --- | ---: |
| `CROOT-13918-01` | `@babel/core@7.28.5` | 2025-12-19 | [GHSA-4x5r-pxfx-6jf8](https://github.com/babel/babel/security/advisories/GHSA-4x5r-pxfx-6jf8) — 2026-06-13 | **176 d** |
| `CROOT-13918-36` | `ws@8.18.3` | 2025-12-19 | [GHSA-58qx-3vcg-4xpx](https://github.com/websockets/ws/security/advisories/GHSA-58qx-3vcg-4xpx) — 2026-05-12 | **144 d** |
| `CROOT-00664-01` | `rollup@4.56.0` | 2026-01-27 | [GHSA-mw96-cpmx-2vgc](https://github.com/advisories/GHSA-mw96-cpmx-2vgc) — 2026-02-23 | **27 d** |
| `CROOT-09942-01` | `adm-zip@0.5.17` | 2026-07-07 | [GHSA-xcpc-8h2w-3j85](https://github.com/advisories/GHSA-xcpc-8h2w-3j85) — 2026-07-10 | **3 d** |
| `CROOT-12898-02` | `fast-uri@3.1.2` | 2026-06-25 | [GHSA-4c8g-83qw-93j6](https://github.com/advisories/GHSA-4c8g-83qw-93j6) — 2026-06-29 | **4 d** |
| `CROOT-12925-01` | `systeminformation@5.29.1` | 2026-01-17 | [GHSA-9c88-49p5-5ggf](https://github.com/advisories/GHSA-9c88-49p5-5ggf) — 2026-02-17 | **31 d** |
| `CROOT-16311-01` | `lodash@4.17.23` | 2026-03-13 | [GHSA-r5fr-rjxr-66jc](https://github.com/advisories/GHSA-r5fr-rjxr-66jc) — 2026-03-31 | **18 d** |

The day gaps are **differences between UTC calendar dates**, not precise publication-to-merge elapsed hours. Where available, the table uses upstream/maintainer advisory publication dates, not later GitHub advisory database ingestion dates. In the `adm-zip` case, the source is GitHub's advisory-database publication on July 10.

**Observed from these selected seven root/advisory pairs:** all seven named advisory publications postdate the associated merged PR. They arise in **six** distinct positive workflows, covering **all six** workflows among the 41 original chronology-incomplete roots. One workflow (`13918`) supplies **two** illustrated advisories. **Five** of the six workflows are original C2 matched positives, while `13918` is one of the two unmatched positives; the original 190 matching pairs are untouched.

**Do not report 7/41 as an empirical prevalence, or 6/6 as a random-sample rate.** This is a purposively inspected subset of source-linked advisory examples. Other warnings on the same roots and the other 34 roots in workflow `13918` were **not** exhaustively publication-dated. The original source D2 packet bytes were read through the Wits read-only connector but **not individually full-file SHA-256 authenticated**; the master D1 and original evidence-index CSV were independently SHA-256 verified in the preceding audit.

## 3. Source meaning: vulnerability, scanner warning and exploitability differ

The original Wits packet for each selected root uses language of `introduces or resolves` a scanner-affected package/version in `package-lock.json`. The modern advisory associates that recorded version with the affected range. This supports the narrower observation: **a later scanner warned about the version present in a historical PR's changed dependency graph**.

It does **not** alone demonstrate: active import/reachability from application entry points, whether attacker-controlled input reaches an affected API, presence of a reachable exploit, whether the vulnerability was absent from the true base's effective transitive graph, security warning knowledge by the original agent, or what an archived 2025/early-2026 vulnerability database would have detected. Those require source-level dependency-graph reconciliation, threat-model constraints and authenticated historical scanners/snapshots.

Conversely, later publication does **not** make the historical package change safe or render modern retrospective exposure comparisons invalid. It constrains any **prospective knowledge or counterfactual prevention** claim.

## 4. Recommended experiment and manuscript separation

**Retrospective exposure outcome:** observed scanner-affected dependency versions in frozen historical base/head as assessed with the study-time advisory catalog. Define the advisory catalog date, scanner version and matcher. No claim that the agent saw this specific warning.

**Prospective-availability outcome:** for each dependency finding, obtain the advisory's earliest confirmed public timestamp *as-of the root-producing commit*, capture the effective scanner/advisory catalog as-of that time and separate `known_before_root`, `known_after_root` and `date_indeterminate`. Track public versus private disclosure separately. A warning published after PR merge cannot qualify as this specific known-before-root public advisory, though other protective knowledge could have been available.

**Retrospective hindsight-oracle intervention:** give the historical issue the later scanner warning and regenerate a patch to measure *what happens if that counterfactual information is supplied*. Call it a **retrospective oracle** rather than a deployable scanner-informed issue-construction method. Require functionality parity, actual vulnerability-mechanism resolution, non-target-warning monitoring, and independently reproducible scanner/source evidence.

**Deployable prospective intervention:** test a feasible pre-implementation mechanism such as contemporary lockfile constraints, dependency policies, archived advisory data, repository-local conventions or up-to-date scanners available at the actual task time. Any later advisory must be excluded from the contemporary-information condition; intentionally using it is a *separate hindsight upper bound*.

**Statistical reporting:** if this timing distinction affects core hypotheses, measure it **across the entire dependency-positive cohort** using original authenticated scanner findings, warning IDs, source commit times, advisory snapshots and deterministic rules. Provide workflow- and repository-clustered sensitivity, not iid root-level tests on 36 package entries from one PR. Preserve all originally frozen cohorts, negative/null outcomes and source disagreements.

## 5. Threats to validity that this checkpoint establishes

A manuscript claim such as *"the agent could have avoided this vulnerable dependency if the issue had mentioned the later CVE warning"* is a valid **counterfactual-information** hypothesis only if clearly labelled hindsight-specific. Its practical feasibility is an independent question. Claiming that the historical issue *should* have contained this particular later-public GHSA is not supported by contemporaneous availability.

The seven examples constitute a **documented temporal-validity counterexample** to unqualified prospective claims, **not evidence that all scanner-positive findings are hindsight-only**. We do not change the C1 positives, C2 matched controls, C5 producing changes, C6 root decisions, D-final/D7 classifications, statistical results or any Wits originals.

## 6. Reproduction

The private Git ledger pins all seven original root IDs, package versions, GHSA/CVE IDs, public PR URLs, merge timestamps, advisory source links, publication dates, dates-as-calendar-day gaps and matched-membership flags. Local/default CI checks their internal consistency against the separately verified 41-root and C1/C2 membership ledgers:

~~~bash
python -m analysis.seven_advisory_temporal_replay_gate
python -m unittest tests.test_seven_advisory_temporal_replay_gate -v
~~~

CI does **not** fetch GitHub advisories or Wits private D2 packets; publication dates were confirmed externally during this checkpoint and the reproducible Git test preserves the reviewed mapping. **All 41 advisory publication dates, exact historical as-of scanner catalog and applicability remain open science gates.**
