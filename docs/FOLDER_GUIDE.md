# Folder guide

> Index of every responsibility folder. Each folder has a README with rules and a Copilot prompt.

| Folder | Owner | Responsibility |
|---|---|---|
| `.` | develop (shared - all four members review) | Project root: entry README, build/dev tooling, containers, git hygiene. |
| `.github` | develop (shared - all four members review) | Repository governance: ownership, templates, CI, Copilot rules. |
| `.github/workflows` | develop (shared - all four members review) | GitHub Actions pipelines that enforce the promotion gates. |
| `backend` | develop (shared - all four members review) | All server-side Python code: gateway plus one package per component. |
| `backend/comp1_trigger_validation` | comp1 | Component 1 - detects that something was put in/taken out of the trolley and validates that it is a real shopping item. |
| `backend/comp1_trigger_validation/api` | comp1 | HTTP layer of Component 1. |
| `backend/comp1_trigger_validation/ml` | comp1 | Training and inference code for the item-validation classifier. |
| `backend/comp1_trigger_validation/services` | comp1 | Business logic of Component 1. |
| `backend/comp1_trigger_validation/tests` | comp1 | Unit tests for Component 1. |
| `backend/comp2_recognition_tracking` | comp2 | Component 2 - recognises which product entered/left the trolley and keeps the live cart. |
| `backend/comp2_recognition_tracking/api` | comp2 | HTTP layer of Component 2. |
| `backend/comp2_recognition_tracking/ml` | comp2 | YOLO dataset preparation, training, export, evaluation. |
| `backend/comp2_recognition_tracking/services` | comp2 | Vision pipeline and cart logic. |
| `backend/comp2_recognition_tracking/tests` | comp2 | Unit tests for Component 2. |
| `backend/comp3_reco_navigation` | comp3 | Component 3 - recommends extra items worth a detour and routes the trolley through the to-buy list. |
| `backend/comp3_reco_navigation/api` | comp3 | HTTP layer of Component 3. |
| `backend/comp3_reco_navigation/cnn` | comp3 | Ambient aisle/section classifier used between AprilTag checkpoints (not for checkpoint detection). |
| `backend/comp3_reco_navigation/navigation` | comp3 | Routing and localisation. |
| `backend/comp3_reco_navigation/recommendation` | comp3 | Recommendation engine: three-signal fusion plus detour filter. |
| `backend/comp3_reco_navigation/session` | comp3 | Session-only state for the shopper. |
| `backend/comp3_reco_navigation/tests` | comp3 | Unit tests for Component 3. |
| `backend/comp4_pattern_billing` | comp4 | Component 4 - purchase history, monthly pattern prediction, billing, mobile sync. |
| `backend/comp4_pattern_billing/api` | comp4 | HTTP layer of Component 4. |
| `backend/comp4_pattern_billing/ml` | comp4 | Monthly purchase-pattern model. |
| `backend/comp4_pattern_billing/services` | comp4 | Business logic of Component 4. |
| `backend/comp4_pattern_billing/tests` | comp4 | Unit tests for Component 4. |
| `backend/gateway` | develop (shared - all four members review) | Single FastAPI entrypoint that mounts every component under a prefix. |
| `config` | develop (shared - all four members review) | Per-environment configuration templates (DEV / TEST / PROD). |
| `data` | develop (shared - all four members review) | Datasets and map data. |
| `data/datasets` | develop (shared - all four members review) | Image datasets for training (comp1_objects, comp2_grocery_yolo, comp3_aisle_images). |
| `data/processed` | develop (shared - all four members review) | Derived datasets created by code. |
| `data/raw` | develop (shared - all four members review) | Immutable original datasets. |
| `data/store_map` | comp3 | The mock-store map used by navigation and the UI. |
| `docs` | develop (shared - all four members review) | All human-readable documentation. |
| `docs/api` | develop (shared - all four members review) | Generated API reference per service. |
| `docs/architecture` | develop (shared - all four members review) | System-level design: how the four components fit together. |
| `docs/components` | develop (shared - all four members review) | One design document per component (goals, algorithms, inputs/outputs, evaluation). |
| `docs/research` | develop (shared - all four members review) | Research artefacts: proposal, paper drafts, panel slides. |
| `docs/testing` | develop (shared - all four members review) | Test strategy and recorded results, including UAT. |
| `evaluation` | develop (shared - all four members review) | Scripts and results that produce the numbers in the paper. |
| `firmware` | develop (shared - all four members review) | Code that runs on microcontrollers. |
| `firmware/trolley_esp32` | develop (shared - all four members review) | The one ESP32 firmware image: load-cell events (Component 1) and motion sensing (Component 3). |
| `firmware/trolley_esp32/include` | develop (shared - all four members review) | Headers shared by all firmware sources. |
| `firmware/trolley_esp32/src` | develop (shared - all four members review) | Firmware sources. |
| `firmware/trolley_esp32/src/comms` | develop (shared - all four members review) | Communication with the host. |
| `firmware/trolley_esp32/src/tasks` | comp1 (loadcell_task) + comp3 (motion_task) | One FreeRTOS task per sensing responsibility. |
| `frontend` | develop (shared - all four members review) | All user interfaces. |
| `frontend/mobile-app` | comp4 | Customer phone app (framework to be decided: React Native or Flutter). |
| `frontend/mobile-app/src/features` | comp4 | Mobile feature modules (lists, recipes, billing, notifications). |
| `frontend/trolley-display` | develop (shared - all four members review) | React + Vite app shown on the trolley screen. One shared app, one feature folder per component. |
| `frontend/trolley-display/src` | develop (shared - all four members review) | Application source. |
| `frontend/trolley-display/src/features/billing` | comp4 | Component 4 UI. |
| `frontend/trolley-display/src/features/cart` | comp2 | Component 2 UI. |
| `frontend/trolley-display/src/features/navigation` | comp3 | Component 3 UI: map, route, to-buy list, suggestions. |
| `frontend/trolley-display/src/features/validation` | comp1 | Component 1 UI. |
| `ml` | develop (shared - all four members review) | Machine-learning workspace for training outside the backend runtime (Google Colab). |
| `ml/colab` | develop (shared - all four members review) | Thin Colab launcher notebooks. |
| `ml/configs` | develop (shared - all four members review) | Versioned hyperparameters per model. |
| `ml/models` | develop (shared - all four members review) | Trained artefacts (weights, vectorisers). |
| `ml/notebooks` | develop (shared - all four members review) | Exploratory notebooks (EDA, experiments). |
| `scripts` | develop (shared - all four members review) | Developer and demo helper scripts. |
| `shared` | develop (shared - all four members review) | Code and definitions used by more than one component. |
| `shared/common` | develop (shared - all four members review) | Reusable Python helpers imported by every backend service. |
| `shared/contracts` | develop (shared - all four members review) | The integration contract between components. |
| `shared/db` | develop (shared - all four members review) | Database definition shared by all services. |
| `simulations` | comp3 | Standalone HTML simulations for the panel presentation. |
| `tests` | develop (shared - all four members review) | Cross-component tests (authored on develop, executed on test). |
| `tests/contract` | develop (shared - all four members review) | Verifies that payloads match shared/contracts. |
| `tests/e2e` | develop (shared - all four members review) | Full-session and performance tests. |
| `tests/hardware` | develop (shared - all four members review) | Hardware-in-the-loop tests. |
| `tests/integration` | develop (shared - all four members review) | Tests of two or more services running together. |
