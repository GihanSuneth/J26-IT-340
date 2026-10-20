# Architecture-impact report

## Classification

| Concern | Existing implementation | Classification | Impact and reason |
| --- | --- | --- | --- |
| Shortest path | `navigation/dijkstra.py` | Reuse unchanged | Validated non-negative weighted-graph primitive; no Phase 7C requirement invalidates it. |
| Multi-stop order | `navigation/held_karp.py` | Reuse unchanged | Exact optimization for the small destination set remains the comparison and planning method. |
| Route/deviation manager | `navigation/route_manager.py`, `deviation.py` | Extend later | Existing rerouting is endpoint/node anchored. Adaptive starts require a position-anchor abstraction, not a rewrite of Dijkstra/Held–Karp. |
| Dead reckoning/correction | `dead_reckoning.py`, `apriltag.py` | Reuse unchanged | Provides pose propagation and mapped checkpoint correction. Acceptance policy belongs above it. |
| Observation policy | `checkpoint_observations.py` | Extend later | Currently expected-sequence based; needs plausible off-route acceptance and explicit duplicate/unknown/implausible outcomes. |
| Spatial state machine | `spatial_simulation.py` | Extend | Already owns movement, pickup, checkpoint, route, guidance, and evaluation state. Added observation history and explicit route fields. |
| Shared state boundary | previously implicit in `dashboard.py` | New module | `shared_session.py` makes identity, revisions, command idempotency, clock rules, and controller ownership explicit. |
| HTTP controls | `dashboard.py` | Refactor | Dispatch remains mapped to existing methods, but mutations now pass through the session validator under one re-entrant lock. |
| Camera processing | `camera_scanner.py` and callbacks in `dashboard.py` | Reuse/extend | Scanner remains sole camera owner. Validated callbacks now mark authoritative session revisions. No physical-motion claim is added. |
| Pickup state | `RouteManager.confirm_destination_visit`, `confirm_product` | Reuse unchanged | Explicit confirmation and preservation of confirmed destinations already exist. Dynamic list mutation remains deferred. |
| Guidance | `guidance.py` | Reuse/extend later | Existing structured guidance and route revisions are exposed to both views; adaptive events will add instruction transitions later. |
| Customer interface | none | New | Presents list, route, estimate, instruction, checkpoint, shelf/level, pickup, and optional voice from the same session. |
| Research execution UI | `spatial.html/js` | Extend | Existing camera/map/telemetry console retained and moved to session endpoints without losing `/research`. |
| Evaluation | test suites and `component3/evaluation/` | Extend | Added concurrency/session contracts and a prospective adaptive-vs-fixed protocol. Historical artifacts remain unchanged. |

## State ownership and synchronization

`SharedNavigationSession` is instantiated once per local server handler class. Both
views read the same object. `GET /api/session/state` calls a snapshot only. Mutations
use `POST /api/session/control` under `simulation_lock`. Every successful new command
increments `state_revision`; duplicate command IDs return the stored response.
Only the current `controller_id` may issue `step`, preventing two browser identities
from independently moving the deterministic clock.

## Demonstrated requirements and deferrals

The milestone demonstrates one authoritative runtime session and synchronized views.
It deliberately does not add free-walk edges, accept unexpected mapped tags, change
lists during active navigation, or alter route optimization. Those items require the
design in `adaptive_navigation_design.md` and separate evaluation.
