# Replay: O/W/P CodeQL comparison (RQ3)

Scripts for the O/W/P CodeQL replay comparison: 14 cases, each replayed with the original issue (O), the issue plus its historical warning (W), and the issue plus a warning-derived safety property (P). Twelve cases have all three conditions, giving 12 + 14 + 14 = 40 scanned patches.

| Step | Script | Purpose |
| --- | --- | --- |
| 1 | `01_freeze_packets.py` | Freeze the 14 input packets (42 ZIPs) with identical base repositories |
| 2 | `02_target_index.py` | Write a versioned target-rule index without altering the frozen ZIPs |
| 3 | `03_preflight_{o,w,p}.py` | Verify the uploaded patch archive byte-for-byte and check that each patch applies with `git apply` |
| 4 | `04_scan_{o,w,p}.py` | Run CodeQL (JavaScript `security-extended`) on the patched repositories and compare with the pre-patch SARIF |
| 5 | `05_aggregate.py` | Combine the three scans (12 + 14 + 14 conditions, CodeQL 2.25.6) into a descriptive per-case comparison |

`03_preflight_p_alt.py` is a second revision of the P-arm preflight; the version used for the recorded run is not identified, so both are kept.

The scripts do not generate patches. The patches were produced separately and uploaded in chunks; the preflight scripts read them. They ran on a Slurm cluster, so paths are built from `$HOME/research_artifacts/prevention_pilot_phase2`, CodeQL is expected at `$HOME/tools/codeql/codeql`, and some steps read earlier job outputs by job ID. Adjust the path constants at the top of each script to run them elsewhere.

Run records, scans and patch bytes are in the study dataset (`study_rq3_owp14_*`, `study_experiment_runs`, `study_experiment_scans`).

## SHA-256

| Script | SHA-256 |
| --- | --- |
| `01_freeze_packets.py` | `1b10095a17625ba71482b6089bb48b7228f698d34e6772e0316e6e99333ce63e` |
| `02_target_index.py` | `15a9d891045a0f20649bf875a5e21332ba3f33f5f444f8687c42777157ff9d08` |
| `03_preflight_o.py` | `6995a12954f8a8168c453c1bce9ccb0996598169b366686030f006a9414d1c77` |
| `03_preflight_p.py` | `053d67f991635c2b6fdff63185f40155a9308b191e099e5de44450b5dead5d77` |
| `03_preflight_p_alt.py` | `1699de8151282cc961f23e8cde43fb4284b3011d788d45c205fcaad5e0bef07f` |
| `03_preflight_w.py` | `5e4209a692a17c8c34b502843a8804d57d288cbcfcaff3b041f7959b3a6fde95` |
| `04_scan_o.py` | `fb83315e24181544c15617332e5e705fc35bf7b934a7e96b31f90c1d75e93a0e` |
| `04_scan_p.py` | `4b5e8ddbeef35babee2dc470515b05c9d670a1fb50cd6316333392c1a75bd3ac` |
| `04_scan_w.py` | `753bae8f1e9730d393309cbc3bb2077927f776a4a41a8b20d44a50dbba70de6e` |
| `05_aggregate.py` | `c6050d1778165d55ee8c673c88b0c2ddb8c963b3c1b7b6d86aa8c72be8b083e6` |
