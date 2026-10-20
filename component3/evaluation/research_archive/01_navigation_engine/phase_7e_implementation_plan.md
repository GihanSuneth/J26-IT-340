# Phase 7E implementation plan — dynamic shopping sessions

## Audited baseline

The Phase 7D simulator stores requested products as a deduplicated tuple and remaining
products as another tuple. Collection is inferred by tuple difference. A pickup
confirms an entire product ID, and `RouteManager` stores unique pickup-node
destinations. This is compatible with quantity one, but cannot represent partial
quantities, preserve a removed collected line, or distinguish customer and accepted
recommendation sources. `SharedNavigationSession` already serializes requests under
the dashboard lock, rejects stale state revisions, and deduplicates command IDs.
Camera callbacks acquire that same lock. Route anchors already account for node and
mid-edge starts and compose exact partial-edge cost with existing Dijkstra/Held–Karp.

Backward-compatible fields used by Phase 7A–7D tests and both views are
`selected_product_ids`, `remaining_products`, `collected_product_ids`, active product,
route-manager destinations, route revisions, checkpoint history, and guidance events.
They must remain available while the quantity-aware model becomes authoritative.

## Implementation sequence

1. Add a small quantity-aware `ShoppingSession` domain model with validated catalog
   IDs, requested/collected/remaining quantities, source metadata, list revision and
   append-only mutation/pickup events. Validate a proposed change before committing it.
2. Initialize it from the legacy selected-product tuple and derive the legacy snapshot
   fields from it. Preserve reset behavior without erasing the requested list.
3. Add atomic add/remove/quantity/pickup operations. Require an expected shopping-list
   revision for live mutations, while retaining `set_products` as the pre-start legacy
   compatibility command.
4. Before committing a list mutation, calculate an anchored Held–Karp route for the
   proposed unique remaining pickup nodes. Reject an unreachable proposal without
   changing shopping, localization, route or history. On success, commit and publish
   the proposed route as one locked command, preserving position and checkpoint state.
5. Confirm one unit per explicit pickup. Keep a pickup node in the route while any
   product quantity at that node remains. Never infer pickup from an AprilTag.
6. Add a recommendation contract whose suggestions are inert until an explicit
   acceptance command enters the same mutation/reoptimization pipeline.
7. Extend customer controls and research diagnostics without changing the server-owned
   camera pipeline or allowing GET polling to advance time.
8. Add domain, simulator, HTTP concurrency/idempotency and two-view tests; then run a
   deterministic comparative evaluation with equal-demand comparisons and repeated
   timing samples.

## Concurrency and session policy

All API commands and camera callbacks remain serialized by the existing re-entrant
server lock. Command IDs are deduplicated before dispatch. Dynamic mutations require
the current shopping-list revision in addition to the optional global state revision.
A failed validation or route calculation performs no mutation. A completed checkout
may be reopened by adding a product: the current checkout position becomes the route
anchor, collected history is retained, and the session returns to a stopped navigation
state until the customer starts or requests movement.

## Optimization claim boundary

Held–Karp is exact over the set of unique remaining pickup nodes for this small demo
catalog, with shortest-path legs supplied by Dijkstra and exact partial-edge anchor
cost included. Quantity does not duplicate a shelf destination. The claim does not
extend to large catalogs, time-dependent constraints, inventory, or physical motion.
