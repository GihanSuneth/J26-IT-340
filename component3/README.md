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
data/derived/                   Audited Phase 8A basket and split artifacts
data/datasets/                  Six-class aisle image dataset
data/store_map/                 Store graph, AprilTag layout, and validators
docs/                           Component design and reproducible evidence
evaluation/                     Component 3 logs, metrics, and test results
firmware/                       Component-owned ESP32 motion task
frontend/navigation/            Component 3 trolley-display navigation feature
ml/                             Colab notebook, configs, models, and experiments
simulations/                    Component 3 simulations and offline dashboard
```

## Rules
Owner: comp3. Population-level POS data only (no individual customer data); recommendations need customer confirmation before becoming route stops.

## Important files

- `backend/comp3_reco_navigation/requirements.txt` — Python dependencies.
- `frontend/navigation/comp3_map_view.jsx` — store map and trolley position view.
- `frontend/navigation/comp3_route_overlay.jsx` — route overlay and next-stop highlight.
- `frontend/navigation/comp3_to_buy_list.jsx` — session to-buy list view.
- `frontend/navigation/comp3_suggestion_card.jsx` — recommendation card requiring customer confirmation.
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
- `data/apriltag_cards/` — locally generated and detector-verified demo
  checkpoint cards for Mac-camera evaluation.
- `backend/comp3_reco_navigation/navigation/route_anchor.py` — exact node/mid-edge
  route-start composition over the existing Dijkstra and Held–Karp algorithms.

## Phase 7D — adaptive free-walk navigation

The shared simulator now supports graph-edge free walk, stop/resume, junction choices,
navigation requests from a node or mid-edge position, and plausible unexpected mapped
checkpoint correction. The customer and research views expose the same authoritative
state. See `evaluation/research_archive/01_navigation_engine/phase_7d_free_walk_adaptive_localization.md`
for algorithm formulation, measured synthetic results and claim boundaries.

## Phase 7E — dynamic shopping sessions

`simulations/navigation_dashboard/shopping_session.py` owns requested, collected and
remaining quantities, source, shopping revision and audit events. Live customer edits
are validated and route-checked before one atomic commit, then reuse the exact
node/mid-edge Dijkstra/Held–Karp path. The recommendation surface is a demonstration
contract only; no model was trained and no score is fabricated. See the Phase 7E
research-archive report for comparative results and limitations.

## Phase 7F — navigation research evaluation

`simulations/navigation_dashboard/phase7f_evaluation.py` runs the fixed-seed paired
baseline, labeled localization, brute-force oracle, complete-journey and scaling
experiments. It writes a manifest, raw and aggregate JSON, and baseline/localization/
performance CSV tables under `evaluation/research_archive/01_navigation_engine/`.
The Phase 7F summary reports synthetic/software navigation acceptance as PASS and
physical camera acceptance as PENDING. No navigation engine, validated map, raw POS
data, CNN image or recommendation model was changed by this evaluation phase.

## Phase 8A — recommendation data preparation

The single local POS-shaped CSV has unknown provenance and license and must not be
described as verified real transactions. The deterministic preparation pipeline audits
10,000 rows, reconstructs 1,991 baskets using normalized product names because source
product IDs are unstable, freezes a leakage-safe chronological split, and creates an
auditable demo-catalog crosswalk. Four baseline implementations and metric functions
are ready for Phase 8B; no final model was trained and no quality metric was reported.
See `evaluation/research_archive/02_recommendation_engine/`.

## Phase 8B — offline recommendation evaluation

Four fitted statistical baselines and a regularized NumPy linear ranker use only the
frozen training split. Association rules were selected by validation NDCG@5 and then
evaluated on the held-out test split. Test NDCG@5 was 0.0232 and HitRate@5 0.0468;
these weak unknown-provenance results are research evidence, not deployment validation.
Reloadable JSON artifacts are under `ml/models/comp3/recommendation_phase8b/`. No model
prediction was integrated into the customer dashboard.

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

## Phase 7B.1 — Mac-camera-assisted checkpoint evaluation

The optional camera mode keeps trolley motion and products simulated while
OpenCV reads genuine `tag36h11` observations from a Mac camera. It is isolated
from manual and guided modes, never uploads frames, pauses at checkpoint gates,
and passes stable detections through the existing ordering, duplication,
map-version, confidence, and correction-distance validator. See
`docs/evaluation/phase7b1_mac_camera_implementation.md` for setup and the exact
local acceptance procedure. Real-camera acceptance remains separate from
mocked-frame and generated-card tests.

The headless smoke test supports `--no-preview`; the separate `--probe-cameras`
diagnostic checks indices 0, 1, and 2 without GUI windows. The dashboard shares
the same camera scanner for detection but does not yet display live video.

The Phase 6C Chromium acceptance and screenshot/export workflow is:

```bash
python3 -B -m component3.simulations.navigation_dashboard.browser_acceptance
```

The documented spatial API start action is `POST /api/spatial/control` with
the JSON body `{"action":"guided_demo"}`.

## Phase 7A — automatic turn-by-turn customer guidance

The synthetic spatial dashboard now generates typed guidance from active route
geometry rather than scripted display text. Instructions cover start,
straight, left, right, U-turn, checkpoint approach/confirmation, product
approach/arrival, pickup, rerouting, uncertainty, checkout, and completion.
Every event has a deterministic ID, route revision, timestamp, target, and
distance; repeated polling refreshes distance without duplicating the event.

All six synthetic products now have validated product ID, display name,
section, shelf, level, bay, walkable pickup node, and shelf-facing coordinates.
Left/right shelf guidance is calculated from the signed approach geometry. A
product is reached only after two consecutive dead-reckoned estimates within
1.0 m and localization uncertainty no greater than 0.75 m. Ground truth is
retained for evaluation only and is not used to accept arrival.

Checkpoint correction is observation-driven. The control API accepts
`{"action":"observe_checkpoint","observation":{...}}`; the observation must
identify the expected mapped tag, map version, timestamp, source, and optional
confidence. Unknown, duplicate, out-of-order, wrong-map, unexpected, and
low-confidence observations are rejected without changing localization.
Simulator-created tag observations are explicitly labeled
`synthetic_spatial_simulator`; this phase does not implement live camera input.

The dashboard prominently displays direction, destination, section/level/side,
distance, heading, progress, localization state, observed versus confirmed
checkpoint state, and non-obstructive event notifications. Optional browser
speech is off by default and only speaks new structured event IDs. Manual mode
still requires pickup confirmation; guided mode uses the same route manager,
arrival monitor, checkpoint processor, deviation monitor, and pickup path.

Generate the synthetic evaluation and run real-browser acceptance with:

```bash
python3 -B -m component3.simulations.navigation_dashboard.phase7a_evaluation
python3 -B -m component3.simulations.navigation_dashboard.phase7a_browser_acceptance
```

The current evaluation reports 4/4 turn classifications, 2/2 turn-notification
timing decisions, 4/4 shelf-side
classifications, 6/6 valid product mappings, 6/6 checkpoint decisions, and
4/4 labeled arrival decisions with zero false arrivals. Three guided runs were
identical and completed with two products, CP200→CP201→CP202, and one reroute.
These are controlled synthetic software results, not physical navigation,
camera, shopper, or store-performance measurements.

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

Phase 7C architecture, roadmap, reproducibility handoff, and the non-destructive
research archive are maintained in `docs/COMP3_ARCHITECTURE.md`,
`docs/COMP3_RESEARCH_ROADMAP.md`, `docs/COMP3_CODEX_HANDOFF.md`, and
`evaluation/research_archive/`. The adaptive free-walk and dynamic-list design is
documented there.

Phase 8C connects the unchanged frozen association model to both dashboards. Suggestions
are experimental, restricted to verified mappings and accepted only through the atomic
shopping mutation/current-position replanning path. Launch with:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard
```

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: J26-IT-340 Component 3 workspace in `component3/`. Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Keep Component 3-owned implementation inside this folder. Inter-component messages must follow root-level `shared/contracts/events.schema.json`. Use type hints, docstrings and unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 3: preprocess the POS CSV, build TF-IDF + KNN signals, fuse them, apply the relevance-vs-detour-cost filter, compute exact routes with Dijkstra + Held-Karp, and correct position at AprilTag checkpoints using encoder + IMU dead reckoning. Expose FastAPI routes under /c3.
```
