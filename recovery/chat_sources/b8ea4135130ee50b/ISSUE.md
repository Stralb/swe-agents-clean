# Issue

Web chat auth mismatch: CLI uses Codex OAuth, but send-stream still fails with 401 invalid_api_key

## Summary

A Hermes Workspace web chat path fails with a 401 `invalid_api_key` error, even though the CLI side is authenticated via Codex OAuth.

This looks like an auth-source mismatch between the CLI OAuth state and the web UI chat backend path.

## What we observed

- In CLI, we are logged in with Codex OAuth.
- The web UI chat loads for a while, then fails.
- The failing runtime error is:

`OpenAI-compatible chat: 401 {"error":{"message":"Invalid API key","type":"invalid_request_error","code":"invalid_api_key"}}`

## Why this looks like a bug

The CLI auth flow is working, but the web chat path does not appear to consume the same auth/token source.

Based on the code:
- `F001` reads bearer auth from:
  - `HERMES_API_TOKEN || CLAUDE_API_TOKEN`
- `src/routes/api/oauth.poll-token.ts` stores OAuth tokens in:
  - `~/.hermes/auth.json`
- `src/routes/api/send-stream.ts` falls back from `/v1/responses` to `/v1/chat/completions`
- the failure happens in that OpenAI-compatible chat path

So the likely issue is that the web chat backend is not bridged to the same Codex OAuth-authenticated state that the CLI uses.

## Expected behavior

If the CLI is authenticated with Codex OAuth, the web UI chat should be able to use the same authenticated provider/session state, or clearly surface that a separate token/env setup is required.

## Actual behavior

The web UI chat reaches the send path, but the backend returns 401 `invalid_api_key`.

## Notes

This does not look like just a missing URL override.
It looks like a token-source / auth bridge problem between:

- CLI Codex OAuth auth
- web UI chat backend auth

If the intended architecture is to keep these separate, the UI should probably explain that clearly instead of failing with a generic API key error.

