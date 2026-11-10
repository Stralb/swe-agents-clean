# Phase 2 baseline CodeQL evaluator source audit — 2026-10-20

## Intake and precise experiment boundary

These two untouched historical scripts were obtained from `research_artifacts/prevention_pilot_phase2/` as separate read-only downloads. We **did not execute either** and did not inspect or modify any Wits directories, jobs, database files or original experiment outputs.

| Historical implementation | SHA-256 of uploaded source | Size |
| --- | --- | ---: |
| `evaluate_phase2.py` | `0dcd9112ea5aa0c5fa490c313a24e405f02fe35219be8a7bb58639368a89225c` | 10,441 bytes |
| `phase2_eval_v2.py` | `0f4c12a28b57e47c6a9be7316b34a01879d22533e08f89bea558b4b25823301d` | 13,691 bytes |

Both source files parse as Python. **Parsing is not equivalent to running them, rerunning CodeQL, or validating historical outputs.** They are retained verbatim in `historical/codeql_phase2/`; never execute either in the original cluster tree.

Both scripts evaluate exactly **three O/pre-PR case archives** and **six O-run patches**: `O3504_R1`, `O3504_R2` (`js/redos`); `O10819_R1`, `O10819_R2` (`js/file-system-race`); and `O629_R1`, `O629_R2` (`js/biased-cryptographic-random`). They are **not** the later O/W/P 14-case arm-evaluation scripts. This distinction prevents falsely attributing October O/W/P outcomes to this code.

## Documented evaluation logic

1. Load one frozen pre-PR repository archive per case.
2. Locate the corresponding CodeQL JavaScript query.
3. Scan the base and collect SARIF alert results for that query.
4. Apply a generated patch to a worktree extracted from the same base.
5. Rebuild/reanalyze the patched tree with CodeQL.
6. Identify potentially new findings by a partial-fingerprint comparison, or fall back to rule/path/line/message matching if no fingerprint is available.
7. Examine whether the **first SARIF result location** overlaps a line attributed to `git diff --unified=0`.

These observations characterize a **scanner-output comparison**, not correctness, security impact, causal attribution or functional-test success.

## Line-level audit of original evaluator

- `evaluate_phase2.py:19-20`: creates output and work directories at import time. Merely importing the module causes filesystem changes.
- `evaluate_phase2.py:80-85`: removes an existing extraction directory and uses unfiltered `tarfile.extractall` on an external archive. Both violate our create-only cluster policy; extraction requires additional security controls.
- `evaluate_phase2.py:87-105`: removes existing CodeQL database directories and unlinks existing SARIF files before rebuilding/reanalyzing.
- `evaluate_phase2.py:59-77`: searches recursively for the query pack and uses substring `@id` matching; exact query matching is not assured when IDs share a prefix.
- `evaluate_phase2.py:109-135`: fingerprints can be missing, shifting the matcher to unstable path/line/message identity. Fingerprint identity also requires validation across CodeQL versions.
- `evaluate_phase2.py:137-161`: only the first SARIF location is checked for changed-line overlap. Flow alerts may be produced by edits elsewhere.
- `evaluate_phase2.py:243-249`: `target_introduced = NO` is emitted whenever the overlap heuristic fails, even if unmatched CodeQL results exist. This can overstate the absence of new patch-related warnings.

## Changes and remaining issues in the revised evaluator

- `phase2_eval_v2.py:181-208`: adds per-case CLI and a `--preflight` mode, but even preflight creates output/work paths and calls `shutil.rmtree` on existing work directories. **Do not treat preflight as read-only.**
- `phase2_eval_v2.py:56-81`: makes query lookup more explicit and anchors `@id` to whitespace/end-of-line. However, absent a fixed explicit pack path, a local fallback query-pack directory is selected; pack version and exact query digest remain unfrozen.
- `phase2_eval_v2.py:84-99`: adds path/link validation and `filter='data'` to extraction, an improvement over v1, but still removes existing destinations. Link/archive behavior must be independently tested for the selected Python runtime.
- `phase2_eval_v2.py:139-161`: adds `git add -N .` so newly created files can be included in the diff, but maintains only first-location line-overlap attribution. SARIF URI percent-decoding present in v1 was removed in v2, creating another possible path-mismatch source.
- `phase2_eval_v2.py:165-178`: adds per-case checkpoint CSVs. However, existing rows are skipped based **only on run ID**, without checking patch SHA, base archive SHA, CodeQL version or query digest.
- `phase2_eval_v2.py:229-269`: reuses existing base and patched SARIF without verifying them against the current source, patch, query and scanner versions. This can mix incompatible frozen runs.
- `phase2_eval_v2.py:271-279`: if unmatched results exist but none overlaps changed lines, records `REVIEW` instead of `NO`. This is more cautious than v1, though a changed-line match still is not sufficient proof of causation.
- The revised program explicitly states it **does not assess functional correctness**. It writes/overwrites outputs under the original `PHASE2_ROOT` by default.

## Decisions for the new repository

- Freeze both originals unchanged as historical code with recorded SHA-256.
- Do **not** run the historical scripts, even with `--preflight`, on Wits. They contain deletion/overwrite operations and output paths in the original research tree.
- Never label `target_introduced=YES` as a verified vulnerability introduced, or `NO` as proof of absence. Preserve the raw SARIF, query, full result locations, patch and baseline evidence for manual review.
- Build a **pure, offline read-only** comparison library using synthetic tests; distinguish unmatched fingerprints and uncertain no-fingerprint results. This supplementary library is not a reconstruction of unseen historical scanner outcomes.
- Require a new run-specific manifest tying case, base SHA, patch SHA, CodeQL binary/version, exact query SHA, environment and SARIF SHA together before trusting checkpoint reuse.
- Continue searching for the distinct actual O/W/P and screening study runners, functional-test criteria and identity matching.

## Evidence still missing

Six patch blobs, three frozen repository archives, baseline and patched SARIF for all six runs, original output/result CSVs, exact CodeQL binary/query hashes, evaluator invocation logs and the later 14-case O/W/P execution drivers. None of these can be inferred from the two Python scripts alone.

**Disposition:** source integrity independently checked; methodology partially reconstructed; historical scanner outcomes and causal claims unverified.
