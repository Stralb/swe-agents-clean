# Issue

Add first-class Codex app-server v2 adapter

Parent: #915

Prerequisite #919 is complete. The task-bound core adapter can ship independently. Provider-neutral approvals, durable reattachment, external lifecycle controls, run-scoped MCP, and release certification remain owned by #852, #853, #856, #857, and #859 and must fail closed here.

## Outcome

Add Codex app-server as a first-class supervised JSON-RPC adapter while retaining the existing one-shot Codex CLI and Codex SDK adapters. This issue delivers initialization, one task-bound thread and turn, structured streaming, cooperative interruption, usage, completion, and exact-version protocol validation.

## Upstream baseline and evidence

Audited 2026-07-23:

- Stable Codex release: [`rust-v0.145.0`](https://github.com/openai/codex/releases/tag/rust-v0.145.0), commit `25af12f7e61572b0bc18ddb1008be543b91519b0`.
- Local executable: `codex-cli 0.145.0`, authenticated through ChatGPT.
- Current Veritas Codex SDK pin: `0.144.3`.

The [version-pinned app-server README](https://github.com/openai/codex/blob/25af12f7e61572b0bc18ddb1008be543b91519b0/codex-rs/app-server/README.md) documents:

- JSONL over stdio as the default transport;
- thread, turn, and item lifecycle;
- thread start/resume/fork/compact/archive;
- streamed item updates, completion, and usage;
- turn interruption;
- command/file approvals and elicitation;
- MCP and version-gated skills/hooks/plugins;
- exact-version TypeScript and JSON Schema generation;
- bounded queues and overload error `-32001`;
- an unsandboxed `thread/shellCommand` method that Veritas must not expose.

## Design

Add an explicit `codex-app-server` adapter/profile:

```text
codex app-server --stdio --strict-config
```

Roles remain explicit:

- `codex-cli`: one-shot automation and compatibility.
- `codex-sdk`: in-process SDK workflows.
- `codex-app-server`: interactive sessions, rich streams, approvals, lifecycle controls, and resume.

Spawn one supervised process without a shell, initialize it once, use exact-version generated schemas, persist Codex thread IDs, and normalize thread/turn/item events without discarding raw protocol evidence.

## Scope

- Executable/version/auth diagnostics.
- Strict-config stdio launch and initialization.
- Thread start for the task-bound run; persist thread identity and publish truthful capability evidence for deferred resume, fork, compact, and archive controls.
- Turn start, item streams, completion, and usage.
- `turn/interrupt`.
- Deterministic command/file approval and elicitation denial while the shared Veritas brokers remain unavailable.
- Disable inherited MCP, plugin, app, hook, and remote-control surfaces until the run-scoped control plane is available.
- Bounded overload retry/backoff.
- Versioned stable/experimental capability negotiation.
- CLI/API/web provider onboarding, controls, telemetry, and docs.

Out of scope:

- Replacing `codex-cli` or `codex-sdk`.
- Using WebSocket transport while upstream labels it experimental.
- Exposing `thread/shellCommand`.
- Enabling experimental methods solely because they appear in generated schemas.

## Security and failure semantics

- Never invoke or proxy `thread/shellCommand`.
- Spawn without a shell in the task worktree using the existing safe Codex environment policy.
- Enforce Veritas sandbox, approval, MCP, credential, path, and network boundaries.
- Reject malformed or uncorrelated thread/turn/item IDs.
- Bound input/output queues and retry only documented overload failures.
- Distinguish protocol error, overload, denial, interruption, child crash, and terminal turn failure.
- Version-gate experimental methods and invalidate evidence after build changes.

## Acceptance criteria

- [x] `codex-app-server` is a distinct executable provider/profile.
- [x] Probe output records exact version/build and redacted authentication readiness.
- [x] The adapter launches `--stdio --strict-config` without a shell and completes initialization exactly once.
- [x] Exact-version schemas validate all consumed requests, responses, and notifications.
- [x] Thread start is supported; resume/fork/compact/archive remain manifest-gated and fail closed until #856.
- [x] Turn and item streams map to the causal Veritas event journal with raw evidence preserved.
- [x] Usage and terminal completion map to the canonical completion contract.
- [x] Approval and elicitation requests are journaled and deterministically denied while #852/#857 remain unavailable.
- [x] `turn/interrupt` supports cooperative cancellation.
- [x] Overload `-32001` uses bounded retry/backoff and remains observable.
- [x] `thread/shellCommand` is structurally unreachable from Veritas.
- [x] CLI, API, web UI, telemetry, and docs distinguish all three Codex adapters and their certified capabilities.

## Test evidence

- Deterministic protocol tests cover the pinned handshake, thread/turn correlation, structured streams, usage, completion, denial, overload, malformed records, uncorrelated responses, size limits, and the unreachable shell-command boundary.
- Lifecycle integration tests cover supervised spawn, persisted thread identity, event journaling, terminal completion, and cooperative interruption.
- The exact Codex CLI v0.145.0 executable completed the credential-gated smoke with remote control observed as disabled.
- Local gates passed: 3,085 workspace unit tests, lint, typecheck, build, pnpm settings, desktop readiness, CLI/MCP compatibility, and the security artifact scan.
- PR #952 passed all seven required CI and desktop artifact checks and merged as `8904d6093f41273ea73916b2341ddc23a2a09b09`.

## Dependencies and non-duplication

- Blocked by #919.
- #850, #854, #858, #892, #893, and #919 are complete and support this core adapter. #852, #853, #856, #857, and #859 remain explicit follow-ups for brokered approvals, crash reattachment, external lifecycle controls, run-scoped MCP, and release certification.
- #298-#305 and #795 established the current Codex adapters and conformance direction. This issue is specifically the app-server transport and does not reopen completed CLI/SDK work.

## Done when

The core adapter is merged with required checks green and can operate the pinned release across initialization, a task-bound thread/turn, structured streaming, cooperative interruption, usage, completion, and fail-closed protocol errors without weakening security boundaries or displacing the CLI/SDK adapters. Deferred provider-neutral controls remain visibly unsupported until their owning issues land.


