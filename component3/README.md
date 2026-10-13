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
simulations/                    Component 3 HTML simulations
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
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.position_tracking_simulation
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.deviation_simulation
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
