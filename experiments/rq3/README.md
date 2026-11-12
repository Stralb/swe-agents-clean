# RQ3 replay: packets, patch scans and aggregation

Scripts behind the O/W/P CodeQL comparison reported for RQ3: 14 historical cases, each replayed with the original issue (O), the issue plus its historical warning (W), and the issue plus a warning-derived safety property (P). Twelve cases have all three conditions (12 O + 14 W + 14 P = 40 scanned patches).

The scripts are **verbatim copies** of the originals that ran on the university cluster. They are not edited, so their SHA-256 values can be compared with the cluster copies (see [PROVENANCE.md](PROVENANCE.md)).

## Pipeline

| Step | Script | What it does |
| --- | --- | --- |
| 1 | `jobs/owp14_20261018_v1/freeze14.py` | Freezes the 14 O/W/P input packets (42 ZIPs) with identical base repositories. Researcher-only metadata is kept separate. |
| 2 | `jobs/owp14_20261018_v2/target_index_fix.py` | Writes a versioned target-rule index without altering the frozen ZIPs. |
| 3 | `jobs/owp14_user12_20261018_v1/preflight.py`<br>`jobs/owp14_user14_w_20261018_v1/preflight.py`<br>`jobs/owp14_user14_p_20261018_v1/preflight.py` (or `…_v2b/`) | Verifies the uploaded patch archive byte-for-byte, then checks in isolation that each patch applies with `git apply` (O, W, P). |
| 4 | `jobs/owp14_user12_20261018_v2/scan12.py`<br>`jobs/owp14_user14_w_20261018_v2/scan14.py`<br>`jobs/owp14_user14_p_20261018_v4/scan14.py` | Runs CodeQL (JavaScript `security-extended` suite) on the patched repositories and compares against frozen pre-patch SARIF controls. |
| 5 | `jobs/owp14_w14_20261018_v3/aggregate_owp.py` | Reads the three completed scans, asserts 12 + 14 + 14 conditions and a single CodeQL version (2.25.6) and suite, and writes a descriptive per-case comparison. It makes no causal claims. |

Each `*.sbatch` file is the Slurm launcher for the script beside it.

## What these scripts do not do

- They do **not generate patches.** The patches were produced outside the cluster and uploaded in base64 chunks; the preflight scripts read them. The upload chunks are not in this repository.
- They report CodeQL alerts. The paper states that functional equivalence was not established.

## Running them

They are tied to the cluster layout. Paths are built from `$HOME/research_artifacts/prevention_pilot_phase2`, CodeQL is expected at `$HOME/tools/codeql/codeql`, and several steps read earlier job outputs by hard-coded Slurm job IDs (for example the packets from job 71014 and the scan results from jobs 71159, 71204 and 71209). To reuse them elsewhere, set up the same directory layout or edit the path constants at the top of each script.

## Where the results are

The original runs, scans, patch bytes and reproduction checks are in the study dataset, in the `study_rq3_owp14_*`, `study_experiment_runs` and `study_experiment_scans` tables. See [../../dataset/README.md](../../dataset/README.md).

## Not included

- The version of the P-arm preflight that produced job 71201 is not recorded, so both candidates (`…_p_20261018_v1` and `…_v2b`) are included.
- Earlier versions of the scan scripts, single-case checks for case 668, and the later functional, syntax and targeted-behaviour checks are not copied. They are kept in the private working archive, available on request.
