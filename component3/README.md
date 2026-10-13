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

## Validation

Run commands from the repository root:

```bash
python3 -B -m unittest -v \
  component3.backend.comp3_reco_navigation.tests.test_dijkstra
python3 -B component3/data/store_map/validate_store_map.py
python3 -B component3/docs/research_evidence/tools/validate_evidence.py
```

Research evidence is stored under `docs/research_evidence/`, with executable
results under `evaluation/`. Shared product and location seeds remain under the
repository-root `shared/db/seed/` directory.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: J26-IT-340 Component 3 workspace in `component3/`. Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Keep Component 3-owned implementation inside this folder. Inter-component messages must follow root-level `shared/contracts/events.schema.json`. Use type hints, docstrings and unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 3: preprocess the POS CSV, build TF-IDF + KNN signals, fuse them, apply the relevance-vs-detour-cost filter, compute exact routes with Dijkstra + Held-Karp, and correct position at AprilTag checkpoints using encoder + IMU dead reckoning. Expose FastAPI routes under /c3.
```
