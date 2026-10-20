# Phase 7G.1 defect-and-fix report

Date: 2026-10-16  
Branch requested: `Comp3_Arun`  
Scope: Component 3 only; no recommendation training, commit, or push.

## Claim boundary

The route, localization, camera-callback, and browser results below are synthetic or
local-software results. No physical trolley was moved. No physical camera was
available for this run, so physical disconnect/reconnect, range, lighting, motion
blur, and tag-visibility acceptance remain **PENDING**. Graph coverage opportunities
do not prove camera visibility or localization accuracy.

## Defects, reproduction, and fixes

### Shopping-list update and route visibility

- **Reproduction:** In the customer editor, select Bananas, Bread loaf, and Frozen
  peas. The checkboxes changed locally, but the authoritative list and route did not
  change until the separate `Update route` button was used. Closing the editor hid
  the only pending selection context.
- **Root cause:** The checkbox handler only changed a browser `Set`; it did not issue
  a backend mutation. The later button used `set_products`, whose documented behavior
  initializes a new not-yet-started run. This combined frontend synchronization,
  missing immediate replan, and hidden/collapsed-UI defects; the quantity-aware
  backend mutation path itself was operating correctly.
- **Fix:** Each checkbox now sends a revision-checked `shopping_add` or
  `shopping_remove`. The existing atomic mutation path validates the proposed list,
  computes an anchored route, commits the list, increments shopping and route
  revisions, and returns one confirmed snapshot. The redundant Update Route button
  was removed. Pending, saved, and rejected states are explicit.
- **State preservation:** Dynamic mutations preserve simulation time, estimated
  position, collected quantities, accepted checkpoints, and append-only shopping
  history. Closing `<details id="edit-shopping">` performs no backend action.
- **Test:** The local API reproduced additions of SIM-P-001, SIM-P-002, and SIM-P-006.
  Shopping revisions advanced 0→1→2→3 and route revisions 0→1→2→3; the 1024×768
  customer render showed exactly those three stops and the 30.0 m route.

### Localization warnings

- **Implementation:** `SpatialNavigationSimulation.localization_health()` derives
  `CONFIRMED`, `ESTIMATED`, `SCAN_EXPECTED`, `SCAN_OVERDUE`,
  `OBSERVATION_REJECTED`, or `CAMERA_UNAVAILABLE` from simulation time, graph-path
  distance travelled since acceptance, uncertainty, motion state, camera state, and
  accepted/rejected observations.
- **Thresholds:** expected at 6 s or 3 m; overdue at 12 s or 6 m; candidate graph
  radius 4.5 m plus current uncertainty. Values are serialized in every health
  snapshot and are configurable constants.
- **Candidates:** Active-layout candidates are ordered by graph-path distance from the
  current route anchor. The calculation handles node and mid-edge anchors. It does
  not infer physical visibility and does not assume the next sequential tag ID.
- **Warnings:** Critical warning state is rendered persistently until resolved or
  explicitly acknowledged. Health derivation is a pure snapshot operation, so polling
  does not append duplicate events.

### Camera observation to authoritative position

The tested path remains:

`OpenCV stable marker ID → active-layout lookup → plausibility validation → accepted/rejected record → estimated-position correction → optional anchored route replan → shared state revision → both dashboards`.

An accepted dense marker now replans when its correction exceeds 0.05 m. A rejected
marker records its raw ID, classification, reason, before/after positions, graph
anchor, correction request, and reachable limit without moving the estimate. Ground
truth is never an input to validation and is not changed by a scan.

Regression scenario: CP200 was accepted at the entrance; mapped mid-edge CP231 was
accepted at (1.0 m, 2.5 m), moved only the estimate, and incremented route revision;
distant CP217 was then rejected as `implausible_position_jump`, leaving both the
estimate and last confirmed CP231 unchanged.

### Position and checkpoint visualization

- Customer: labelled `YOU ARE HERE` estimate, finite two-pulse correction feedback,
  current route, next destination/distance, full-map tablet fit, and an optional Tags
  overlay. Simulated ground truth is not sent into the customer rendering path.
- Operator: labelled estimate and synthetic-truth markers, uncertainty circle,
  previous/current routes, finite route-revision highlight, all active-layout tag IDs,
  last accepted, raw/latest, candidate, and rejected tag states. Labels and legends
  supplement color.
- Operator priority: technical health/warnings, camera/raw detections, localization
  map, diagnostics, then audit events. Product and simulation controls are now a
  collapsed secondary panel; Research Execution controls remain available.

## Extended AprilTag layout

The versioned `comp3-dense-apriltag-layout-v2` remains separate from historical maps.
It contains 62 unique AprilTag 36h11 IDs over 37 graph edges, retains CP200, CP201,
and CP202 at their original locations, and records an observed maximum opportunity
spacing of 2.0 m. IDs 203–229 cover additional nodes/junctions/shelf approaches and
IDs 230–261 cover mid-edge localization opportunities. All IDs are within the
selected dictionary's declared maximum 586.

All 62 cards were generated as 90×100 mm PNG/PDF files and decoded before acceptance.
The output includes printable sheets, a manifest, and `placement_sheet.csv` with
coordinates, orientation, graph anchor, purpose, and matching print filename.

## Validation results

- Dashboard/API tests: **128/128 passed**.
- Component backend tests in `component3/.venv`: **136/136 passed**.
- Dense layout: **62/62 unique**, **37/37 edges pass**, maximum opportunity spacing
  **2.00 m**.
- Printable decoding: **62/62 full-layout cards passed**; **9/9 practical subset
  cards passed**.
- Validated research store map: **15/15 checks passed**; historical map unchanged.
- Evidence validator: **113 indexed artifacts passed before this report was indexed**.
- Python compilation, both dashboard JavaScript syntax checks, and `git diff --check`:
  passed.
- Installed headless Chrome rendered customer and operator views at 1024×768. Both
  displayed shared revision 4; customer showed the confirmed three-item list and
  route without page scrolling. Operator showed backend localization health and
  graph-derived candidate IDs. Python Playwright is unavailable, so scripted DOM-click
  browser acceptance remains a tooling limitation; API and source-contract tests cover
  the interaction behavior.

## Practical acceptance matrix

See `phase_7g1_test_results.json`. Software cases A–N and P are covered by automated
tests, API checks, or Chrome rendering as recorded there. Physical case O and any
hardware-dependent portion of E/K remain **PENDING**; their software callback and
state-transition paths passed.

## Changed areas

- `simulations/navigation_dashboard/spatial_simulation.py`, `shared_session.py`,
  `dashboard.py`
- `simulations/navigation_dashboard/static/customer.*`, `static/spatial.*`
- `simulations/navigation_dashboard/tests/test_phase7g.py`,
  `tests/test_phase7b2_dashboard.py`
- `data/apriltag_cards/generate_dense_cards.py` and generated full-layout artifacts

Historical maps, raw POS data, navigation algorithms, previous evidence, AprilTag IDs,
and camera ownership were not replaced.
