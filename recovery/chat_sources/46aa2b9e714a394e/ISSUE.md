# Issue

Add a bidirectional Buzz communication adapter for Squad Chat

Parent: #904
Depends on: #905

## Objective

Extend the completed provider-neutral communication-adapter foundation with a native Buzz adapter that round-trips mapped Squad Chat messages and replies through a Buzz channel with durable replay, deduplication, authorship, thread, and audit semantics.

## User outcome

An operator maps a Veritas Squad Chat target to one Buzz community/channel. A message sent from either side appears once on the other side with the correct author, timestamp, thread/root relationship, delivery state, and external link. Disconnect/reconnect or process restart does not lose or duplicate accepted events.

## Current state

- Veritas's shared adapter contract already models provider, delivery/reply modes, Squad/task/run/approval/notification targets, thread mappings, health, and audit: [`F010`](https://github.com/[REPOSITORY]/blob/b704ab92d0c108739f1cfb62be4a66d8bd208187/F010#L3-L130).
- The service already implements redacted configuration, send, mapping, reply ingestion, `externalReplyId` dedupe, sanitization, audit, and disconnect behavior: [`F002`](https://github.com/[REPOSITORY]/blob/b704ab92d0c108739f1cfb62be4a66d8bd208187/F002#L30-L560).
- Buzz is Nostr-first. The relay exposes WebSocket/NIP-11 plus a narrow authenticated `/events`, `/query`, `/count` HTTP bridge: [`router.rs`](https://github.com/block/buzz/blob/acfbb1bb6af54cb29cb152496ff43b8285dcb8cf/crates/buzz-relay/src/router.rs#L28-L141).
- Buzz's own ACP harness reconnects with a `since` filter, queues per channel, and replays unprocessed mentions: [`buzz-acp` lifecycle](https://github.com/block/buzz/blob/acfbb1bb6af54cb29cb152496ff43b8285dcb8cf/crates/buzz-acp/README.md#L242-L253).

## Architecture

Add a provider implementation behind the generic service:

- **Outbound:** create and sign the exact supported Buzz message/reply event using the configured identity; send through the authenticated relay contract; persist the returned Buzz event ID against the Veritas delivery ID.
- **Inbound:** maintain one supervised WebSocket subscription per enabled Buzz connection/community, restricted to explicitly mapped channels and an allowlist of supported message/reply/edit/delete kinds.
- **Mapping:** retain the existing Veritas target mapping and add a typed Buzz coordinate `{ community, channelId, eventId?, authorPubkey?, kind? }`.
- **Cursor:** persist a total order `(created_at, event_id)` through storage. Commit it only after the Veritas projection and audit entry are durable.
- **Replay:** reconnect with a bounded overlap window; dedupe by `(community, event_id)`; never use timestamp alone.
- **Loop prevention:** store outbound event IDs and a Veritas-origin/idempotency marker where the Buzz contract permits. Do not re-ingest the adapter's own outbound event as a new user reply.
- **Ambiguous delivery:** preserve `delivery_unknown`, query/reconcile by event ID/idempotency marker, then retry only when safe. Buzz's CLI intentionally avoids blind replay of ambiguous non-idempotent writes; the adapter must match that guarantee.

The long-lived transport is native protocol code, not a spawned `buzz` CLI. The optional CLI remains a doctor/support tool from #905.

## Initial supported projection

| Buzz surface | Initial behavior |
| --- | --- |
| Stream root message | Create one Squad Chat message in the mapped target. |
| Stream reply | Create one threaded Squad Chat reply and store root/reply coordinates. |
| Veritas root/reply | Publish a Buzz root/reply with a stable delivery mapping. |
| Message edit | Apply only if Squad Chat has an explicit edit contract; otherwise record a bounded audit event and retain original text. |
| Message delete | Apply only if Squad Chat has an explicit tombstone/delete contract; otherwise record deletion metadata without destructive local removal. |
| Reactions, canvas, files, forums, DMs | Deferred unless required to preserve a referenced message safely. |
| Unknown kind | Ignore with redacted, rate-limited telemetry. |

## Scope

- `buzz` provider implementation for the existing communication service.
- Typed Buzz external coordinates, delivery metadata, cursor/checkpoint, and provider health.
- Supervised connection lifecycle with enable, reconnect, backoff/jitter, disconnect, and clean shutdown.
- Mapping API/UI for one connection/community/channel to one supported Veritas target.
- Root/reply outbound and inbound projection, external links, public author identity, and sanitized content.
- Delivery/audit UI that exposes queued/sent/unknown/failed/replayed/ignored states.
- Explicit support matrix for edits/deletes and unsupported event kinds.
- Operator docs for channel membership, least scopes, mapping, replay, and troubleshooting.

## Non-goals

- Running an ACP agent or creating a Veritas task from every Buzz message.
- DMs, forum voting, canvas synchronization, presence/typing, media upload, moderation, workflows, or NIP-34 projection.
- A polling loop when the WebSocket subscription is healthy.
- Treating Buzz as a broad `AgentProvider`.
- Reading Buzz Desktop internal SQLite/state or delegating correctness to `buzz-acp`.
- Automatic channel creation or membership management.
- Destructive local deletion when Buzz emits a deletion event without an equivalent Veritas contract.

## Security and reliability

- Require #905 healthy identity/community/membership evidence before connecting or sending.
- Subscribe only to mapped channel IDs and an explicit kind allowlist.
- Verify relay/event identity and retain signed author pubkey as external metadata.
- Sanitize message content using the existing adapter path; do not render raw HTML or unsafe links.
- Bound event size, batch size, reconnect backlog, overlap window, retry count, telemetry cardinality, and stored diagnostics.
- Separate `relay_connected`, `subscription_active`, `last_event_at`, `cursor_lag`, `last_send`, and `last_error` health facets.
- Stop reconnecting on authentication, community, membership, or unsupported-contract errors until configuration/evidence changes.
- Never include private keys, tokens, auth tags, raw request headers, or unredacted relay URLs in audit/log output.

## Acceptance criteria

- [ ] A mapped Veritas root message publishes once to the configured Buzz channel and stores the returned event coordinate.
- [ ] A mapped Veritas reply publishes with the correct Buzz root/reply relationship.
- [ ] An inbound Buzz root and reply project once into the correct Squad Chat target/thread with public author, timestamp, external coordinate, and audit entry.
- [ ] Restart after cursor persistence resumes without loss; overlap replay produces no duplicate messages.
- [ ] A crash between Veritas projection and cursor persistence replays safely and dedupes by Buzz event ID.
- [ ] An adapter-originated Buzz event does not echo back as a new user message.
- [ ] Ambiguous outbound results remain visible and are reconciled before retry.
- [ ] Mapping conflicts, missing roots, out-of-order replies, deleted roots, unknown authors, malformed events, and unsupported kinds have deterministic behavior.
- [ ] Health distinguishes transport, subscription, cursor, authorization, and send status with actionable reasons.
- [ ] Disabling/disconnecting the adapter closes workers cleanly without deleting mappings or cursor state.
- [ ] Existing Microsoft Teams communication behavior remains compatible.

## Tests

- Unit tests for event mapping, external coordinates, reply roots, cursor ordering, dedupe, loop prevention, edit/delete policy, content sanitization, and error classification.
- Fake-relay contract tests for auth failure, membership failure, malformed/oversized events, disconnect/backoff, overlap replay, out-of-order replies, duplicate event IDs, unknown kinds, and ambiguous sends.
- Persistence test that restarts the adapter between projection and cursor commit.
- Route/access tests for mapping, send, health, delivery, disconnect, and read/write permissions.
- React tests for mapping form, health facets, delivery-unknown state, external links, and accessible controls.
- Credential-free E2E: Veritas sends root/reply; fake Buzz sends root/reply; both sides contain exactly one correctly threaded projection after a forced reconnect.
- Optional live smoke against the pinned Buzz release, including actual reply delivery and thread retrieval.

## Dependencies

- **Parent:** #904
- **Depends on:** #905 connection/identity/compatibility diagnostics.
- **Reuses:** closed #739 communication adapter and existing Squad Chat APIs.
- **Does not depend on:** #870 ACP. Communication and execution remain independent seams.
- #850/#874 are not required for chat delivery; the workflow-trigger child depends on them.

## Risks and rollback

- Buzz thread-following is under active upstream repair ([Buzz #2270](https://github.com/block/buzz/issues/2270)). Pin and test exact root/reply behavior.
- CLI TLS issues ([Buzz #2308](https://github.com/block/buzz/issues/2308)/[Buzz #2457](https://github.com/block/buzz/issues/2457)) reinforce using native protocol for the worker.
- A naive timestamp cursor can lose same-second events. Use `(created_at, event_id)`.
- Rollback disables the Buzz worker while retaining redacted configuration, mappings, cursor, and audit state for recovery.

## Primary evidence

- [Buzz relay route inventory](https://github.com/block/buzz/blob/acfbb1bb6af54cb29cb152496ff43b8285dcb8cf/crates/buzz-relay/src/router.rs#L28-L141)
- [Buzz CLI message examples](https://github.com/block/buzz/blob/acfbb1bb6af54cb29cb152496ff43b8285dcb8cf/crates/buzz-cli/README.md#L27-L43)
- [Buzz CLI retry/ambiguity handling](https://github.com/block/buzz/blob/acfbb1bb6af54cb29cb152496ff43b8285dcb8cf/crates/buzz-cli/src/client.rs#L78-L126)
- [Buzz ACP reconnect/replay semantics](https://github.com/block/buzz/blob/acfbb1bb6af54cb29cb152496ff43b8285dcb8cf/crates/buzz-acp/README.md#L242-L253)
- [Veritas communication types](https://github.com/[REPOSITORY]/blob/b704ab92d0c108739f1cfb62be4a66d8bd208187/F010#L3-L130)

## Planning metadata

- Priority: High
- Size: L
- Actionable after: #905



## Documentation requirement

Document channel mapping, least scopes, thread/edit/delete support, replay and cursor behavior, delivery-unknown recovery, health facets, and safe disable/rollback in the Buzz operator guide.

## Compatibility and migration

The provider union and external-coordinate metadata are additive. Existing Teams mappings/deliveries remain readable and unchanged. New cursor/origin fields need storage defaults and a reversible migration through the storage abstraction; no historical message rewrite is required.

## Unlocks

- #911 Buzz event-to-workflow trigger bridge
- #912 composed compatibility gate

