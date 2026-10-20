# Shared navigation session

The server owns one in-memory `SharedNavigationSession` per dashboard process. Its
snapshot includes session/map identity; requested, remaining, and collected products;
estimated and simulated-true position; uncertainty; checkpoint history; route and
revision; guidance; camera status; navigation status; and evaluation events.

## Mutation contract

- Reads (`GET /api/session/state`) never call `step` and never increment revisions.
- Mutations use bounded JSON and a validated action allow-list.
- `command_id` gives at-most-once behavior within the process.
- `state_revision` increases after each new successful mutation.
- `client_id` owns the step lease after its first accepted step. A different client
  receives HTTP 409 and cannot change simulation time.
- The controller renews a two-second monotonic lease on each accepted step. If its
  tab closes, another active view can take over after lease expiry without reset.
- A re-entrant server lock serializes camera callbacks and browser mutations.
- The clock advances only by explicit `step(count)` with count 1–40 and fixed 0.25 s.

The compatibility `/api/spatial/*` routes remain available for historical scripts,
but the two maintained Phase 7C interfaces use `/api/session/*`.

## Lifecycle limitations

State and idempotency history are not persisted across server restarts. There is no
authentication or distributed lock. The two-second expiry is a local demonstration
policy rather than an authenticated multi-user coordination protocol.
