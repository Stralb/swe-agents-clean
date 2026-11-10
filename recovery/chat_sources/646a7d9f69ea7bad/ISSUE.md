# Issue

[Feature] Support Cursor CLI login session (reuse subscription quota) instead of requiring CURSOR_API_KEY

### Problem / pain point

The built-in "Cursor" managed agent (added in #1399) only works via the Cursor SDK
authenticated with a `CURSOR_API_KEY` (either from settings or the `CURSOR_API_KEY`
env var). In `probeCursorSdkAvailability()` (electron/bridges/aiBridge/agentDiscoveryHandlers.cjs),
the agent is skipped entirely from discovery unless an API key is present:

    const authenticated = hasEnvApiKey || hasSettingsApiKey;
    ...
    if (!cursorSdkStatus.available) continue;

This means Cursor Pro/Business/Enterprise users who already run `cursor-agent login`
locally and use the CLI's "Auto" mode (which draws from their subscription's included
agent quota) cannot use that same authenticated session inside Netcatty. To use Cursor
through Netcatty's Catty Agent panel, they're forced onto the metered API instead of
their already-paid-for subscription quota — even though `claude` and `copilot` managed
agents in the same file *do* reuse the local CLI's login (`probeClaudeAuth`,
`probeCopilotAuth`) without requiring a separate API key.

This is inconsistent with how the other managed agents behave and effectively makes
Cursor the only "pay twice" option in the AI assistant settings.

### Proposed solution

Add a local-CLI-auth detection path for Cursor, similar to what already exists for
Claude Code / Copilot, so `probeCursorSdkAvailability()` can report `authenticated: true`
based on a locally logged-in `cursor-agent` CLI session (e.g. detecting credentials under
`~/.cursor` or running something like `cursor-agent status`), without requiring
CURSOR_API_KEY to be set.

If reusing the CLI's session inside the in-process @cursor/sdk isn't feasible, an
acceptable fallback would be letting the managed agent spawn the `cursor-agent` binary
directly as a subprocess (non-interactive/print mode) the same way other CLI-backed
agents are invoked, so it inherits the user's existing login/subscription quota instead
of always going through the metered SDK+API-key path.

### Alternatives considered

- Manually running `cursor-agent` inside a Netcatty terminal tab works today and does use
  the subscription's free quota, but it bypasses Catty Agent entirely — no structured tool
  calls, no approval gating, no multi-host orchestration, no chat history integration.
- Setting CURSOR_API_KEY works but bills against the metered API instead of the included
  subscription quota, which defeats the purpose for Enterprise users who already pay for
  Cursor's Auto mode.
- The legacy `acpCommand`/`acpArgs` fields could theoretically point at an arbitrary CLI,
  but these are marked `@deprecated` (pre-SDK migration) in infrastructure/ai/types.ts and
  are not a supported path going forward.

### Related area

AI assistant

### How important is this to you?

Would improve my daily workflow

### Before submitting

- [x] I searched existing issues and discussions for similar requests
