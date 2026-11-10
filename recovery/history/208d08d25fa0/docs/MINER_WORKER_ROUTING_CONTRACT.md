# Miner worker-routing contract — recovered source and preservation warning

**Purpose:** engineering recovery and regression coverage of original miner source. This does **not** reclassify historical cases, rerun experiments, or change frozen results.

## Exact source promotion

Two source modules are byte-for-byte identical in the archived August 17, August 19 and October 20 miner snapshots and have been copied, unchanged, into the work branch:

| Active file | SHA-256 | Dependency |
| --- | --- | --- |
| `src/artifacts/regions.py` | `d5445509284912dd2809eca249123063016f644a8c70859e6ec9f530ea5e6e17` | Python standard library |
| `src/filters/tool_applicability.py` | `34053e60b685666f54bf6afb587e92850ccce3e87c5d59d9ae7efe5abfeffce0` | `src.artifacts.regions`, stdlib, ambient `os.getenv` in one function |

Tests in `tests/test_miner_original_worker_routing.py` verify original bytes and synthetic behavior without invoking the collector, databases, scanners, or any cluster command.

## Recovered contract mismatch — important

**Historical source behaviour, not a new research finding.** The original code declares `PRIMARY_WORKER_KEYS = {"codeql", "osv_dependency", "trivy_dependency", "dependency_downgrade", "ci_security"}` but `route_reasons()` returns the key `secret_ci`, **not** `ci_security`. The original gate computes:

```python
any(not routes.get(k, "").startswith("not_applicable:") for k in PRIMARY_WORKER_KEYS)
```

For the missing `ci_security` key, `routes.get("ci_security", "")` is the empty string, and that string does not begin with `not_applicable:`. As a result, **`has_primary_applicable_downstream_worker([{"filename":"README.md"}])` returns `True`**, even when its actual scanner-specific routes are all marked unavailable.

Similarly, `has_any_applicable_downstream_worker()` evaluates all `route_reasons().values()` including the informational `artifact_profile`, which is not an unavailable worker route. This also returns `True` for the README fixture. These outcomes are confirmed in synthetic regression tests and should **not** be silently corrected in the immutable historical implementation.

The separate high-yield surface gate uses `EVIDENCE_STRICT_SURFACE` from the *ambient process environment*. General source paths may change classification when this variable changes; the regression tests set it explicitly. Precise historical configuration provenance is required before reproducing old acceptance decisions.

## Integration decision

These two exact original modules are promoted for **testing and inspection only**. The new `offline_case_collection.py` intentionally does **not** call the original primary-worker or high-yield gates yet. Before activating them in a historical replay, we must decide which behaviour is being reproduced:

1. **Compatibility mode:** retain the byte-exact original behavior, including the key mismatch. This preserves what historical runs *could* have done under the recovered code, but we must still establish the actual runtime version/configuration.
2. **Corrected mode:** explicitly change the key lookup and exclude the informational `artifact_profile` route from worker eligibility. This is a new software behavior and cannot be used to reinterpret or silently change frozen study results.

Future commits must label which mode they use and include independent tests. Do not infer from this code audit that a particular historical Wits case was selected or excluded.

## Verification

Ten new regression tests cover exact source identity across three snapshots, code/JS language regions, the missing route-key issue, the information-only profile issue, high-yield behavior under controlled `EVIDENCE_STRICT_SURFACE`, and dependency files.

```bash
python -m unittest tests.test_miner_original_worker_routing -v
python -m unittest discover -s tests -v
```

On the local staging copy, **75/75** relevant baseline-plus-new tests passed with Python 3.13. GitHub CI provides a separate Python 3.11 check. No Wits cluster or scanner execution occurred.
