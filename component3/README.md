# Component 3 — Recommendation, Navigation, and CNN Aisle Recognition

**Owner:** comp3

## Responsibility

Component 3 recommends extra items worth a detour, routes the trolley through
the confirmed to-buy list, tracks position between checkpoints, and optionally
classifies the current aisle using a CNN.

## Workspace structure

```text
backend/comp3_reco_navigation/  API, recommendation, navigation, CNN, and tests
data/raw/                       Local population-level POS CSV
data/processed/                 Reproducible recommendation outputs
data/datasets/                  Six-class aisle image dataset
data/store_map/                 Store graph, AprilTag layout, and validators
docs/                           Component design and reproducible evidence
evaluation/                     Component 3 logs, metrics, and test results
firmware/                       Component-owned ESP32 motion task
frontend/navigation/            Trolley-display navigation feature
ml/                             Colab notebook, configs, models, and experiments
simulations/                    Component 3 simulations and offline dashboard
```

## Rules
Owner: comp3. Population-level POS data only (no individual customer data); recommendations need customer confirmation before becoming route stops.

## Important files

- `backend/comp3_reco_navigation/requirements.txt` — Python dependencies.
- `backend/comp3_reco_navigation/cnn/train.py` — CNN training entry point.
- `backend/comp3_reco_navigation/cnn/infer.py` — CNN inference entry point.
- `ml/colab/comp3_cnn_train.ipynb` — Google Colab launcher.
- `ml/configs/comp3_cnn.yaml` — CNN configuration.
- `ml/configs/comp3_reco.yaml` — recommendation configuration.
- `data/raw/Retail_pos_basket_data.csv` — ignored local POS dataset.
- `backend/comp3_reco_navigation/navigation/position_tracking_simulation.py` —
  deterministic synthetic encoder/IMU evaluation and report figure generator.
- `simulations/navigation_dashboard/` — local-only interactive navigation
  dashboard, map/route adapter, and adapter tests.

## Phase 4A — simulated position tracking

`python -B -m component3.backend.comp3_reco_navigation.navigation.position_tracking_simulation`
replays the Dijkstra/Held-Karp route through the existing metric store map and
writes deterministic ground truth, ideal/noisy sensor streams, checkpoint
events, aggregate metrics, a reproducibility log, and plots. Motion uses east
as +x, north as +y, and heading counter-clockwise from +x. The estimator
integrates signed wheel displacement with IMU yaw increments using the
midpoint method. At mapped graph-node arrivals, the corrected scenario uses
the existing tag-ID-to-node mapping and exact stored x/y as a simulated map
observation; it is not an OpenCV detection.

All noise, bias, speed, sampling, and turn settings are assumptions recorded
in `evaluation/position_tracking/simulation_config.json`, not physical sensor
calibrations. Scenarios B and C share the exact same noisy samples and truth.
This simulation does not establish camera, encoder, or IMU hardware accuracy.
See `docs/research_evidence/05_position_tracking/notes.md` for the evaluated
method and observed results.

## Phase 5A — route-deviation detection

`python -B -m component3.backend.comp3_reco_navigation.navigation.deviation_simulation`
evaluates a planned Held-Karp route against synthetic position estimates using
the existing graph-node coordinates. `navigation/deviation.py` projects each
estimate onto the nearest clamped route segment and reports its distance,
nearest segment, route progress, and threshold status. By default the enter
threshold follows `epsilon(d) = 0.3 + 0.02*d` metres, where `d` is progress
along the coordinate polyline; a fixed metre threshold can be supplied instead.
A lower hysteresis exit threshold and consecutive-sample confirmations filter
brief alarms and noisy recovery.

The deterministic evaluation includes eight labeled scenarios, with
ground-truth labels kept separate from the detector input. Seeded synthetic
position noise, a fixed 1.5 m off-route displacement, 0.5 s samples, three
enter confirmations, two recovery confirmations, and 0.15 m hysteresis are
simulation assumptions, not calibrated hardware values. Metrics, per-sample
observations, configuration, and reproducibility information are saved under
`evaluation/route_deviation/`; report PNG/SVG figures and test evidence are
indexed under `docs/research_evidence/05_position_tracking/`. Invalid
positions are rejected and excluded from classification counts. This phase
detects deviations only; it does not reroute the trolley or establish physical
localization performance.

The default Phase 5A simulation produced 56 observations across eight
scenarios (54 valid, two rejected), with TP=9, FP=1, TN=39, FN=5,
precision=0.900000, recall=0.642857, F1=0.750000, and a mean detected-episode
delay of two samples (1.0 s). These are controlled synthetic results; see the
position-tracking research notes for methodology and limitations.

## Phase 5B — route recalculation after confirmed deviation

`python -B -m component3.backend.comp3_reco_navigation.navigation.route_recalculation_simulation`
evaluates automatic route recalculation after the Phase 5A detector enters a
confirmed deviated state. `navigation/route_manager.py` projects the position
estimate onto the nearest valid graph edge, applies deterministic edge and
endpoint tie-breaking, and uses the selected endpoint as the starting node for
the existing Held-Karp/Dijkstra route algorithms. Recalculation is latched for
the duration of a deviation episode; it can trigger again only after the
detector reports recovery and a later entry. Shopping stops are removed only by
an explicit visit-confirmation event. Failed localization or route calculation
retains the active route and remaining list.

The seed-5052 evaluation covers 12 controlled scenarios. Its assumptions
include 0.5 s samples, 1.2 m synthetic lateral deviation with seeded +/-0.01 m
jitter, 1.5 m maximum snap distance, three entry confirmations, and two
recovery confirmations; these are not sensor calibrations. The run produced
six successful and two failed reroute attempts, zero false or missed reroute
triggers, 1.000 remaining-stop and checkout preservation rates, and one
suppressed duplicate attempt. Mean synchronous trigger-to-reroute delay was
0.000 s; mean route-distance change was -3.000 m across six successful
scenarios. These synthetic results do not imply hardware performance.

The graph is localized to an edge but routing remains node-only. Dijkstra and
Held-Karp begin at the deterministically chosen endpoint, so the partial-edge
distance from the trolley estimate to that endpoint is omitted from the route
cost. Full scenario records and reproducibility data are under
`evaluation/route_recalculation/`; the route-manager suite has 19 tests.
See `docs/research_evidence/05_position_tracking/notes.md` for metric
definitions, assumptions, and limitations.

## Phase 6A — offline navigation dashboard foundation

Launch the local dashboard from the repository root:

```bash
python3 -B -m component3.simulations.navigation_dashboard.dashboard
```

Open `http://127.0.0.1:8765/research` for the Phase 6A view of the validated
research graph. The server binds to loopback only and serves bundled assets;
it does not call cloud services or internet APIs. It uses Python's standard
library and requires no dashboard packages. Streamlit and Plotly were not
present in the existing environment, so they were not installed. See
`simulations/navigation_dashboard/README.md` for launch, test, and offline
details.

The dashboard reads the existing 24 m by 18 m store graph and AprilTag layout.
It offers the six mapped section access nodes as selectable destinations and
plans the selected visit order with the existing Held-Karp and Dijkstra
algorithms. The deterministic default is B1, B3, and B5; checkout remains the
final node. The map uses the stored metric coordinates and equal x/y scale.
Because the graph has no product-to-location mappings, this demonstration
selects mapped aisle/category access points and does not generate product IDs.
This foundation supports static route planning and reset/clear interactions
with the Phase 6B live software simulation described below.

## Phase 6B — live interactive navigation simulation

At `/research`, the Phase 6B dashboard provides deterministic graph-constrained
movement on the validated research graph. The dashboard root (`/`) now opens a
separate, versioned synthetic supermarket walkthrough. Both views reuse the
existing Component 3 Held-Karp, Dijkstra, dead-reckoning, deviation, and
route-manager implementations; those algorithms are not duplicated.

The `/research` guided panel scenario retains its B1/B3/B5 demonstration. The
root spatial dashboard has its own Phase 6C **Start Guided Demo** action for
synthetic Bananas and Frozen peas. Its seed-6042 server state machine uses the
actual spatial lane graph, existing route algorithms, dead reckoning,
checkpoint correction, deviation monitor, route manager, and pickup state. It
records two automated simulated pickup confirmations, takes exactly one valid
wrong turn after Bananas, reroutes once after detector confirmation, then
reaches Frozen peas and checkout. Movement is fixed at 0.25-second simulation
samples and stays on graph edges. Truth is used only to report simulation
error, not as estimator or detector input. AprilTag observations are simulated
and do not represent camera detection or hardware accuracy. Manual mode remains
independent and continues to require explicit pickup confirmation.

The research-graph route manager localizes to a graph edge but currently plans
from a selected endpoint. Any partial-edge distance is excluded from node-only
route cost. The simulator does not teleport to the selected anchor: it follows
graph edges to the anchor, and the UI/event log calls out the route-cost
limitation.

### Spatial navigation correction

The root dashboard uses `data/demo_store/v1/demo_store.json`, an explicitly
synthetic 20 m by 14 m layout with walkable lanes, shelf obstacles, three
mapped demonstration checkpoints, and six `SIM-P-*` demonstration products.
It is separate from `data/store_map/store_graph.json` and
`data/store_map/apriltag_layout.json`; neither validated research file is
modified. The catalog and geometry are not POS inventory or a surveyed store.
Routes are generated on the derived lane graph and stay clear of shelf
footprints. Manual product collection requires explicit confirmation at the
mapped pickup node. Guided mode instead pauses for a visible pickup notice and
records its automated confirmation as simulated before continuing.

The root view exposes current turn instructions and maneuver/checkpoint
distances, aisle and shelf targets, simulation truth and estimated position,
checkpoint correction events, product progress, route history after rerouting,
and a chronological event log. Wrong turns use connected lane edges and only
trigger the existing route manager after its confirmation samples. If the local
server stops, the page displays a launch command and automatically reconnects
and resynchronizes when it becomes available again.

Run spatial and dashboard tests with:

```bash
python3 -B -m unittest -v \
  component3.simulations.navigation_dashboard.tests.test_spatial_simulation \
  component3.simulations.navigation_dashboard.tests.test_simulation \
  component3.simulations.navigation_dashboard.tests.test_adapter
```

Evaluation output is generated with:

```bash
python3 -B -m component3.simulations.navigation_dashboard.evaluation
```

The report and telemetry CSV are written under
`evaluation/navigation_simulation/`. Run the navigation dashboard tests with:

```bash
python3 -B -m unittest -v \
  component3.simulations.navigation_dashboard.tests.test_simulation \
  component3.simulations.navigation_dashboard.tests.test_adapter
```

See `simulations/navigation_dashboard/README.md` for API, control, evaluation,
and offline-operation details.

The Phase 6C Chromium acceptance and screenshot/export workflow is:

```bash
python3 -B -m component3.simulations.navigation_dashboard.browser_acceptance
```

The documented spatial API start action is `POST /api/spatial/control` with
the JSON body `{"action":"guided_demo"}`.

## Validation

Run commands from the repository root:

```bash
python3.14 -m venv component3/.venv
component3/.venv/bin/python -m pip install --only-binary=:all: \
  -r component3/backend/comp3_reco_navigation/requirements.txt
component3/.venv/bin/python -B \
  component3/data/store_map/generate_apriltag_test_images.py
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.apriltag_offline_evaluation
python3 -B -m unittest -v \
  component3.backend.comp3_reco_navigation.tests.test_dijkstra
python3 -B -m component3.backend.comp3_reco_navigation.tests.test_held_karp \
  --output component3/evaluation/test_results/held_karp_tests.txt
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.tests.test_apriltag \
  --output component3/evaluation/test_results/apriltag_tests.txt
component3/.venv/bin/python -B -m unittest -v \
  component3.backend.comp3_reco_navigation.tests.test_dead_reckoning
component3/.venv/bin/python -B -m unittest -v \
  component3.backend.comp3_reco_navigation.tests.test_deviation
component3/.venv/bin/python -B -m unittest -v \
  component3.backend.comp3_reco_navigation.tests.test_route_manager
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.position_tracking_simulation
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.deviation_simulation
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.route_recalculation_simulation
python3 -B -m \
  component3.backend.comp3_reco_navigation.navigation.held_karp_demo
python3 -B component3/data/store_map/validate_store_map.py
python3 -B component3/docs/research_evidence/tools/validate_evidence.py
```

The project-local `.venv/` is ignored by Git. Phase 3A was verified with
CPython 3.14.0, `opencv-contrib-python` 5.0.0.93 (OpenCV 5.0.0), and NumPy
2.5.4 on arm64 macOS. AprilTag fixtures and metrics are synthetic offline
evaluation artifacts, not physical-camera accuracy measurements.

Research evidence is stored under `docs/research_evidence/`, with executable
results under `evaluation/`. Shared product and location seeds remain under the
repository-root `shared/db/seed/` directory.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: J26-IT-340 Component 3 workspace in `component3/`. Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Keep Component 3-owned implementation inside this folder. Inter-component messages must follow root-level `shared/contracts/events.schema.json`. Use type hints, docstrings and unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 3: preprocess the POS CSV, build TF-IDF + KNN signals, fuse them, apply the relevance-vs-detour-cost filter, compute exact routes with Dijkstra + Held-Karp, and correct position at AprilTag checkpoints using encoder + IMU dead reckoning. Expose FastAPI routes under /c3.
```
