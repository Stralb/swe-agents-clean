# OSV and Trivy historic runner replay — no-network sandbox verification

The dedicated `.github/workflows/snapshot-stubs-offline.yml` workflow builds a temporary container with Python 3.11, Git and the SHA-verified candidate `packaging==25.0` wheel, mounts the private repository read-only, drops Linux capabilities, sets a non-root UID, limits memory/CPUs/processes, and runs with **Docker `--network none`** and a disposable writable `/tmp`.

Inside this container, the *exact original* SHA-pinned OSV and Trivy scanner control-flow functions operate only on freshly generated two-commit local Git fixtures. OSV discovers a hidden companion `poetry.lock` and uses original `git ls-tree`/`git show` to reconstruct base/head manifest snapshots. Trivy uses the original base/head Git worktrees. Both run local executable **stubs**, not actual OSV/Trivy engines, and the original SQLite worker integration tests execute against disposable test databases.

The stub CLI includes explicit modes to check malformed JSON and nonzero scanner returns; these tests are meant to identify original failure-status semantics. A green isolated CI run demonstrates that the synthetic runner pipeline works without network access, *not* that a genuine OSV/Trivy advisory database or historical rule package is present.

The image's Python base tag, apt package repositories and Git version are not fully digest-pinned. A reproducibility-grade execution of actual historical target repositories requires a separately pinned immutable image, advisory snapshot hashes, scanner versions and governance review. This fixture is not a license to run unknown user code. Original research snapshots, Wits files and `main` remain unchanged.


## Synthetic executable mount requirement

The first run under the network-disabled container failed because the Python fixture writes executable stubs beneath the ephemeral `/tmp` mount and `shutil.which` could not resolve them as runnable. The CI mount now explicitly uses `exec` on the limited `/tmp` tmpfs to permit those **test-created, deterministic stubs** to execute. This is a deliberate test-environment exception, not a recommendation to permit arbitrary executable content in a production scanner sandbox. All source/repository mounts remain read-only; there is no network namespace connectivity, and the container still runs as a non-root user with all capabilities dropped and `no-new-privileges`. This change does not touch historical scanner source.


## Verified outcome — 21 October 2026

After explicitly enabling `exec` for the dedicated temporary mount, [the CI container ran all **11** isolated OSV/Trivy local replay tests successfully](https://github.com/Stralb/arno-research-reproducibility/actions/runs/39618153102). The same source revision passed [the complete Python regression suite: **441 discovered, 437 pass, 4 expected real-tool skips**](https://github.com/Stralb/arno-research-reproducibility/actions/runs/39618162612). Exact runner/CLI argument processing, Git manifest snapshots, parsed synthetic alerts, archived worker integration and malformed-report cases are verified only on the deterministic fake CLIs. This is distinct from executing real OSV/Trivy binaries or reproducing the original study.
