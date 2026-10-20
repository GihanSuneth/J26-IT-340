# Component 3 offline navigation simulation

The dashboard is a loopback-only, offline software-in-the-loop demonstration.
The root route (`/`) serves a synthetic walkable supermarket demonstration;
the validated research-graph dashboard remains available at `/research`.
Neither view connects to a physical trolley, cloud service, external API, or
internet resource. The optional Phase 7B.1 mode can read the Mac camera locally;
frames are never uploaded or written by the dashboard.

## Launch

From the repository root:

```bash
python3 -B -m component3.simulations.navigation_dashboard.dashboard
```

Open `http://127.0.0.1:8765/`. Stop with Ctrl-C. An alternate local port is
available:

```bash
python3 -B -m component3.simulations.navigation_dashboard.dashboard --port 8766
```

The server accepts only `127.0.0.1` or `localhost`. Python's standard library
and the existing Component 3 navigation modules are used; no package install
or API key is required. Static files are bundled in `static/`. If the server
stops, the browser displays the local launch command and retries state
synchronization until the server is available again.

## Synthetic supermarket walkthrough

`data/demo_store/v1/demo_store.json` is a versioned, explicitly synthetic
demonstration layout. It defines a 20 m × 14 m boundary, walkable lanes and
intersections, shelf footprints, six synthetic catalog entries, accessible
pickup nodes, and three mapped checkpoints. It is not a replacement for the
validated research map in `data/store_map/`; those graph and AprilTag files
remain unchanged. Synthetic `SIM-P-*` identifiers are not POS records.

`demo_store.py` validates the geometry and derives the graph before a session
can run. The navigation engine uses the existing Dijkstra, Held-Karp, dead
reckoning, deviation monitor, checkpoint-correction, and `RouteManager`
implementations. Motion advances only along validated graph edges, and mapped
pickup points are reached through accessible corridors. The SVG preserves
equal metric x/y scale and labels shelf footprints, pickup nodes, and the three
demonstration checkpoints.

The spatial controls support product selection, route planning, start, pause,
resume, fixed-step advance, reset, speed adjustment, wrong-turn injection, and
explicit simulated pickup confirmation. Product arrival alone does not count
as collection. A deviation is rerouted only after the existing confirmation
policy confirms it. The previous and updated planned routes are distinguished
on the map; detector distance and confirmation sample count appear in the
telemetry. Checkpoint detections remain simulated in manual and guided modes.
The separate Mac Camera Evaluation mode uses genuine OpenCV detections.

`GET /api/spatial/map` returns the validated demonstration map;
`GET /api/spatial/state` returns simulation state and events;
`POST /api/spatial/control` accepts local navigation controls, including
`{"action":"guided_demo"}` for the one-click spatial scenario; and
`GET /api/spatial/export.json` exports the current run state, trails, metrics,
and event history.

### Phase 7B.1 Mac Camera Evaluation

Use the project environment so the ArUco/AprilTag APIs are available:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard
```

Choose products and select **Plan selected products**, then **Start Camera
Evaluation**. Camera mode begins at an entrance gate and waits for real CP200.
Virtual motion resumes only after the existing observation processor accepts
the scan. It pauses again at CP201 and CP202. Product pickups always require
the ordinary explicit confirmation button. Manual and guided modes retain their
existing behavior.

Camera endpoints are loopback-only:

- `GET /api/camera/state` returns connection, live IDs, consensus state,
  validation outcome, and bounded scan records.
- `GET /api/camera/export.json` downloads those scan records as local JSON.
- `POST /api/camera/control` with `{"action":"refresh"}` probes indices through
  AVFoundation and returns only devices that open and produce a readable frame.
- `POST /api/camera/control` with `{"action":"start","camera_index":0}` opens
  a camera from that verified inventory.
- `POST /api/camera/control` with `{"action":"switch","camera_index":1}` fully
  releases the previous capture before opening another verified camera.
- `POST /api/camera/control` with `{"action":"stop"}` releases it and safely
  pauses an active camera-mode run.
- `POST /api/spatial/control` with `{"action":"camera_evaluation"}` creates the
  gated virtual-navigation session; it does not open a camera itself.

Before dashboard evaluation, probe available indices without opening GUI windows:

```bash
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.apriltag_camera_smoke_test \
  --probe-cameras
```

The probe reports each device's open/frame-read status, dimensions, backend, and
errors, releasing each device before opening the next. The dashboard's
**Refresh Cameras** button performs the same verification after a Continuity
Camera connects. Names come from macOS `system_profiler` when exposed; otherwise
the verified OpenCV index is shown. Switching uses the scanner's single capture
lifecycle and releases the old device first.
For a headless AprilTag smoke scan that deliberately does not submit navigation
observations, run:

```bash
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.apriltag_camera_smoke_test \
  --camera-index 0 --no-preview
```

The scanner prints stable detected IDs. Stop with Ctrl-C; the camera is released
on shutdown. OpenCV's native preview is intentionally not used because native
GUI operations from the camera worker are not reliable on macOS. The embedded
dashboard preview shares the scanner's single capture lifecycle and never opens
a second browser-owned session or changes detector input.
By default, up to five consecutive read failures or two seconds without a
successful read marks the camera disconnected and pauses camera-assisted
navigation. A recovered read resets only partial consensus (not duplicate
suppression). Frame processing is limited to 15 FPS by default. These values
can be configured for the smoke test with `--max-consecutive-read-failures`,
`--read-recovery-timeout`, and `--max-fps` (capped at 60 FPS).
On macOS, grant Camera access to the launching Terminal or Python host in
**System Settings > Privacy & Security > Camera**, then fully restart that host
if permission changed. An unavailable camera is reported and never replaced
with synthetic observations.

Generate detector-verified print cards with:

```bash
component3/.venv/bin/python component3/data/apriltag_cards/generate_cards.py
```

See `docs/evaluation/phase7b1_mac_camera_implementation.md` for the complete
workflow, rejection cases, and physical-camera acceptance status.

### Phase 7A structured guidance

`guidance.py` classifies maneuvers from signed route-segment angles and emits
structured, deduplicated events. Product instructions use validated section,
shelf level, bay, pickup node, and shelf-facing geometry from the versioned
synthetic catalog. Arrival requires two confident dead-reckoned estimates
within the configured radius; simulation truth never grants arrival.

`checkpoint_observations.py` separates a tag observation from map correction.
To submit a synthetic or future detector observation, post:

```json
{
  "action": "observe_checkpoint",
  "observation": {
    "tag_id": 201,
    "timestamp_s": 12.5,
    "detection_source": "external_simulated_input",
    "map_id": "comp3-synthetic-supermarket-demo-v1",
    "confidence": 0.95
  }
}
```

The server validates sequence, duplication, time, map, known ID, and
confidence before calling the existing checkpoint correction function. This
interface does not claim live camera support. The UI distinguishes the last
observation, accepted checkpoint, and localization correction, and offers
optional browser speech that is disabled by default.

Run Phase 7A tests and evaluations from the repository root:

```bash
python3 -B -m unittest -v component3.simulations.navigation_dashboard.tests.test_phase7a_guidance
python3 -B -m component3.simulations.navigation_dashboard.phase7a_evaluation
python3 -B -m component3.simulations.navigation_dashboard.phase7a_browser_acceptance
```

## Simulation design

- `engine.py` owns deterministic physical-time state and delegates route
  ordering, shortest paths, dead reckoning, deviation detection, localization,
  route replacement, and explicit stop confirmation to the existing
  `Held-Karp`, `Dijkstra`, `DeadReckoner`, `RouteDeviationMonitor`, and
  `RouteManager` implementations.
- `sensors.py` produces seeded synthetic wheel-displacement and IMU-yaw
  measurements. Ground-truth x/y is maintained separately and is not passed to
  the estimator or deviation detector.
- A physical simulation sample is always 0.25 seconds. Playback rate controls
  how many fixed samples the local UI requests per refresh; it does not change
  the simulation clock step. Trolley movement speed is separately configurable.
- At `/research`, movement interpolates along the existing research graph. Its
  boundary, nodes, edge connections, aisle labels, and eight checkpoint
  coordinates come from `data/store_map/`.
- Checkpoints are simulated tag observations only. A mapped checkpoint snaps
  the estimator to the existing configured location and records a correction
  event. This is not camera detection or hardware localization.
- Detector input is the dead-reckoning estimate. The existing three-sample
  confirmation and recovery policies are used. A confirmed reroute is latched
  by `RouteManager`; failed localization stops movement and preserves the
  previous route and remaining stops.
- After localization, the existing route manager chooses a graph endpoint and
  uses node-only routing. When the trolley is on a partial edge, the simulator
  physically follows mapped edges to the selected anchor; it does not jump to
  that anchor. The omitted partial-edge distance is not included in the
  node-only reroute cost and is explicitly labeled.
- Passing a destination does not mark it visited. Normal runs stop at a
  selected destination until **Confirm shopping stop** is pressed. The guided
  demonstration records an explicit simulated confirmation event at each
  selected stop.

## Spatial controls and research-graph guided scenario

The normal controls provide destination selection, route calculation, start,
pause, resume, fixed-step advance, reset, movement speed, playback rate,
encoder/IMU noise, a wrong-turn request at a later graph junction, and explicit
shopping-stop confirmation.

The root spatial dashboard exposes manual controls independently and also has
a prominent **Start Guided Demo** action. One click safely resets the spatial
simulator, selects synthetic Bananas (`SIM-P-001`) and Frozen peas
(`SIM-P-006`), calculates the Held-Karp/Dijkstra route, and starts at the
entrance. The server-owned state machine then follows lane edges, reports live
guidance and checkpoints, records clearly labeled automated *simulated* pickup
confirmations, injects one valid alternate edge, waits for the existing
deviation monitor, accepts the existing `RouteManager` replacement route, and
finishes at checkout. Seed `6042` and fixed 0.25-second samples make repeated
runs identical. Browser polling advances this authoritative state machine but
does not decide collection, deviation, reroute, or completion.

Guided stages are: initial route calculated; leaving the entrance; navigating
to Bananas; Bananas pickup; wrong turn and deviation confirmation; replacement
route active; Frozen peas pickup; navigating to checkout; and demonstration
complete. Pause, resume, reset, trolley speed, playback rate, remaining
distance, stage, instruction, checkpoint, collected products, reroute count,
completion summary, and the chronological event log remain visible. Reset
returns to ordinary manual mode; manual mode never auto-confirms a product or
injects a wrong turn.

**Start guided demo** in `/research` uses seed `6042`, the default B1/B3/B5
destinations, and fixed 0.25-second samples. It plans with the existing
algorithms, follows the mapped entrance route, accumulates synthetic
dead-reckoning drift, applies simulated AprilTag corrections, takes the valid
B4-to-M4 alternate edge, waits for detector confirmation, recalculates once,
physically returns along mapped edges when endpoint anchoring requires it,
confirms the selected stops, and reaches checkout. The run is reproducible for
identical configuration and actions. All truth, estimate, and algorithm events
are labeled separately.

## API and exports

Phase 7C adds two synchronized views over one server-owned session:

- `/customer` — map-first customer navigation with a live position marker,
  turn-by-turn banner, highlighted remaining route, aisle/bay/shelf directions,
  product stops, checkpoint sequence, pickup confirmation, and optional voice.
  In live AprilTag mode, the page shows the continuously running scanner state
  and expected checkpoint; an early or distant tag is rejected without changing
  the customer's location.
- `/` — research execution view with camera, map, localization, route revisions,
  rejection reasons, metrics, and timeline.
- `/research` — preserved validated research-graph dashboard.

`GET /api/session/state` is read-only. `POST /api/session/control` accepts a
validated `client_id` and idempotent `command_id`; only one client can advance
the fixed-step clock. Refreshing either page does not reset the session.

- `GET /api/map` — validated graph, sections, destinations, and checkpoints.
- `GET /api/simulation` — current state, telemetry, trajectories, metrics, and
  chronological event log.
- `POST /api/simulation/control` — local JSON control actions: `start`,
  `pause`, `resume`, `step`, `reset`, `set_destinations`, `configure`,
  `wrong_turn`, `confirm_stop`, and `guided_demo`.
- `GET /api/simulation/export.csv` and `/api/simulation/export.json` — current
  truth/estimate samples, events, and metrics.

The event and telemetry output distinguishes simulated truth, sensor-only
estimates, simulated checkpoint corrections, detector states, and route-manager
decisions. Position-error values compare truth and estimate for evaluation and
display only; they do not influence route decisions.

Real-browser acceptance can be reproduced where Playwright Chromium is
available:

```bash
python3 -B -m component3.simulations.navigation_dashboard.browser_acceptance
```

It captures the nine required guided states without overwriting earlier
evidence and writes the completed browser state and summary metrics under
`component3/evaluation/navigation_simulation/`.

## Reproducible evaluation and tests

Run the scenario evaluator from the repository root:

```bash
python3 -B -m component3.simulations.navigation_dashboard.evaluation
```

It writes measured scenario results to
`component3/evaluation/navigation_simulation/navigation_simulation_results.json`
and guided-demo samples/events to
`component3/evaluation/navigation_simulation/guided_demo_telemetry.csv`.
Scenarios include normal/noisy movement, a brief unconfirmed detector episode,
checkpoint correction, confirmed and failed rerouting, duplicate suppression,
explicit shopping-stop confirmation, checkout completion, controls, and
deterministic replay.

Run simulator and dashboard adapter tests:

```bash
python3 -B -m unittest -v \
  component3.simulations.navigation_dashboard.tests.test_simulation \
  component3.simulations.navigation_dashboard.tests.test_adapter
```

The tests cover graph-constrained motion, estimator separation, deterministic
sensors and replay, checkpoint correction, route-manager integration,
confirmation thresholds, safe failed rerouting, visit confirmation, reset and
controls, HTTP input validation, and CSV/JSON exports. Run all navigation
dashboard tests, including the synthetic spatial map and API suite, with:

```bash
python3 -B -m unittest -v \
  component3.simulations.navigation_dashboard.tests.test_simulation \
  component3.simulations.navigation_dashboard.tests.test_adapter \
  component3.simulations.navigation_dashboard.tests.test_spatial_simulation
```

The UI uses bundled HTML/CSS/JavaScript/SVG and preserves equal x/y metric
scale. No dependency installation or external service is needed.

## Phase 7B.2 dashboard

The main `/` view now separates shopping, the metric map, local camera
evaluation, guidance/voice, and results. Use **Refresh Cameras**, choose a
frame-verified device, then **Select Camera** before starting. The selector is
rebuilt from successful open-and-read probes rather than fixed MacBook/iPhone
index assumptions. A device name is displayed only when macOS supplies one.

Live preview frames come from the authoritative Python scanner through
`GET /api/camera/preview.jpg`; the browser never opens the camera. The scanner
keeps only one throttled, bounded JPEG in memory. Voice navigation is optional
and off by default, with event-ID deduplication and cancellation on disable or
route revision.

Run the new viewport and voice acceptance with:

```bash
python3 -m component3.simulations.navigation_dashboard.phase7b2_browser_acceptance
```

## Phase 7D adaptive navigation

Use **Enter free walk**, select only one of the displayed connected graph edges, and
stop/resume at any point. **Navigate from here** constructs a node or mid-edge anchor,
retains the partial-edge distance, and optimizes the remaining products plus checkout
with the existing Dijkstra/Held–Karp stack. Both `/customer` and `/` read the same
server session; GET polling is non-mutating and only the explicit movement controller
posts deterministic 0.25 s steps.

Mapped off-route checkpoint observations are accepted only when online graph distance,
elapsed simulation time, uncertainty, map version, source and motion limits make them
plausible. Rejected observations do not change pose, checkpoint or route. Simulated
truth is used only for evaluation metrics.

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.phase7d_evaluation
python3 -B -m component3.simulations.navigation_dashboard.phase7d_browser_acceptance
```

## Phase 7E dynamic shopping

The customer catalog supports live add, remove, increase and remaining-quantity
decrease commands. Each command carries the displayed shopping revision; stale
commands return HTTP 409, and duplicate command IDs return their first stored result.
One explicit pickup confirms one unit. The Research view shows shopping/route
revisions, old/new costs, anchor, reason, timing and the shared event stream.

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.phase7e_evaluation
python3 -B -m component3.simulations.navigation_dashboard.phase7e_browser_acceptance
```

## Phase 7G practical demonstration

`/customer` is the tablet shopper display; `/` is the authorized operator/research
view. Customer Start uses the singleton backend autoplay clock, while the operator
view retains deterministic manual stepping. Product arrival always stops for an
explicit Picked up or Skip decision. Skip can defer the item until after the trolley
leaves the shelf, or remove only its remaining requested quantity.

The optional dense layout is `component3/data/demo_store/v2/dense_apriltag_layout.json`.
Regenerate its coverage report and the smaller practical cards with:

```bash
component3/.venv/bin/python -m component3.data.demo_store.generate_dense_layout
component3/.venv/bin/python -m component3.data.apriltag_cards.generate_dense_cards
```

See `component3/PHASE_7G_DEMO_GUIDE.md` for the two demonstration modes, claim
boundaries, future trolley event contract and acceptance checklist.

### Phase 7G.1 reliability behavior

Customer product selections now use immediate quantity-aware shopping mutations; each
confirmed mutation automatically recalculates the anchored route and updates every view.
There is no separate customer Update Route step. The operator view exposes the
backend-derived `localization_health` record and all IDs in the active dense layout.
The full 62-card printable set and placement CSV are in
`component3/data/apriltag_cards/generated_dense_all/`. Physical visibility and camera
performance remain unmeasured.
