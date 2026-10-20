# Phase 8C architecture and implementation

## Data flow

```text
authoritative ShoppingSession revision
  → verified demo-ID / normalized-name crosswalk
  → process-cached frozen association model
  → original model ranking
  → selected/collected/dismissed + catalog/shelf/graph filters
  → optional anchored Held–Karp detour calculation
  → revision-bound experimental recommendation
  → explicit accept → existing atomic shopping add → anchored route replan
```

`live_service.py` verifies SHA-256
`a1d4c70d26d7b816dc447b7478538e47791541b8dad346ec04391f53e58850cb`
before loading `selected_model.json`. It is cached once per backend process, never
trains, and never reads split assignments, predictions, or held-out labels. Failure
disables recommendations while leaving navigation operational.

Only Bananas, Bread loaf, Milk carton, and Pasta convert to normalized vocabulary.
Cereal box and Frozen peas remain unmapped. The full frozen ranking is retained in
operator diagnostics. Candidates are removed for empty input, existing list/collection
state, prior session dismissal, missing mapping, or invalid shelf/pickup references.

Accept validates ID and revision, uses the atomic add, increments shopping revision
once, and replans from the current node/mid-edge anchor. Dismiss records an event and
leaves list/route unchanged. Shared command IDs make retries idempotent. Detour is the
anchored optimized remaining cost difference with and without the candidate; it does
not affect model ordering or mutate the route.

The customer card is compact, explicitly experimental, and shows verified product,
shelf and optional route distance without scores or personalization claims. The operator
panel shows model identity/checksum, input, ranking/filter reasons, timings, fallback,
events and revisions below higher-priority localization health.

Phase 7 had a hardcoded `DEMO-R-001` Frozen peas suggestion plus the atomic navigation
path. Phase 8C replaced only that suggestion source and added model/filter/revision
evidence around the existing route architecture.
