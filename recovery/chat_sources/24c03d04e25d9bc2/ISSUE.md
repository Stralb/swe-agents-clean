# Issue

feat(workflows): cross-invocation artifact scope + cold-resume pointer recovery (by-reference, not a DB blob)

## Problem

When a `persist_session` node is re-invoked and the provider can't restore the prior session (Codex thread expired, Pi JSONL missing/moved, OpenCode session gone), the node runs on a **fresh** session with **zero prior context**. PR #1842 makes this loss *visible* (a warning + the cold run is kept) but does nothing to *recover* the lost context.

The context we'd want is often **already on disk** as artifacts â it's just unreachable from the new run, because artifacts are run-isolated.

## â ï¸ Reframing â this supersedes the original "node output memory" framing

This issue was originally filed as a **DB-backed node-output store** that re-injects a node's last output **by value** (a preamble) on cold resume. Deeper investigation + a survey of current context-engineering practice (Anthropic, Manus) shows that's the **wrong direction**. Keeping this note in the issue so we don't build it the wrong way.

### #1846-as-filed vs. artifacts â they're two implementations of the *same* need

| | **Artifacts (`$ARTIFACTS_DIR`)** | **Node Output Memory (original #1846)** |
|---|---|---|
| Carries | any files the model writes | a node's final **output text** |
| Into context | **by-reference** â model `Read`s on demand | **by-value** â injected as a preamble |
| Structure | freeform, model-named | freeform text blob |
| Managed by | the model (engine gives the path) | the engine |
| Scope | **per-run** (run-isolated; cross-run only via `$ARTIFACTS_DIR/../runs/*` hacks or `archon continue`) | **cross-invocation** `(workflow, node, scope, provider)` |
| Survives session loss | â on disk | â in DB |

**The honest read:** both solve *durable context that outlives the provider session.* Artifacts already do the durable, **by-reference** half well; their only real gap for the cold-resume case is that they're **run-isolated** (a fresh invocation gets an empty dir). The original #1846 bolts on a parallel DB text store **plus a by-value re-injection.**

**Why by-value is the wrong direction:** current practice treats the context window as scarce RAM and uses *restorable compression* â keep the **pointer** in context, put the **payload** on disk, let the agent fetch on demand ([Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); [Manus: Context Engineering](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) â "the file system as the ultimate contextâ¦ restorable compression: drop the page content as long as the URL is preserved"). Pasting a DB blob into every cold-resumed prompt is exactly the anti-pattern. The stronger version of the same idea is **by-reference**.

## Proposed Solution (by-reference)

1. **Stable cross-invocation artifact scope.** Give `persist_session` workflows an opt-in durable artifact location keyed by `(workflow_name, scope_key)` â the same scope key the session store already uses â instead of (or alongside) the per-run `runs/<runId>/` dir. So the next invocation can *see the prior invocation's files* without `../runs/*` path hacks. Concurrency/worktree isolation must be handled (don't let two concurrent runs of the same workflow+scope clobber).
2. **Cold-resume pointer recovery.** In PR #1842's cold-resume branch (`F003`, `resumed === false`), in addition to the existing warning, **point the fresh session at the prior invocation's artifacts** ("prior context was lost; relevant artifacts from the last run are at `<path>` â Read them if needed") rather than pasting any blob. Failure-path only â no effect on warm resume / first run, so it can't reintroduce the #1392 stale-output footgun.

This composes with the future suspend/resume **checkpoint** primitive (checkpoint â session pointer + artifact pointer + DAG cursor), instead of being a by-value side-channel.

## Explicitly rejected

- **A parallel DB text-blob store + by-value preamble.** Duplicates what artifacts already store durably, injects unconditionally into the window (context rot), and cuts against restorable-compression practice. If a small structured *index* of "what the last run produced" turns out to be needed, it should be a sidecar **pointer/metadata** record (see typed-artifacts companion), not the output text itself.

## Relationship to the broader context-passing redesign

This is one slice of "make artifacts the canonical, durable, **typed, by-reference** memory." Companion issues (Tier 1, the high-leverage direction):

- **Typed artifacts + sidecar metadata** (`output_type`, engine-written `.meta.json`) â gives "find the plan artifact from the last run" a real answer instead of filename guessing. *(Foundation for the pointer recovery above.)*
- **Node-boundary summarization + pointer injection** â fixes the real measured pain: `$nodeId.output` injects full upstream text **by value, uncapped** (e.g. `create-pr` pastes `$analyze + $plan + $validate` whole). Highest-ROI item, independent of resume.

Companion issues: #1847 (typed artifacts — the foundation) · #1848 (summarization + pointer injection — highest ROI) · #1849 (reliable cross-provider structured output — the Tier-2 enabler, with the Pi caveats).

## User Flow

### Before (current)

```
run N:   node (persist_session) writes artifacts to runs/<N>/ ; session 'sess-123' persisted (id only)
run N+1: node resumes 'sess-123' -> session GONE -> fresh session
         [!] runs/<N+1>/ is EMPTY; prior artifacts at runs/<N>/ exist but are unreferenced
         [!] PR #1842 warns, but the fresh run is blind
```

### After (proposed)

```
run N:   node writes to durable scope artifacts/<workflow>/<scope>/ ; session persisted
run N+1: node resumes -> session GONE -> resumed=false
         [+] executor surfaces the warning AND points the fresh session at artifacts/<workflow>/<scope>/
         [+] the model Reads the prior plan/findings on demand (by-reference) â not pasted into every prompt
```

## Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| DB text-blob + by-value preamble (original framing) | engine-controlled, simple | duplicates artifacts; context rot; anti-restorable-compression | **Rejected** |
| Pointer recovery into prior-run artifacts via `../runs/*` glob | no new storage | brittle path hack; depends on same worktree/codebase reg | Stopgap only |
| Stable cross-invocation artifact scope + pointer recovery | by-reference; reuses session scope key; composes with checkpoint | needs concurrency/isolation handling | **Chosen** |

## Scope

- Package(s): `workflows`, `core` (path resolution in `paths`)
- Breaking change? `No` (opt-in, additive)
- Database changes? `No` for the artifact-scope path; possibly a small pointer/index row later (not the output text)
- New external dependencies? `No`

## Security Considerations

- New permissions/capabilities? `No`
- New external network calls? `No`
- Secrets/tokens handling? `No` â artifacts already on disk under the same trust boundary; a stable scope dir doesn't widen exposure. Concurrency/worktree isolation must avoid cross-scope leakage.

## Definition of Done

- [ ] Opt-in stable cross-invocation artifact scope keyed by `(workflow_name, scope_key)`, with concurrency/worktree isolation
- [ ] Cold-resume branch (`F003`, `resumed === false`) points the fresh session at the prior scope's artifacts (by-reference), no by-value blob
- [ ] No effect on warm resume / first run / non-persist nodes (guards the #1392 regression)
- [ ] Tests: durable-scope round-trip across two invocations, cold-resume pointer surfaced, isolation between scopes/worktrees
- [ ] Docs: `authoring-workflows.md` "When a resume can't be restored" updated to describe by-reference recovery
- [ ] Cross-linked with the typed-artifacts and output-summarization companion issues

## Context

Follows PR #1842 (surface cold-resume + warn, no replay). Related continuity work: #1830, #1840. Stepping stone to the suspend/resume checkpoint primitive.

