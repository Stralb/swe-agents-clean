# Research Map and Evidential Status (20 October 2026)

**Purpose:** A cross-stage map for recovering source code while preserving experimental chronology and frozen labels. This is a research recovery document; it does not claim independent end-to-end replication.

## The pipeline and units

| Stage | Unit | Frozen or reported observation | Status / interpretation |
| --- | --- | --- | --- |
| Mining, agent-markers and linking | GitHub issue → agent-associated merged PR workflow | 3,809 workflows | Reported cohort; regenerate from frozen database and query before treating as independently verified |
| Security scanning | Scanner-positive workflow | 192 | Observed historical scanner cohort; scanner provenance/false-positive controls remain necessary |
| Producing-change mapping | Exactly mapped scanner-producing change | 455 changes in 191 workflows | One scanner-positive workflow has no exactly mapped producing change. Never force it into the denominator |
| C root census | Distinct implementation-decision root | 342 roots representing all 455 mapped changes | Crosswalk checked locally: 342 unique roots; 455 distinct PCs; 191 workflows; 283 singleton and 59 multi-PC roots |
| D provenance, final export | Root with H/T/M route; M explanation tier | 5 H; 103 T; 234 M | Original frozen output; conflicts with D7 cohort export |
| D7 holdout | Root after cohorts assigned | 6 H; 103 T; 233 M, partitioned into 56 discovery-derived and 177 new holdout M | Analyzed separately, not silently substituted for D original |
| C5/C6/C7 controls | Matched positive–control workflow pair | 190 pairs, including 115 same-repository pairs in historical summary | Frozen inputs and analyses available; independent regeneration of all reported p-values still pending |
| Decision-level control Steps 4–7 | Mechanism-decision pair / evidence side | Step 4: 51 matched decisions (31 primary); Step 7: 102 symmetric evidence sides planned | Keep pilot, primary, partial runs and symmetric evidence design separate |
| Outcome-blind discovery v2/v2.1 | Observed corpus feature / pattern | v2.1 run status PASS; 3,485 discoveries (1,950 strict grade A) | Its own failure audit identifies weak discovery units; do not promote as a confirmed scientific mechanism |
| Discovery v2.2 | Concrete code-change operation | Corrective design available; complete execution not established | Never describe it as a completed replacement until stage results verified |
| T1/T2 retrospective interventions | Case × fresh implementation condition | Several pilots and blinded packets available | Keep historical replay, generation, target warning and counterfactual definitions distinct |
| October O/W/P prevention | Case × prompt arm × generation | 7-case handoff and 14-case exploratory packages are documented | Zero *new* CodeQL findings in a subset is not equivalent to confirmed vulnerability prevention or functional correctness |

## Research lineage at a glance

1. **Source discovery and mining.** Repository exploration, PR-first linkage, agent markers, collection windows and rate-limit handling were iterated repeatedly. The cluster's current miner source archive contains historical backups that must be audited individually, not pasted into `src/` as active modules.
2. **Security validation and manual evaluation.** Scanner findings were revalidated, normalized, and mapped to changes. The 122-case evaluation, F1–F5 attack footprint, multichain and provenance corrections are important historical strata, not labels automatically assigned to all 3,809 workflows.
3. **C root census.** C defines an implementation decision and partitions all producing changes. Its 342-root denominator replaced earlier selected-subset denominators; 455-to-342 accounting is locally verified via the recovered CSV crosswalk.
4. **D provenance.** Repeated blinded coding passes, followed by mandatory adjudication, labeled the frozen C roots. Both passes used **GPT-5.6 Sol**; these are blinded repeated LLM passes, **not independent human raters or different model families**.
5. **Matched comparisons.** Workflow-level and decision-level controls ask different questions. Preserve denominators, same-repository strata, exclusion criteria, tests, and null effects separately.
6. **Discovery and counterfactual interventions.** The mechanism identification and warning-informed counterfactual studies are exploratory causal investigations. A historical warning supplied to a fresh issue is a **retrospective oracle intervention**, not a deployable warning predictor. Hindsight is progressively removed in later prompt conditions.

## Version selection rules

- A folder named `FINAL`, `PASS`, or `LATEST` is evidence of that package's **declared state**, not cross-version scientific authority.
- The **C** root partition currently has an explicit internal accounting check. The **D and D7** final labels **cannot both be treated as one dataset**; see `provenance/d_vs_d7_label_differences.csv`.
- Discovery v2.1 is computationally completed, but the v2.2 design document criticizes its scientific discovery unit. Distinguish computational reproducibility from validity of the research claim.
- A source file with passing Python syntax is **not automatically** a tested or accurate miner implementation.

## Work remaining

Recover and reconstruct the exact database snapshot and scanner configuration for 3,809/192/455; trace original scanner reruns and exclusions; reconcile D/D7 via adjudication ledger; recover all source scripts producing each frozen analysis; recover full October CodeQL provenance/functional tests; and regenerate key tables in a fresh environment. Keep any gaps explicit.
