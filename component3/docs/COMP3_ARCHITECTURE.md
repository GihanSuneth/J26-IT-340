# Component 3 architecture

## Current system

Component 3 is a local research prototype with a validated navigation library, a
synthetic supermarket simulation, camera-assisted AprilTag observation pipeline, and
two synchronized dashboard views.

```text
Customer View (/customer) ─┐
                           ├─ /api/session/* ─ SharedNavigationSession
Research Execution (/) ────┘                         │
                                                    ▼
CameraScanner ─ validated observations ─ SpatialNavigationSimulation
                                                    │
                Dijkstra · Held–Karp · DeadReckoning · DeviationMonitor
                RouteManager · CheckpointProcessor · GuidanceEngine
```

The validated historical graph dashboard remains at `/research`. The Phase 7C views
share one in-memory session, map, products, pose, clock, route, checkpoint history,
guidance stream, camera state, and event timeline.

Phase 7D adds a graph-constrained free-walk state machine, reusable node/edge route
anchors, adaptive checkpoint plausibility and correction, and exact anchored
Held–Karp replanning. Camera recognition, validation, correction and replanning remain
separate recorded stages.

Phase 7E adds a quantity-aware `ShoppingSession` beneath the compatibility product-ID
fields. Shopping revision checks, command deduplication and the existing server lock
make add/remove/quantity/pickup operations atomic with anchored route validation.
Camera callbacks share the lock, and recommendations remain inert until acceptance.

Phase 7F leaves the engine unchanged and adds a deterministic evaluation layer. The
runner exercises public algorithms and session operations, keeps simulated truth out
of localization inputs, verifies small optimized routes against exhaustive
permutations, and emits versioned raw/aggregate/table evidence. A separate browser
wrapper reruns maintained Phase 7C–7E flows without replacing their historical files.

Phase 8A adds an offline recommendation-preparation boundary. A read-only CSV audit
feeds normalized-name basket reconstruction, a frozen chronological split, catalog
reconciliation, four transparent baselines, and metric functions. Derived artifacts
live under `data/derived/recommendation_phase8a/`; no final model or recommendation
quality result exists. Source product IDs are not used as SKUs because every ID maps
to multiple names.

Phase 8B implements the offline fitting/evaluation layer without connecting predictions
to either dashboard. Four statistical baselines and a NumPy bag-of-items linear ranker
share the frozen Phase 8A vocabulary and examples. JSON artifacts are reloadable through
`recommendation/inference.py`. Association rules are the validation-selected artifact;
the existing explicit-acceptance navigation path remains unchanged and unused by model
predictions in this phase.

```text
ignored raw POS CSV (read only)
        │ audit + strict parsing
        ▼
normalized-name baskets ── chronological split ── model evaluation (Phase 8B)
        │
        └─ catalog crosswalk ─ output contract ─ explicit acceptance
                                                   │
                                  atomic shopping mutation + route replan
```

## Authoritative session and clock

`shared_session.py` supplies session/map identity, revisioning, idempotent command
IDs, a single step-controller lease, and a read-only snapshot contract. The server's
re-entrant lock serializes commands and camera callbacks. Simulation time changes only
on accepted `step` commands; each step is a deterministic 0.25 seconds. Page load,
refresh, and GET polling cannot advance time or reset state. The controller renews a
two-second monotonic lease, allowing another open view to continue after it closes.

## Implemented features

- Dijkstra shortest paths and Held–Karp destination ordering.
- Graph-constrained deterministic motion, dead reckoning, checkpoint correction,
  deviation detection, and route-manager rerouting.
- Explicit product confirmation and shelf-level guidance.
- Manual, guided, and real-camera-assisted virtual modes.
- Optional browser speech, real local preview, observation rejection reasons, and
  downloadable evaluation state.
- Shared customer/research views and multi-view clock protection.
- Junction-based free walk with stop/resume and deterministic edge motion.
- Exact node or mid-edge route starts with explicit partial-edge cost and direction.
- Expected and plausible unexpected mapped-checkpoint correction without a truth oracle.
- Remaining-destination replanning that preserves list, confirmations and prior route.
- Live add/remove/increase/decrease operations with requested, collected and remaining quantities.
- Explicit one-unit pickup, append-only shopping events and monotonic list revisions.
- Customer-accepted demonstration recommendation contract with no fabricated score.
- Phase 8A POS audit, basket derivation, leakage-safe split, baseline implementations,
  metric definitions, and guarded POS-to-demo catalog crosswalk.
- Phase 8B deterministic model fitting, validation selection, frozen test evaluation,
  safe JSON artifacts and offline inference contract.

## Status boundaries

Persistent/distributed sessions, calibrated physical localization, large-catalog
optimization and dashboard recommendation integration are not implemented. The only POS-shaped
source has unknown provenance/license and cannot support real-transaction claims.
Camera observations
must not be described as physical trolley movement. Detailed audit and evidence are indexed at
`component3/evaluation/research_archive/README.md`.

## Phase 8C live recommendation integration

The unchanged association artifact is loaded through a checksum-verified process cache.
Only verified normalized-name mappings become actionable. Suggestions are bound to one
shopping revision; explicit acceptance uses the existing atomic mutation and node/mid-
edge route optimizer, while dismissal is non-mutating. Customer and operator views read
the same state. Operator-only diagnostics expose ranking, filters, timings and decisions.
The integration is experimental and limited to four verified mappings.
