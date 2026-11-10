# Issue

DAG executor threads session id across provider boundaries → downstream node fails to resume (claude-terminal TUI boot timeout)

## Summary
In a DAG workflow that mixes providers across sequential nodes, a downstream node inherits the previous node's provider session id and tries to resume it under a DIFFERENT provider. The resume target doesn't exist, so the node fails to start. With the claude-terminal provider this manifests as a TUI boot timeout stuck on the "Resume session" picker.

## Repro
1. A DAG workflow with a sequential chain where node A uses `provider: cursor` and the next AI node B uses `provider: claude-terminal` and does NOT set `context: fresh`.

Node B's first turn logs `isResume: true` with a session id created by node A, then:

```
claude-terminal: TUI did not become input-ready within boot timeout.
Last screen: Resume session ⌕ agent-<uuid>  "No sessions match agent-<uuid>"
```

Retries (2x) repeat identically; the node fails and aborts the workflow.

## Root cause
`F001` (~3301-3305):

```ts
const isFreshSequential = isParallelLayer || node.context === 'fresh';
let resumeSessionId = isFreshSequential ? undefined : lastSequentialSessionId;
```

`lastSequentialSessionId` is inherited with no provider-equality check. Cross-provider resume is impossible, so the downstream provider gets a foreign session id.

## Expected
A sequential node should inherit the previous session id only when the previous node ran on the SAME resolved provider. On a provider change, start a fresh session.

## Workaround
Add `context: fresh` to every node that follows a different-provider node.

## Notes
- Homogeneous-provider workflows are unaffected (resume targets always valid).
- claude-terminal `ensureInputReady` (`packages/providers/.../claude-terminal/provider.ts` ~374-388) could additionally detect the resume picker and Esc out, but the core fix is the provider-boundary session reset.
- Environment: archon @ commit ffa21cf1, Claude Code CLI 2.1.177, macOS.

