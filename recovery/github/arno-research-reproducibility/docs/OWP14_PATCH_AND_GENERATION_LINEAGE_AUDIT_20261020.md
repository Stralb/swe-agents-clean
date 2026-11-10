# October O/W/P — patch lineage, prompt construction and implementation scope

**Audit date:** 2026-10-20  
**Status:** archive membership and recorded patch→preflight→CodeQL linkage **verified**; model-session equivalence, original-issue functional acceptance, historical-warning delta and causal prevention **not established**.

## Archive identities

| User-supplied archive | Outer ZIP SHA-256 | Checked members |
| --- | --- | ---: |
| `02_ALL_GENERATED_PATCHES.zip` | `1495e6797aec65d912ac3bc77b893cf79561f471749f78d6807fecbc619e0049` | 368/368 |
| `07_AGENT_PROMPTS_AND_TRACES.zip` | `d004abaafea36b9e54c8620ac456072ae74937b483608b469f9198d103c135c3` | 600/600 |

Both ZIPs opened with no CRC failures and have an exact entry-to-part-index correspondence, with no duplicate file paths, missing entries or SHA-256/size mismatches. The code was read only as data; no script, Slurm job or patch was executed or applied. The original Wits cluster and third-party repositories were not accessed or modified during this check.

## Patch cohort identity — do not combine strata

`02_ALL_GENERATED_PATCHES.zip` contains **235** top-level `.patch` members, comprising **40 O/W/P patches** (12 O, 14 W, 14 P) and **195 screening patches** covering the *same 65 screening cases in three stages*. All 65 patch byte hashes differ across all three screen stages: this is three per-case patch versions, **not 195 distinct cases or proof of independent generation**. All 14 O/W/P case IDs also appear among the 65 screening case IDs; the strata remain distinct.

The O/W/P preflight results each declare completion and successful application in an isolated copy. **40/40** direct patch bytes match their preflight SHA-256/byte count and the corresponding patch inside the nested original-transfer ZIP. The three nested transfer ZIP hashes match their summary manifests, and the scanner `RESULT.json` in `03_CODEQL_SARIF_AND_SCANS.zip` matches **40/40 patch digests and input-packet ZIP digests**. All 40 scanner records say `SCAN_COMPLETE` and CodeQL **2.25.6**. Those records point to **14** distinct *archived baseline SARIF identities*, exactly one per case, shared across available arms; every arm records reuse of a compatible original `screen65_codeql_job70675/CASE_XXXXX/before.sarif` baseline. These *before* files are **not present** in the supplied scan export and new-warning deltas have not been recomputed.

Case **08461** and **15151** have W and P but no O in this exported patch/scan cohort. No missing O is imputed.

## O/W/P treatment definitions — code-proven, application not independently verified

The archived `owp14_20261018_v1/freeze14.py` contains exactly **14 historical target specifications** and constructs three condition packets per case (42 planned input ZIPs). It specifies the following issue-content transformation:

| Condition | Frozen packet source code specification | Interpretation |
| --- | --- | --- |
| **O** | Original issue body, no additional implementation information | Original-issue condition, but verified original-as-of-PR issue text is unavailable |
| **W** | Original issue plus previous CodeQL `Rule` and `Diagnostic`, asking to implement without introducing that finding | **Retrospective oracle**, using the historical warning |
| **P** | Original issue plus a tailored natural-language safety/property requirement, omitting the literal CodeQL rule ID | Mechanism/property intervention **still informed by historical warning selection** |

The P condition is **not truly hindsight-free** merely because it omits the rule ID: the property text was designed for the case's historical mechanism. Therefore W→P is a removal of *explicit scanner jargon* but not a demonstration that an agent would derive the same property prospectively from the new issue alone.

The run-instructions template says to use only the frozen `ISSUE.md` and `REPO/`, not consult GitHub/earlier chats, and return a unified `.patch` from a fresh coding session. Its researcher notes require logging model, configuration, seeds/timing and invalid generations. The frozen manifest explicitly says `generations_started=0` **at packet-freeze time**, and `historical_issue_body_verified_asof_pr=False`; it is *not* evidence that later user-provided patches were never generated. Case **00668** uses exact copies of a previously frozen three-arm packet, rather than packets newly produced by this builder; its definitions must be checked against that earlier packet.

The misleadingly named `07_AGENT_PROMPTS_AND_TRACES.zip` contains **41 Python files, 63 Slurm scripts and 496 `.out`/`.err` job logs**, *not complete model chat transcripts, model IDs, temperature/seed specifications, or a session-level issuance ledger*. Job-runner history allows code provenance, not evidence that the implementation-agent sessions actually obeyed the prompts or were independent/comparable.

### Historical program versioning

Python static syntax parsing passed **40/41** job `.py` files. `owp14_20261018_v4/eval_668_uploaded_scannerfix.py` fails at line 101 due to a single misindented `if`. The `v4b` source corrects that line. Neither should be promoted as active production code without separate control-flow and output verification. This correctable program defect is historical evidence and should remain preserved. Other source-script changes include an old P scanner referring to an obsolete preflight directory, corrected in v3, then a missing `source_bytes` field used for ordering, corrected to `source_files` in v4.

## Structural implementation differences: measured directly from patch text

On the **12 fully paired cases**, structural patch measurements give:

| Measure | O | W | P |
| --- | ---: | ---: | ---: |
| Number of paired cases | 12 | 12 | 12 |
| Median patch size | **10,482.5 bytes** | **6,305.5 bytes** | **6,631 bytes** |
| Median added + deleted diff lines | **146** | **92** | **98.5** |
| Smaller than O by patch size | — | **9/12** | **9/12** |
| Fewer changed lines than O | — | **10/12** | **7/12** |

The measurements count unified-diff `+` and `-` content lines, excluding `+++` and `---` file headers; changed-path counts come from source preflight records and are checked against the number of `diff --git` blocks. Test-path flags are heuristics based on names and are *not* evidence of executed or passing tests. The full 40-row, case-level, SHA-indexed table is in `provenance/owp14_patch_scope_20261020.csv`.

A large case-level example is **06104**, where O changes 693 lines across 10 files; W changes 72 lines across 3 files; P changes 100 lines across 4 files. Similarly, case **16633** has O=464, W=55 and P=55 changed lines. Its O patch also fails the independently archived JSX-aware syntax check while recording no newly introduced CodeQL warnings.

**Interpretation:** a lower alert count may arise from patch size, reduced task coverage, changed file choices, missing features, altered implementation mechanisms or genuinely safer coding. These alternatives are *not identified* by scanner-count differences. Do not normalize alerts by changed lines and declare a causal treatment effect; line counts are post-intervention outcomes and require appropriate experimental design.

## Scientific conclusions and gates

1. O/W/P patch bytes and their frozen preflight/scan identities can be traced end to end without source execution. This resolves one **artifact lineage** uncertainty, not the key causal uncertainties.
2. The 14 baseline SARIF files themselves are still absent. Although the reported scanner version and per-case baseline hash are consistent, CodeQL alert set differences are not independently reconstructed.
3. `ISSUE.md` pre-PR provenance and source-tree equality across arm ZIPs require frozen input files or an independent on-cluster content-hash audit. Equal *baseline SARIF hashes* alone cannot establish identical input repositories.
4. There are no complete coding-agent session transcripts, guaranteed equal model/configuration, or randomized independent generation records in the supplied archives. This materially limits W/P versus O comparisons.
5. Smaller W/P patches and the known 16633-O syntax failure create plausible *task-coverage and functionality confounders*. Original issue acceptance and same-task completion must be established before a treatment effect is assessed.
6. Because W and P information is derived from known historical warning mechanisms, the current intervention is retrospective. Prospective retrieval/selection of safety requirements is a *separate* empirical research question.

**Status:** archival patch identity and offline static scope measurements reproduced; causal interpretation, full functional equivalence, prospective feasibility and independent CodeQL differential verification **remain open**.

## Repeat locally (no Wits cluster writes)

```bash
python -m tools.owp14_generation_lineage /path/to/02_ALL_GENERATED_PATCHES.zip /path/to/07_AGENT_PROMPTS_AND_TRACES.zip --scanner /path/to/03_CODEQL_SARIF_AND_SCANS.zip
python -m tools.owp14_patch_scope /path/to/02_ALL_GENERATED_PATCHES.zip --format csv
python -m tools.owp14_patch_scope /path/to/02_ALL_GENERATED_PATCHES.zip --format json
python -m unittest discover -s tests -v
```

The commands read local files and print to stdout. Original research archives, prompts, model traces and third-party source patches are deliberately **not** committed to GitHub.
