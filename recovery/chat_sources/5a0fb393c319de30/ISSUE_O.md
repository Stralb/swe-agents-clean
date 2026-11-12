WP13: composed acceptance at the production boundary

## Why this is its own issue

Every phase of the Codex write substrate proved its own mechanism, and each proof was phase-local. That is precisely the shape of failure the substrate exists to prevent: a system where each helper passes its own tests while a production path still writes around it.

The unit's own plan names the seams that a phase-local green suite cannot see ([050_composed_acceptance.md](devlog/_plan/260804_codex_write_substrate/050_composed_acceptance.md)):

- startup restores a journal before the server exists (`src/cli/index.ts:169-176`)
- server construction rewrites `models_cache.json` directly (`src/server/index.ts:362-403`)
- sixteen management call sites invoke a swallowed best-effort catalog writer (`src/server/management-api.ts:105-112`)
- explicit restore writes history inline (`src/codex/inject.ts:764-794`)
- the retry guardian gives up after sixty ticks (`src/codex/history-migration-guardian.ts:34-35,87-90`)

## What is already proven, and what is not

The write lock now has a production caller and real two-process contention through `injectCodexConfig` — one process commits, the other reports `busy`, and the loser's bytes are absent. Admission produces byte-exact witnesses, ownership is genuinely tri-state, and the service-manager probe distinguishes "answered no" from "could not ask".

What is **not** proven is that every production entry point funnels through that substrate. The census in `050` counts 36 rows across two execution classes, and nothing yet asserts they all converge.

## Scope

`050_composed_acceptance.md` specifies the whole program: a workstation-safe `tests/codex-composed-acceptance.test.ts` plus a disposable-host service job at `scripts/disposable-host/codex-service-composed-acceptance.ts`. Service-manager entry points stay out of ordinary test discovery — they need a host that can be destroyed.

Scenarios A through F are written there, including the two-process race after approval, `/healthz` under real SQLite contention, and one effective user reaching one lock from different environment homes.

## Deferred deliberately

This was deferred from the substrate unit rather than skipped. The unit's honest claim today is that each mechanism works and that the lock is reachable from production — not that the composed system has no path around it.
