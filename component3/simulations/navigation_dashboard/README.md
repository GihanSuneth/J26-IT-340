# Component 3 offline navigation simulation

The dashboard is a loopback-only, offline software-in-the-loop demonstration.
The root route (`/`) serves a synthetic walkable supermarket demonstration;
the validated research-graph dashboard remains available at `/research`.
Neither view connects to a physical trolley, camera, cloud service, external
API, or internet resource.

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
telemetry. Checkpoint detections are simulated, not camera observations.

`GET /api/spatial/map` returns the validated demonstration map;
`GET /api/spatial/state` returns simulation state and events;
`POST /api/spatial/control` accepts local navigation controls, including
`{"action":"guided_demo"}` for the one-click spatial scenario; and
`GET /api/spatial/export.json` exports the current run state, trails, metrics,
and event history.

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
