[auto] UAT stuck-loop (×9) + orphaned worktree after milestone completion

## Problem

Two cascading bugs cause severe instability in `gsd auto` across milestones:

1. **`run-uat` stuck-loop** (S01×6, S02×9, S03×4): the `uat-verdict-gate` dispatch rule blocks progression with `level: "warning"`, which triggers `pauseAuto`. When the session resumes, it re-enters the same worktree and re-dispatches `run-uat` endlessly because the `ASSESSMENT` file written by the agent doesn't survive cross-session sync.

2. **Orphaned worktree after milestone completion**: after `complete-milestone` + `mergeAndExit`, the worktree directory and `milestone/<MID>` branch are not removed. Every subsequent `/gsd auto` call discovers the orphaned worktree and re-enters it, diverging from the merged `main`.

---

## Root Cause

### Bug 1 — UAT stuck-loop: `run-uat` ASSESSMENT file not synced into worktree on resume

**Location**: `auto-worktree.ts` — `syncProjectRootToWorktree()` + `auto-post-unit.ts` — `LIFECYCLE_ONLY_UNITS`

**Sequence**:
1. `run-uat` executes inside the worktree. The agent writes `S01-ASSESSMENT.md` (verdict: `FAIL`) via `gsd_summary_save` → `saveArtifactToDb` → `process.cwd()` → disk path inside the worktree.
2. `run-uat` is in `LIFECYCLE_ONLY_UNITS` → **no auto-commit**. The file stays untracked in the worktree working tree.
3. `syncStateToProjectRoot()` (post-unit) copies the worktree `.gsd/` → project root. `S01-ASSESSMENT.md:FAIL` lands in the project root.
4. `uat-verdict-gate` sees verdict `"fail"` → `level: "warning"` → calls `pauseAuto()`.
5. On next `/gsd auto` (resume), `syncProjectRootToWorktree()` runs with **`force: false`** (additive-only). If `S01-ASSESSMENT.md` is already present in the worktree (from step 1), it is NOT overwritten — the stale `FAIL` copy blocks.
6. But **between sessions**, `syncProjectRootToWorktree` also deletes `gsd.db` in the worktree and re-creates it from disk. During that rebuild, the worktree's in-memory write from step 1 may not be on disk if a session crash preceded the pause — leaving the worktree without any `ASSESSMENT` file at all.
7. `checkNeedsRunUat` (`auto-prompts.ts:~802`) finds no verdict → re-dispatches `run-uat`.

**The compounding issue**: when the session is stopped (not merely paused) and restarts from the project root — because `paused-session.json` was not written or was lost — `enterMilestone()` in `auto-start.ts` must re-enter the worktree. It does so by calling `getAutoWorktreePath()` then `enterAutoWorktree()`. If the worktree was left in a state where `reconcilePlanCheckboxes()` can't find the `ASSESSMENT` verdict, `checkNeedsRunUat` dispatches `run-uat` again.

**Code path** (confirmed in source):
```ts
// auto-prompts.ts ~802
if (!prefs?.uat_dispatch) return null;
// ...
const assessmentFile = resolveSliceFile(base, mid, sid, "ASSESSMENT");
if (assessmentFile) {
  const assessmentContent = await loadFile(assessmentFile);
  if (assessmentContent && hasVerdict(assessmentContent)) return null; // ← only exits if file found AND has verdict
}
```

If `S01-ASSESSMENT.md` is absent from the worktree (deleted by DB rebuild), `loadFile` returns null, `hasVerdict` is never called → `run-uat` is dispatched again.

### Bug 2 — Orphaned worktree: `teardownAutoWorktree` silently fails, branch not deleted

**Location**: `auto-worktree.ts` — `teardownAutoWorktree()` + `worktree-manager.ts` — `removeWorktree()`

After `complete-milestone`, `stopAuto()` detects the SUMMARY and calls `resolver.mergeAndExit()`. The squash merge succeeds (confirmed: `feat(M011): ...` commit on `main`). However `teardownAutoWorktree()` attempts `removeWorktree()` which calls `nativeWorktreeRemove()` + `nativeBranchDelete()`. Both calls are wrapped in `try { ... } catch { /* may fail */ }` — **failures are silently swallowed**. When the worktree directory contains uncommitted files (e.g. untracked `S01-UAT-RESULT.md` written by `run-uat`), `git worktree remove` fails with "contains untracked files". The catch swallows it. The force-remove attempt also fails if the process CWD is still inside the worktree at the time of the call. Result: the worktree directory and branch remain on disk forever.

**Confirmed in production**:
```
git worktree list:
  /project                              06ff412 [main]     ← M011 merged ✓  
  /project/.gsd/worktrees/M011         5ee7af0 [milestone/M011]  ← orphaned ✗
```

**Code path** (confirmed in source):
```ts
// worktree-manager.ts ~364
try { nativeWorktreeRemove(basePath, resolvedWtPath, useForce); } catch { /* may fail */ }
// If the directory is still there, try harder:
if (existsSync(resolvedWtPath)) {
  try { nativeWorktreeRemove(basePath, resolvedWtPath, true); } catch { /* may fail */ }
}
// → nativeWorktreePrune called, but the .git file still exists → prune has no effect
// → nativeBranchDelete called but branch is still in git's worktree registry → fails
```

The `teardownAutoWorktree()` call in `auto-worktree.ts` has a warning for this case (logWarning + rmSync fallback) but the `rmSync` also silently fails when git's internal `.git/worktrees/<name>` lock file is present.

---

## Environment

- GSD version: 2.53.0
- Model: claude-sonnet-4-6
- Units affected: `run-uat/M011/S01` (×6), `run-uat/M011/S02` (×9), `run-uat/M011/S03` (×4), `complete/milestone-M011`

---

## Reproduction Context

- Active milestone with worktree isolation enabled
- `uat_dispatch: true` in preferences
- First `run-uat` produces `verdict: FAIL` in ASSESSMENT
- Session pauses/stops via `uat-verdict-gate` (warning-level stop)
- User restarts `/gsd auto`
- New session cannot find verdict in worktree ASSESSMENT → re-dispatches `run-uat` indefinitely

---

## Forensic Evidence

```
[ERROR] stuck-loop: run-uat/M011/S01 dispatched 7 times (worktree journal: 1 time, project-root session: 6 times)
[ERROR] stuck-loop: run-uat/M011/S02 dispatched 9 times
[ERROR] stuck-loop: run-uat/M011/S03 dispatched 4 times

Journal trace (worktree):
  11:24:46 dispatch-match run-uat M011/S01
  11:27:48 unit-end run-uat M011/S01 → artifactVerified:true
  11:28:05 dispatch-stop reason:"UAT verdict for S01 is 'fail' — blocking progression"

Activity log trace (project root, 2nd session):
  004-run-uat-M011-S01 (ASSESSMENT written with verdict:PASS via gsd_summary_save)
  005-run-uat-M011-S01 (again — ASSESSMENT not found in worktree)
  ...009-run-uat-M011-S01

Orphaned worktree after complete-milestone:
  git worktree list showed milestone/M011 still registered after merge commit:
  "feat(M011): Inspecteur Xray CSS flottant — merge milestone/M011"
  
error-trace: ls src/lib/xrayWindow.svelte.ts: No such file or directory
  → complete-milestone running in project-root context, file only exists in worktree
```

---

*Auto-generated by `/gsd forensics` — GSD 2.53.0*
