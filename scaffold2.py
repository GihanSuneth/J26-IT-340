#!/usr/bin/env python3
"""
scaffold.py - J26-IT-340 smart-trolley monorepo generator.

Run ONCE on the `develop` branch from the repo root:
    git checkout develop
    python scaffold.py            # creates missing files only
    python scaffold.py --force    # overwrites generated files (careful)
    git add -A && git commit -m "chore: repo skeleton"
Then merge develop into test, comp1..comp4 (see docs/BRANCHING.md).

What it creates
  * every directory (+ .gitkeep when empty)
  * every file, starting with a header comment saying what the file is for
  * a README.md in each responsibility folder: purpose, what code belongs there,
    rules, and a ready-to-paste GitHub Copilot prompt
  * docs/FOLDER_GUIDE.md (index of all folders)
  * .github/copilot-instructions.md (repo-wide Copilot rules)
"""
import json
import os
import re
import sys
from pathlib import Path

FORCE = "--force" in sys.argv
ROOT = Path(".")

# --------------------------------------------------------------------------- #
# Ownership (mirrors CODEOWNERS / docs/BRANCHING.md)
# --------------------------------------------------------------------------- #
SHARED = "develop (shared - all four members review)"
OWN = {
    "frontend/trolley-display/src/features/validation": "comp1",
    "frontend/trolley-display/src/features/cart": "comp2",
    "frontend/trolley-display/src/features/navigation": "comp3",
    "frontend/trolley-display/src/features/billing": "comp4",
    "frontend/mobile-app": "comp4",
    "firmware/trolley_esp32/src/tasks/loadcell_task.cpp": "comp1",
    "firmware/trolley_esp32/src/tasks/motion_task.cpp": "comp3",
    "firmware/trolley_esp32/src/tasks": "comp1 (loadcell_task) + comp3 (motion_task)",
    "data/store_map": "comp3",
    "simulations": "comp3",
}


def owner_of(p):
    m = re.search(r"comp([1-4])", p)
    if m:
        return f"comp{m.group(1)}"
    for k, v in OWN.items():
        if p.startswith(k):
            return v
    return SHARED


# --------------------------------------------------------------------------- #
# FILE DESCRIPTIONS  (path -> one-line purpose, written into the file header)
# --------------------------------------------------------------------------- #
F = {
    # root
    "LICENSE": "Project licence. Choose one (or 'all rights reserved') per SLIIT policy.",
    "Makefile": "Developer shortcuts: make setup | lint | test | up | down.",
    ".gitignore": "Files git must never track: secrets, datasets, model weights, caches.",
    ".pre-commit-config.yaml": "Pre-commit hooks: ruff, black, nbstripout (strip notebook output), eslint, detect-secrets.",
    ".env.example": "Template of every environment variable the system reads. Copy to .env; never commit .env.",
    "docker-compose.yml": "DEV stack: Postgres + gateway + comp1..comp4 services + trolley-display frontend.",
    "docker-compose.test.yml": "TEST/UAT overrides: real service URLs, test database, hardware-attached flags.",
    # .github
    ".github/CODEOWNERS": "Maps each path to its owning member; enforces the ownership table in docs/BRANCHING.md.",
    ".github/pull_request_template.md": "PR checklist: owned paths only, unit + contract tests pass, linked issue, screenshots/logs.",
    ".github/copilot-instructions.md": "Repo-wide rules GitHub Copilot follows in every suggestion.",
    ".github/ISSUE_TEMPLATE/task.md": "Issue template for planned work (goal, component, acceptance criteria).",
    ".github/ISSUE_TEMPLATE/bug.md": "Issue template for defects (steps, expected/actual, branch, logs).",
    ".github/workflows/ci-develop.yml": "CI on PR to develop: lint, per-component unit tests, contract tests, frontend build.",
    ".github/workflows/ci-test.yml": "CI on PR to test: docker-compose.test.yml up, run tests/integration and tests/e2e.",
    ".github/workflows/release-main.yml": "On merge to main: tag the release, attach build artifacts, publish CHANGELOG entry.",
    # config
    "config/dev.env.example": "DEV environment values: localhost URLs, simulated sensors, debug logging.",
    "config/test.env.example": "TEST/UAT values: trolley-laptop URLs, real ESP32 serial port, test DB.",
    "config/prod.env.example": "PROD/panel-demo values: frozen config, debug off, demo store map.",
    # docs
    "docs/BRANCHING.md": "Branch model (comp -> develop -> test -> main), gates, ownership table, hotfix rule.",
    "docs/CONTRIBUTING.md": "Commit convention, PR rules, code style, how to run tests locally.",
    "docs/COLAB_GUIDE.md": "How to train on Google Colab: Drive layout, run IDs, checkpointing, exporting weights.",
    "docs/architecture/system-overview.md": "End-to-end architecture: four components, data flow, event sequence, hardware.",
    "docs/architecture/deployment.md": "How DEV, TEST and PROD environments are run and what hardware each needs.",
    "docs/components/comp1-trigger-validation.md": "Component 1 design: weight trigger, item validation, outputs and accuracy targets.",
    "docs/components/comp2-recognition-tracking.md": "Component 2 design: camera capture, chroma-key, YOLO recognition, cart state.",
    "docs/components/comp3-reco-navigation.md": "Component 3 design: three-signal fusion, detour filter, Held-Karp routing, AprilTag/dead-reckoning.",
    "docs/components/comp4-pattern-billing.md": "Component 4 design: purchase history, monthly prediction, billing, mobile sync.",
    "docs/testing/test-plan.md": "What is tested at each level (unit, contract, integration, E2E, UAT) and pass criteria.",
    "docs/testing/integration-test-report.md": "Results of integration runs on the test branch (date, commit, pass/fail, defects).",
    "docs/testing/uat/uat-plan.md": "UAT scenarios: scripted shopping sessions on the mock store, participants, success measures.",
    "docs/testing/uat/uat-results.md": "Recorded UAT outcomes and feedback; the evidence required before test -> main.",
    "docs/releases/CHANGELOG.md": "Release history of main (version, date, what changed).",
    # shared
    "shared/contracts/events.schema.json": "JSON Schema of every event exchanged between components (the integration contract).",
    "shared/contracts/openapi.yaml": "Combined OpenAPI description of the gateway and component REST endpoints.",
    "shared/contracts/esp32_serial_protocol.md": "Wire protocol between ESP32 and backend: frame format, message types, rates, baud 115200.",
    "shared/db/schema.sql": "Authoritative relational schema (products, carts, cart_items, bills, history, sessions).",
    "shared/db/seed/products.csv": "Seed products. Columns: product_id,product_name,category,price,aisle_id",
    "shared/db/seed/store_locations.csv": "Seed shelf positions. Columns: product_id,aisle_id,shelf,x_m,y_m",
    "shared/common/__init__.py": "Package marker for shared helpers.",
    "shared/common/config.py": "Loads environment configuration into a typed settings object used by all services.",
    "shared/common/logging.py": "Single structured-logging setup so every service logs in the same format.",
    "shared/common/event_bus.py": "Publish/subscribe wrapper for inter-component events (in-process queue or HTTP/WebSocket).",
    "shared/common/http_client.py": "Shared HTTP client with timeouts/retries for service-to-service calls.",
    "shared/common/auth.py": "Session/token helpers shared by the gateway and the mobile sync API.",
    # gateway
    "backend/gateway/main.py": "FastAPI entrypoint: creates the app, mounts routers, CORS, health check, startup wiring.",
    "backend/gateway/routers.py": "Includes each component's router under /c1, /c2, /c3, /c4 prefixes.",
    "backend/gateway/config.py": "Gateway-specific settings (ports, allowed origins, service URLs).",
    "backend/gateway/requirements.txt": "Python dependencies of the gateway (fastapi, uvicorn, pydantic, httpx).",
    "backend/gateway/Dockerfile": "Container image for the gateway service.",
    # comp1
    "backend/comp1_trigger_validation/requirements.txt": "Python dependencies for Component 1 (fastapi, pyserial, opencv-python, scikit-learn/torch).",
    "backend/comp1_trigger_validation/Dockerfile": "Container image for Component 1.",
    "backend/comp1_trigger_validation/api/__init__.py": "Package marker.",
    "backend/comp1_trigger_validation/api/router.py": "FastAPI routes for Component 1 (weight-event ingest, validate, health).",
    "backend/comp1_trigger_validation/api/schemas.py": "Pydantic request/response models for Component 1 endpoints.",
    "backend/comp1_trigger_validation/services/__init__.py": "Package marker.",
    "backend/comp1_trigger_validation/services/serial_bridge.py": "Reads ESP32 serial frames and turns load-cell frames into weight samples.",
    "backend/comp1_trigger_validation/services/weight_event_service.py": "Debounce, baseline and delta-threshold logic: decides when a weight change is an add/remove event.",
    "backend/comp1_trigger_validation/services/camera_capture.py": "Grabs a still/short clip from camera 1 when a weight event fires.",
    "backend/comp1_trigger_validation/services/validation_pipeline.py": "Combines weight evidence and vision classifier into a valid/invalid item decision.",
    "backend/comp1_trigger_validation/services/trigger_publisher.py": "Publishes the valid_item_event that triggers Component 2.",
    "backend/comp1_trigger_validation/ml/__init__.py": "Package marker.",
    "backend/comp1_trigger_validation/ml/dataset.py": "Loads/labels the valid-vs-non-shopping-object dataset.",
    "backend/comp1_trigger_validation/ml/features.py": "Feature extraction (image and weight features) for the validation classifier.",
    "backend/comp1_trigger_validation/ml/train.py": "Training entrypoint. Reads ml/configs/comp1_validation.yaml; writes ml/models/comp1/<run_id>/. Run from Colab.",
    "backend/comp1_trigger_validation/ml/infer.py": "Loads the trained model and returns a validity prediction for one capture.",
    "backend/comp1_trigger_validation/ml/evaluate.py": "Computes accuracy/precision/recall/confusion matrix; writes to evaluation/comp1/.",
    "backend/comp1_trigger_validation/tests/test_weight_events.py": "Unit tests for debounce/threshold logic with synthetic weight traces.",
    "backend/comp1_trigger_validation/tests/test_validation_pipeline.py": "Unit tests for the validation decision logic with mocked classifier output.",
    # comp2
    "backend/comp2_recognition_tracking/requirements.txt": "Python dependencies for Component 2 (fastapi, opencv-python, ultralytics, onnxruntime, numpy).",
    "backend/comp2_recognition_tracking/Dockerfile": "Container image for Component 2.",
    "backend/comp2_recognition_tracking/api/__init__.py": "Package marker.",
    "backend/comp2_recognition_tracking/api/router.py": "FastAPI routes: recognize, get cart, confirm/remove item, health.",
    "backend/comp2_recognition_tracking/api/schemas.py": "Pydantic models for recognition results and cart state.",
    "backend/comp2_recognition_tracking/services/__init__.py": "Package marker.",
    "backend/comp2_recognition_tracking/services/event_listener.py": "Subscribes to Component 1's valid_item_event and starts a recognition run.",
    "backend/comp2_recognition_tracking/services/camera2_capture.py": "Captures frames from the cart-interior camera 2.",
    "backend/comp2_recognition_tracking/services/chroma_key.py": "Isolates the item from the green-screen background before recognition.",
    "backend/comp2_recognition_tracking/services/frame_diff.py": "Frame differencing to decide whether an item was added or removed.",
    "backend/comp2_recognition_tracking/services/recognizer.py": "Wraps the YOLO model: image in, product label + confidence out.",
    "backend/comp2_recognition_tracking/services/cart_service.py": "Maintains cart state (items, quantities) and emits cart_updated events.",
    "backend/comp2_recognition_tracking/ml/__init__.py": "Package marker.",
    "backend/comp2_recognition_tracking/ml/dataset_prep.py": "Builds the YOLO dataset (labels, splits, augmentation) from raw grocery images.",
    "backend/comp2_recognition_tracking/ml/train.py": "YOLO training entrypoint. Reads ml/configs/comp2_yolo.yaml; run from Colab.",
    "backend/comp2_recognition_tracking/ml/infer.py": "Runs inference with the exported model on one frame.",
    "backend/comp2_recognition_tracking/ml/export_onnx.py": "Exports trained weights to ONNX/pt for the trolley laptop (pins versions).",
    "backend/comp2_recognition_tracking/ml/evaluate.py": "mAP/precision/recall evaluation; writes to evaluation/comp2/.",
    "backend/comp2_recognition_tracking/tests/test_frame_diff.py": "Unit tests for add/remove detection using synthetic frames.",
    "backend/comp2_recognition_tracking/tests/test_cart_service.py": "Unit tests for cart add/remove/quantity logic.",
    # comp3
    "backend/comp3_reco_navigation/requirements.txt": "Python dependencies for Component 3 (fastapi, scikit-learn, pandas, numpy, networkx/scipy, opencv-contrib-python, pyserial).",
    "backend/comp3_reco_navigation/Dockerfile": "Container image for Component 3.",
    "backend/comp3_reco_navigation/api/__init__.py": "Package marker.",
    "backend/comp3_reco_navigation/api/recommend.py": "POST /recommend: basket + current position -> filtered recommendations.",
    "backend/comp3_reco_navigation/api/route.py": "POST /route and /route/recompute: to-buy list -> ordered stops and path.",
    "backend/comp3_reco_navigation/api/checkpoint.py": "POST /checkpoint: AprilTag hit and dead-reckoning updates from the trolley.",
    "backend/comp3_reco_navigation/api/session.py": "Session-only to-buy list endpoints (add, remove, confirm suggestion, reset).",
    "backend/comp3_reco_navigation/api/schemas.py": "Pydantic models for all Component 3 requests/responses.",
    "backend/comp3_reco_navigation/recommendation/__init__.py": "Package marker.",
    "backend/comp3_reco_navigation/recommendation/preprocess.py": "Cleans the POS CSV: drops user_id, fixes product keys, filters non-grocery categories, builds baskets.",
    "backend/comp3_reco_navigation/recommendation/tfidf_category.py": "sklearn TF-IDF + cosine similarity over category/product text (signal 1).",
    "backend/comp3_reco_navigation/recommendation/knn_cooccurrence.py": "KNN over basket co-occurrence vectors (signal 2).",
    "backend/comp3_reco_navigation/recommendation/fusion.py": "Fuses the three signals into one ranked candidate list.",
    "backend/comp3_reco_navigation/recommendation/detour_filter.py": "Relevance-vs-detour-cost filter: the novelty. Keeps a candidate only if its relevance justifies the extra route length.",
    "backend/comp3_reco_navigation/navigation/__init__.py": "Package marker.",
    "backend/comp3_reco_navigation/navigation/store_graph.py": "Loads data/store_map/store_graph.json into a graph (aisles, dual corridors, cross-aisles).",
    "backend/comp3_reco_navigation/navigation/dijkstra.py": "Pairwise shortest-path distances between product stops.",
    "backend/comp3_reco_navigation/navigation/held_karp.py": "Exact multi-stop TSP via Held-Karp DP over the Dijkstra distance matrix.",
    "backend/comp3_reco_navigation/navigation/route_manager.py": "Owns the active route; recomputes only on deviation or to-buy-list change.",
    "backend/comp3_reco_navigation/navigation/apriltag.py": "AprilTag detection with cv2.aruco; maps tag IDs to checkpoint nodes.",
    "backend/comp3_reco_navigation/navigation/dead_reckoning.py": "Wheel-encoder + IMU position estimate between checkpoints.",
    "backend/comp3_reco_navigation/navigation/deviation.py": "Adaptive deviation test: epsilon(d) = eps_base + sigma*d (eps_base=0.3 m, sigma=0.02).",
    "backend/comp3_reco_navigation/cnn/__init__.py": "Package marker.",
    "backend/comp3_reco_navigation/cnn/train.py": "Trains the ambient aisle/section classifier. Reads ml/configs/comp3_cnn.yaml; run from Colab.",
    "backend/comp3_reco_navigation/cnn/infer.py": "Runs the aisle classifier on a frame between checkpoints.",
    "backend/comp3_reco_navigation/session/__init__.py": "Package marker.",
    "backend/comp3_reco_navigation/session/tobuy_list.py": "In-memory, session-only to-buy list (nothing persisted after reset).",
    "backend/comp3_reco_navigation/tests/test_held_karp.py": "Held-Karp optimality tests against brute force on small instances.",
    "backend/comp3_reco_navigation/tests/test_dijkstra.py": "Shortest-path tests on the mock store graph.",
    "backend/comp3_reco_navigation/tests/test_fusion.py": "Tests for score fusion ordering and weights.",
    "backend/comp3_reco_navigation/tests/test_detour_filter.py": "Tests that costly low-relevance detours are rejected and cheap relevant ones accepted.",
    "backend/comp3_reco_navigation/tests/test_dead_reckoning.py": "Tests for position drift and the adaptive epsilon(d) deviation threshold.",
    # comp4
    "backend/comp4_pattern_billing/requirements.txt": "Python dependencies for Component 4 (fastapi, sqlalchemy, psycopg, pandas, scikit-learn).",
    "backend/comp4_pattern_billing/Dockerfile": "Container image for Component 4.",
    "backend/comp4_pattern_billing/api/__init__.py": "Package marker.",
    "backend/comp4_pattern_billing/api/router_reco.py": "Routes for history-based (individual) recommendations and monthly lists.",
    "backend/comp4_pattern_billing/api/router_billing.py": "Routes for checkout, bill generation and payment status.",
    "backend/comp4_pattern_billing/api/router_sync.py": "Routes syncing lists, recipes and bills with the mobile app.",
    "backend/comp4_pattern_billing/api/schemas.py": "Pydantic models for Component 4 endpoints.",
    "backend/comp4_pattern_billing/services/__init__.py": "Package marker.",
    "backend/comp4_pattern_billing/services/history_service.py": "Stores and queries per-customer purchase history.",
    "backend/comp4_pattern_billing/services/billing_service.py": "Totals the confirmed cart, applies prices/discounts, creates the bill.",
    "backend/comp4_pattern_billing/services/shopping_list_service.py": "Builds and edits the monthly shopping list.",
    "backend/comp4_pattern_billing/services/recipe_service.py": "Recipe-to-ingredient mapping used to extend shopping lists.",
    "backend/comp4_pattern_billing/services/notification_service.py": "Sends reminders/alerts to the mobile app.",
    "backend/comp4_pattern_billing/services/sync_service.py": "Two-way sync of lists and bills between backend and mobile app.",
    "backend/comp4_pattern_billing/ml/__init__.py": "Package marker.",
    "backend/comp4_pattern_billing/ml/features.py": "Builds per-customer purchase-pattern features.",
    "backend/comp4_pattern_billing/ml/train.py": "Trains the monthly-purchase predictor. Reads ml/configs/comp4_monthly.yaml.",
    "backend/comp4_pattern_billing/ml/predict_monthly.py": "Predicts next month's likely purchases for a customer.",
    "backend/comp4_pattern_billing/ml/evaluate.py": "Evaluates predictions; writes to evaluation/comp4/.",
    "backend/comp4_pattern_billing/tests/test_billing.py": "Unit tests for totals, rounding and bill creation.",
    "backend/comp4_pattern_billing/tests/test_monthly_prediction.py": "Unit tests for the monthly prediction interface and output shape.",
    # frontend
    "frontend/trolley-display/package.json": "Frontend dependencies and scripts (React + Vite).",
    "frontend/trolley-display/src/main.jsx": "React entrypoint: mounts <App/>.",
    "frontend/trolley-display/src/app/App.jsx": "Top-level layout of the trolley screen; hosts the four feature panels.",
    "frontend/trolley-display/src/app/routes.jsx": "Screen routing (shopping, checkout, idle).",
    "frontend/trolley-display/src/api/client.js": "Single fetch/WebSocket client to the gateway; all components call the backend through it.",
    "frontend/trolley-display/src/features/validation/ValidationPanel.jsx": "Shows item-validation status (accepted/rejected) from Component 1.",
    "frontend/trolley-display/src/features/cart/CartPanel.jsx": "Live cart list with add/remove confirmation from Component 2.",
    "frontend/trolley-display/src/features/navigation/MapView.jsx": "Draws the store map and the trolley's current position.",
    "frontend/trolley-display/src/features/navigation/RouteOverlay.jsx": "Draws the Held-Karp route and highlights the next stop.",
    "frontend/trolley-display/src/features/navigation/ToBuyList.jsx": "Session to-buy list with check-off and add/remove.",
    "frontend/trolley-display/src/features/navigation/SuggestionCard.jsx": "Shows a recommendation with detour cost; customer must confirm before it joins the route.",
    "frontend/trolley-display/src/features/billing/BillingPanel.jsx": "Checkout summary and bill from Component 4.",
    # firmware
    "firmware/trolley_esp32/platformio.ini": "PlatformIO build config: ESP32 board, Arduino framework, libs (HX711, IMU), serial 115200.",
    "firmware/trolley_esp32/include/pins.h": "All GPIO pin assignments (load cell, encoders, IMU) in one place.",
    "firmware/trolley_esp32/include/protocol.h": "Frame types and field layout; must match shared/contracts/esp32_serial_protocol.md.",
    "firmware/trolley_esp32/src/main.cpp": "Boot, create FreeRTOS tasks (Core 0 motion 20 Hz, Core 1 load cell), start serial link.",
    "firmware/trolley_esp32/src/tasks/loadcell_task.cpp": "Core 1 task: reads HX711 load cells and emits weight events (Component 1).",
    "firmware/trolley_esp32/src/tasks/motion_task.cpp": "Core 0 task: samples wheel encoders + IMU at 20 Hz and emits motion frames (Component 3).",
    "firmware/trolley_esp32/src/comms/serial_link.cpp": "Thread-safe USB-UART writer/reader; serialises frames per the protocol.",
    # data
    "data/store_map/store_graph.json": "Mock store graph: nodes, edges with metre lengths, aisle/product mapping (5-6 aisles).",
    "data/store_map/apriltag_layout.json": "AprilTag ID -> checkpoint node and pose.",
    # ml
    "ml/colab/comp1_validation_train.ipynb": "Colab launcher for Component 1 training (clone, mount Drive, run train.py).",
    "ml/colab/comp2_yolo_train.ipynb": "Colab launcher for Component 2 YOLO training.",
    "ml/colab/comp3_cnn_train.ipynb": "Colab launcher for Component 3 aisle-classifier training.",
    "ml/configs/comp1_validation.yaml": "Hyperparameters and paths for Component 1 training.",
    "ml/configs/comp2_yolo.yaml": "Hyperparameters, dataset path and augmentation for YOLO training.",
    "ml/configs/comp3_cnn.yaml": "Hyperparameters and dataset path for the aisle classifier.",
    "ml/configs/comp3_reco.yaml": "Recommendation settings: TF-IDF params, K for KNN, fusion weights, detour threshold.",
    "ml/configs/comp4_monthly.yaml": "Hyperparameters for the monthly-purchase predictor.",
    # simulations
    "simulations/store_navigation_sim.html": "Interactive store navigation simulator (Held-Karp routing, dual corridors).",
    "simulations/end_to_end_walkthrough.html": "Seven-stage end-to-end presentation walkthrough for the panel.",
    "simulations/trolley_pipeline_sim.html": "Animated onboard-pipeline mock trolley with checkout/reset flow.",
    # scripts
    "scripts/bootstrap.sh": "One-command dev setup: venvs, npm install, pre-commit install, .env copy.",
    "scripts/seed_db.py": "Loads shared/db/seed/*.csv into the database.",
    "scripts/run_demo.sh": "Starts the full stack (and hardware bridge) for the panel demo.",
    # tests
    "tests/contract/test_event_schemas.py": "Validates sample payloads from every component against events.schema.json.",
    "tests/integration/test_c1_to_c2.py": "Valid item from C1 reaches C2 and updates the cart.",
    "tests/integration/test_c2_to_c3.py": "Cart update from C2 triggers C3 recommendation + route update.",
    "tests/integration/test_c3_to_c4.py": "Confirmed cart and recommendation outcome reach C4 billing/history.",
    "tests/e2e/test_full_shopping_session.py": "Scripted full session: add items, navigate, confirm suggestion, checkout.",
    "tests/e2e/test_latency_budget.py": "Asserts end-to-end latency budgets (event -> screen update).",
    "tests/hardware/test_esp32_link.py": "Hardware-in-the-loop: ESP32 frames parse correctly (skipped without device).",
}

# --------------------------------------------------------------------------- #
# FOLDER SPECS  path -> (purpose, what lives here, rules, copilot prompt)
# --------------------------------------------------------------------------- #
D = {}


def d(path, purpose, contains, rules, prompt):
    D[path] = (purpose, contains, rules, prompt)


d(".", "Project root: entry README, build/dev tooling, containers, git hygiene.",
  "README.md, Makefile, docker-compose*.yml, .gitignore, .env.example, pre-commit config.",
  "Changed only on develop. No source code at root.",
  "Write the root README for the smart shopping trolley project: overview of the four components, architecture diagram placeholder, quick start (make setup, make up), branch model (comp -> develop -> test -> main), and links to docs/BRANCHING.md and docs/FOLDER_GUIDE.md.")

d(".github", "Repository governance: ownership, templates, CI, Copilot rules.",
  "CODEOWNERS, pull_request_template.md, copilot-instructions.md, ISSUE_TEMPLATE/, workflows/.",
  "Develop-only. A broken workflow blocks every member, so test changes in a PR first.",
  "Create CODEOWNERS mapping the ownership table in docs/BRANCHING.md to placeholders @comp1-owner..@comp4-owner (shared paths require all four). Create a PR template with a checklist: only owned paths changed, unit tests pass, contract tests pass, linked issue, logs/screenshots attached.")

d(".github/workflows", "GitHub Actions pipelines that enforce the promotion gates.",
  "ci-develop.yml (PR to develop), ci-test.yml (PR to test), release-main.yml (merge to main).",
  "Keep jobs fast on develop (unit + contract only); heavy integration/E2E belongs to ci-test.",
  "Write three GitHub Actions workflows. ci-develop: Python 3.11 matrix over backend/comp1..4 and gateway running ruff and pytest, then pytest tests/contract, then Node 20 build of frontend/trolley-display. ci-test: docker compose -f docker-compose.yml -f docker-compose.test.yml up -d, run pytest tests/integration tests/e2e, upload logs as artifacts. release-main: on push to main, create a git tag from docs/releases/CHANGELOG.md and attach build artifacts.")

d("config", "Per-environment configuration templates (DEV / TEST / PROD).",
  "dev.env.example, test.env.example, prod.env.example. Real secrets live in untracked .env files.",
  "Never commit real credentials. Every variable used in code must appear here.",
  "For every os.environ / settings field used in shared/common/config.py and each backend component, add a documented entry to the three env example files with sensible per-environment values (localhost URLs for dev, trolley-laptop LAN URLs and serial port for test, frozen demo values for prod).")

d("docs", "All human-readable documentation.",
  "BRANCHING.md, CONTRIBUTING.md, COLAB_GUIDE.md, FOLDER_GUIDE.md, plus subfolders: architecture/, api/, components/, research/ (proposal, paper, panel-slides), testing/ (+uat/), releases/.",
  "Docs are authored on develop (component design docs may be edited by their owner via PR).",
  "Draft docs/BRANCHING.md describing the model comp1-4 -> develop -> test -> main, promotion gates, hotfix rule, the ownership table, and Conventional Commit examples such as feat(comp3): add Held-Karp solver.")

d("docs/architecture", "System-level design: how the four components fit together.",
  "system-overview.md, deployment.md, sequence-diagrams/ (Mermaid or PNG).",
  "Describe interfaces, not internals; internals belong in docs/components/.",
  "Write system-overview.md: the end-to-end flow weight event (C1) -> valid item (C1) -> recognition and cart (C2) -> recommendation + routing (C3) -> billing and history (C4). Add a Mermaid sequence diagram per hop and a hardware block diagram.")

d("docs/api", "Generated API reference per service.",
  "OpenAPI exports (json/yaml) and rendered docs.",
  "Generated, not hand-edited. Source of truth is shared/contracts/openapi.yaml.",
  "Write a script that exports the OpenAPI JSON from each FastAPI service into this folder and a short README table listing each endpoint, owner component and request/response model.")

d("docs/components", "One design document per component (goals, algorithms, inputs/outputs, evaluation).",
  "comp1-..., comp2-..., comp3-..., comp4-... .md",
  "Owner updates only their file. Anything touching another component goes through an issue.",
  "For my component, write a design doc with: problem, inputs/outputs (reference event names in shared/contracts/events.schema.json), algorithm steps, assumptions, evaluation metrics, risks and open questions.")

d("docs/research", "Research artefacts: proposal, paper drafts, panel slides.",
  "proposal/, paper/, panel-slides/ (PDF, PPTX, LaTeX, .docx).",
  "Binary files only here; keep them small. Paper figures regenerate from evaluation/.",
  "Create a paper skeleton with sections Abstract, Introduction, Related Work, System Design, Methodology per component, Evaluation, Limitations, Conclusion, References; add TODO markers for results that come from evaluation/.")

d("docs/testing", "Test strategy and recorded results, including UAT.",
  "test-plan.md, integration-test-report.md, uat/uat-plan.md, uat/uat-results.md.",
  "Results are committed on develop (never directly on test) and flow forward.",
  "Write a test plan covering unit, contract, integration, E2E, hardware-in-the-loop and UAT: what each level proves, tools, who runs it, and the pass criteria required to promote develop -> test and test -> main.")

d("shared", "Code and definitions used by more than one component.",
  "contracts/ (event + API + serial schemas), db/ (schema, migrations, seed), common/ (config, logging, event bus, http client, auth).",
  "DEVELOP-ONLY. Any change needs a PR reviewed by all four members. Components must not import each other, only shared/.",
  "Review changes in this folder for backward compatibility: list which components break if a field is renamed or removed, and suggest a versioned alternative.")

d("shared/contracts", "The integration contract between components.",
  "events.schema.json (JSON Schema), openapi.yaml, esp32_serial_protocol.md.",
  "Additive changes only after first integration. Bump a schema version on any breaking change.",
  "Extend events.schema.json with JSON Schema definitions for weight_event, valid_item_event, cart_updated, recommendation_event, route_update and checkout_event (required fields: event_id, session_id, timestamp, type, payload). Then generate matching Pydantic models and a pytest that validates sample payloads.")

d("shared/db", "Database definition shared by all services.",
  "schema.sql, migrations/ (numbered SQL or Alembic), seed/ (products.csv, store_locations.csv).",
  "Migrations are append-only. Never edit a migration that has been merged.",
  "Write schema.sql for PostgreSQL: products, aisles, store_locations, sessions, carts, cart_items, bills, purchase_history, with primary/foreign keys and indexes, plus an initial numbered migration that creates them.")

d("shared/common", "Reusable Python helpers imported by every backend service.",
  "config.py, logging.py, event_bus.py, http_client.py, auth.py.",
  "No component-specific logic. Keep dependencies minimal and fully typed.",
  "Implement config.py with pydantic-settings reading environment variables (ENV, DB_URL, SERVICE_URLS, SERIAL_PORT, LOG_LEVEL), logging.py for JSON logs with session_id, and event_bus.py with publish(event) / subscribe(type, handler) over an in-process asyncio queue with a pluggable HTTP backend.")

d("backend", "All server-side Python code: gateway plus one package per component.",
  "gateway/, comp1_trigger_validation/, comp2_recognition_tracking/, comp3_reco_navigation/, comp4_pattern_billing/.",
  "A component imports only from shared/, never from another component. Each has its own requirements.txt and Dockerfile.",
  "Describe in README how to run the whole backend with uvicorn for development and how each component is mounted by the gateway.")

d("backend/gateway", "Single FastAPI entrypoint that mounts every component under a prefix.",
  "main.py, routers.py, config.py, requirements.txt, Dockerfile.",
  "No business logic: routing, CORS, health, startup only. Develop-only.",
  "Write a FastAPI app that includes the routers from comp1..comp4 under /c1../c4, exposes /health aggregating each component, enables CORS for the frontend origin, and a WebSocket /ws that forwards cart_updated, recommendation_event and route_update events to the trolley display.")

# ---- comp1 ----
C1 = "backend/comp1_trigger_validation"
d(C1, "Component 1 - detects that something was put in/taken out of the trolley and validates that it is a real shopping item.",
  "api/, services/, ml/, tests/, requirements.txt, Dockerfile.",
  "Owner: comp1. Publishes valid_item_event to the contract; never calls Component 2 code directly.",
  "Implement Component 1 end to end: ESP32 weight events -> debounce -> camera capture -> classifier -> valid_item_event, exposing FastAPI routes under /c1. Follow the folder layout (api, services, ml, tests) and the event contract.")
d(C1 + "/api", "HTTP layer of Component 1.",
  "router.py (routes), schemas.py (Pydantic models).",
  "Thin: validate input, call services, return output. No algorithms here.",
  "Create FastAPI APIRouter with POST /weight-event, POST /validate, GET /health. Define Pydantic v2 request/response models in schemas.py matching shared/contracts/events.schema.json.")
d(C1 + "/services", "Business logic of Component 1.",
  "serial_bridge, weight_event_service, camera_capture, validation_pipeline, trigger_publisher.",
  "Pure Python classes with injectable dependencies so they unit-test without hardware.",
  "Implement WeightEventService (baseline tracking, debounce window, delta threshold, add/remove sign), SerialBridge (pyserial 115200, newline-delimited JSON frames per esp32_serial_protocol.md), and ValidationPipeline combining weight and vision confidence into a decision.")
d(C1 + "/ml", "Training and inference code for the item-validation classifier.",
  "dataset.py, features.py, train.py, infer.py, evaluate.py.",
  "train.py reads ml/configs/comp1_validation.yaml and writes ml/models/comp1/<run_id>/ with metadata.json (git commit, dataset version, hyperparameters). Heavy training runs on Colab.",
  "Write train.py (argparse --config, --out, seeded, checkpointing each epoch), infer.py (load weights, predict one image), and evaluate.py (accuracy, precision, recall, confusion matrix saved to evaluation/comp1/).")
d(C1 + "/tests", "Unit tests for Component 1.",
  "test_*.py using pytest.",
  "No hardware or network: use synthetic traces and mocks.",
  "Write pytest tests for WeightEventService with synthetic weight traces: noise below threshold ignored, step add detected, step remove detected, debounce works.")

# ---- comp2 ----
C2 = "backend/comp2_recognition_tracking"
d(C2, "Component 2 - recognises which product entered/left the trolley and keeps the live cart.",
  "api/, services/, ml/, tests/, requirements.txt, Dockerfile.",
  "Owner: comp2. Consumes valid_item_event; emits cart_updated.",
  "Implement Component 2: on valid_item_event capture camera 2, isolate the item with chroma key, run YOLO, use frame differencing to confirm add vs remove, update the cart and emit cart_updated. FastAPI routes under /c2.")
d(C2 + "/api", "HTTP layer of Component 2.",
  "router.py, schemas.py.",
  "Thin routes only.",
  "Create APIRouter with POST /recognize, GET /cart/{session_id}, POST /cart/confirm, DELETE /cart/item/{id}, GET /health, with Pydantic v2 models.")
d(C2 + "/services", "Vision pipeline and cart logic.",
  "event_listener, camera2_capture, chroma_key, frame_diff, recognizer, cart_service.",
  "Each stage is a separate class so it can be tested with static images.",
  "Implement chroma_key.py (HSV green mask with OpenCV, largest-contour crop), frame_diff.py (absdiff of before/after frames with area threshold -> ADD/REMOVE/NONE), recognizer.py (wrap Ultralytics YOLO or ONNX runtime), cart_service.py (add/remove/quantity, emits cart_updated).")
d(C2 + "/ml", "YOLO dataset preparation, training, export, evaluation.",
  "dataset_prep.py, train.py, infer.py, export_onnx.py, evaluate.py.",
  "Train on Colab via ml/colab/comp2_yolo_train.ipynb. Pin ultralytics/torch versions in requirements.txt; export ONNX for the trolley laptop.",
  "Write dataset_prep.py (split train/val/test, YOLO label format, augmentation), train.py (reads ml/configs/comp2_yolo.yaml, resumes from last checkpoint on Drive), export_onnx.py and evaluate.py (mAP50, mAP50-95, per-class precision/recall).")
d(C2 + "/tests", "Unit tests for Component 2.",
  "test_frame_diff.py, test_cart_service.py.",
  "Use synthetic numpy images; no camera.",
  "Write pytest tests generating synthetic before/after frames to verify ADD, REMOVE and NONE detection, and cart tests for quantity increment/decrement.")

# ---- comp3 ----
C3 = "backend/comp3_reco_navigation"
d(C3, "Component 3 - recommends extra items worth a detour and routes the trolley through the to-buy list.",
  "api/, recommendation/, navigation/, cnn/, session/, tests/, requirements.txt, Dockerfile.",
  "Owner: comp3. Population-level POS data only (no individual customer data); recommendations need customer confirmation before becoming route stops.",
  "Implement Component 3: preprocess the POS CSV, build TF-IDF + KNN signals, fuse them, apply the relevance-vs-detour-cost filter, compute exact routes with Dijkstra + Held-Karp, and correct position at AprilTag checkpoints using encoder + IMU dead reckoning. Expose FastAPI routes under /c3.")
d(C3 + "/api", "HTTP layer of Component 3.",
  "recommend.py, route.py, checkpoint.py, session.py, schemas.py.",
  "Thin routes; algorithms live in recommendation/ and navigation/.",
  "Create routers: POST /recommend, POST /route, POST /route/recompute, POST /checkpoint, /session/tobuy (GET, POST, DELETE), /session/reset. Define Pydantic v2 models for positions, stops, routes and suggestions.")
d(C3 + "/recommendation", "Recommendation engine: three-signal fusion plus detour filter.",
  "preprocess, tfidf_category, knn_cooccurrence, fusion, detour_filter.",
  "No individual user data: preprocess.py must drop user_id. Do not use product_id as a join key (one id maps to many names in the dataset); use cleaned product names or rebuilt ids. Parameters come from ml/configs/comp3_reco.yaml.",
  "Implement preprocess.py (read data/raw CSV, drop user_id, drop non-grocery categories, build baskets, write data/processed), tfidf_category.py (sklearn TfidfVectorizer + cosine similarity), knn_cooccurrence.py (sklearn NearestNeighbors on basket vectors), fusion.py (weighted fusion of the signals described in docs/components/comp3-reco-navigation.md) and detour_filter.py (keep a candidate only when fused relevance justifies the added route length versus the current Held-Karp route; threshold configurable).")
d(C3 + "/navigation", "Routing and localisation.",
  "store_graph, dijkstra, held_karp, route_manager, apriltag, dead_reckoning, deviation.",
  "Held-Karp is exact, so the stop count must stay small (mock store: 5-6 aisles). Recompute only on deviation or list change.",
  "Implement held_karp.py (bitmask DP returning order and total length from a distance matrix), dijkstra.py (pairwise distances over store_graph.json), apriltag.py (cv2.aruco detector returning tag id and pose), dead_reckoning.py (encoder + IMU pose integration at 20 Hz) and deviation.py (epsilon(d) = 0.3 + 0.02*d metres, returns whether to recompute).")
d(C3 + "/cnn", "Ambient aisle/section classifier used between AprilTag checkpoints (not for checkpoint detection).",
  "train.py, infer.py.",
  "Train on Colab; save weights to ml/models/comp3/<run_id>/ with metadata.json.",
  "Write a small PyTorch CNN (or transfer learning with MobileNet) for aisle classification: train.py reads ml/configs/comp3_cnn.yaml and checkpoints each epoch; infer.py returns aisle label + confidence for one frame.")
d(C3 + "/session", "Session-only state for the shopper.",
  "tobuy_list.py.",
  "Nothing here may be written to disk or database; cleared on reset/checkout.",
  "Implement ToBuyList: add/remove item, mark found, list remaining, confirm a suggestion into the list, reset(); in-memory only and thread-safe.")
d(C3 + "/tests", "Unit tests for Component 3.",
  "test_held_karp, test_dijkstra, test_fusion, test_detour_filter, test_dead_reckoning.",
  "Algorithm tests must compare against brute force or hand-computed values.",
  "Write pytest tests: Held-Karp equals brute-force permutation search for up to 8 stops; Dijkstra on a hand-built 5-aisle graph; detour_filter rejects a low-relevance high-detour candidate; deviation threshold equals 0.3 + 0.02*d.")

# ---- comp4 ----
C4 = "backend/comp4_pattern_billing"
d(C4, "Component 4 - purchase history, monthly pattern prediction, billing, mobile sync.",
  "api/, services/, ml/, tests/, requirements.txt, Dockerfile.",
  "Owner: comp4. Individual-history personalisation belongs here, not in Component 3.",
  "Implement Component 4: persist purchase history, predict monthly needs, build shopping lists (with recipes), generate bills at checkout, and sync with the mobile app. FastAPI routes under /c4.")
d(C4 + "/api", "HTTP layer of Component 4.",
  "router_reco.py, router_billing.py, router_sync.py, schemas.py.",
  "Thin routes only.",
  "Create three APIRouters: recommendations/monthly list, billing (checkout, bill, status), and sync (lists, recipes, notifications) with Pydantic v2 schemas.")
d(C4 + "/services", "Business logic of Component 4.",
  "history, billing, shopping_list, recipe, notification, sync services.",
  "Database access through shared/db schema only.",
  "Implement BillingService (sum cart_items, apply prices, create bill row), HistoryService (append purchases per customer), ShoppingListService (monthly list from predictions) using SQLAlchemy against shared/db/schema.sql.")
d(C4 + "/ml", "Monthly purchase-pattern model.",
  "features.py, train.py, predict_monthly.py, evaluate.py.",
  "train.py reads ml/configs/comp4_monthly.yaml and logs run metadata like other components.",
  "Write features.py (per-customer frequency/recency features), train.py, predict_monthly.py (top-N predicted items for next month), evaluate.py (precision@k, recall@k).")
d(C4 + "/tests", "Unit tests for Component 4.",
  "test_billing.py, test_monthly_prediction.py.",
  "Use in-memory SQLite or mocks.",
  "Write pytest tests for bill totals and rounding, and for predict_monthly returning at most N unique items.")

# ---- frontend ----
d("frontend", "All user interfaces.",
  "trolley-display/ (React app on the trolley screen), mobile-app/ (customer phone app).",
  "UIs talk to the backend only through the gateway.",
  "Describe how to start the trolley display (npm run dev) pointing at the gateway URL from config.")
d("frontend/trolley-display", "React + Vite app shown on the trolley screen. One shared app, one feature folder per component.",
  "package.json, public/, src/ (app, api, components, features).",
  "Do not create a separate frontend per component. Owners edit only their features/<x> folder; shared shell (app/, api/, components/) is develop-only.",
  "Scaffold a Vite React app with routes for shopping and checkout, a gateway client with fetch + WebSocket, and a layout that renders ValidationPanel, CartPanel, navigation (MapView + RouteOverlay + ToBuyList + SuggestionCard) and BillingPanel.")
d("frontend/trolley-display/src", "Application source.",
  "main.jsx, app/ (shell + routes), api/ (gateway client), components/ (shared UI atoms), features/ (per-component UI).",
  "Shared folders (app, api, components) are develop-only.",
  "Create reusable UI components (Button, Card, Badge, Modal, Spinner) in components/ with a consistent large-touch-target style suitable for a trolley screen.")
d("frontend/trolley-display/src/features/validation", "Component 1 UI.",
  "ValidationPanel.jsx (+ any hooks/styles).",
  "Owner: comp1. Read data via api/client.js only.",
  "Build ValidationPanel showing the latest weight event, validation result (accepted/rejected) and confidence from the /c1 endpoint or WebSocket events.")
d("frontend/trolley-display/src/features/cart", "Component 2 UI.",
  "CartPanel.jsx.",
  "Owner: comp2.",
  "Build CartPanel: live list of recognised items with quantity, a confirm/remove control, and total item count updating from cart_updated events.")
d("frontend/trolley-display/src/features/navigation", "Component 3 UI: map, route, to-buy list, suggestions.",
  "MapView, RouteOverlay, ToBuyList, SuggestionCard.",
  "Owner: comp3. A suggestion must be confirmed by the customer before it is added to the route.",
  "Build MapView (SVG store map from store_graph.json with the trolley marker), RouteOverlay (polyline of the Held-Karp path, highlight next stop), ToBuyList (check-off, add/remove), SuggestionCard (shows item, aisle and detour metres with Accept/Dismiss).")
d("frontend/trolley-display/src/features/billing", "Component 4 UI.",
  "BillingPanel.jsx.",
  "Owner: comp4.",
  "Build BillingPanel: itemised bill, subtotal/discounts/total and a Pay/Done action calling the /c4 billing endpoint.")
d("frontend/mobile-app", "Customer phone app (framework to be decided: React Native or Flutter).",
  "src/features/{lists, recipes, billing, notifications}/.",
  "Owner: comp4. Decide the framework before writing code and record it in docs/architecture/.",
  "Scaffold the chosen mobile framework with four feature modules (lists, recipes, billing, notifications) that call the /c4 sync endpoints through one API client.")
d("frontend/mobile-app/src/features", "Mobile feature modules (lists, recipes, billing, notifications).",
  "One subfolder per feature.",
  "Owner: comp4.",
  "For each feature folder create a screen, an API hook and a small test, following the mobile framework's conventions.")

# ---- firmware ----
d("firmware", "Code that runs on microcontrollers.",
  "trolley_esp32/ (single shared ESP32 image).",
  "Only one firmware image exists because one ESP32 serves both Component 1 and Component 3.",
  "Explain how to build and flash with PlatformIO (pio run -t upload) and how to read the serial stream for debugging.")
d("firmware/trolley_esp32", "The one ESP32 firmware image: load-cell events (Component 1) and motion sensing (Component 3).",
  "platformio.ini, include/, src/ (main, tasks/, comms/).",
  "Shared structure is develop-owned. loadcell_task.cpp is comp1's file, motion_task.cpp is comp3's. Frame format must match shared/contracts/esp32_serial_protocol.md.",
  "Write a PlatformIO project for ESP32 (Arduino framework, 115200 baud) that creates two FreeRTOS tasks pinned to cores (Core 0 motion at 20 Hz, Core 1 load cell) and sends newline-delimited JSON frames over USB-UART via a mutex-protected serial writer.")
d("firmware/trolley_esp32/include", "Headers shared by all firmware sources.",
  "pins.h (GPIO map), protocol.h (frame types/fields).",
  "protocol.h must stay in sync with the serial protocol doc; change both in the same PR.",
  "Define pins.h constants for HX711 DT/SCK, two wheel-encoder inputs, IMU I2C SDA/SCL, and protocol.h enums/structs for frame types WEIGHT, MOTION, HEARTBEAT.")
d("firmware/trolley_esp32/src", "Firmware sources.",
  "main.cpp, tasks/, comms/.",
  "main.cpp only wires tasks; logic lives in tasks/ and comms/.",
  "Write main.cpp: initialise serial_link, pin motion_task to core 0 and loadcell_task to core 1 with xTaskCreatePinnedToCore, and a heartbeat frame every second.")
d("firmware/trolley_esp32/src/tasks", "One FreeRTOS task per sensing responsibility.",
  "loadcell_task.cpp (comp1), motion_task.cpp (comp3).",
  "Never block on serial inside a task: push frames to the serial_link queue.",
  "Implement loadcell_task (HX711 read, tare, filtering, emit WEIGHT frame on change above threshold) and motion_task (read encoders + IMU at 20 Hz via vTaskDelayUntil, emit MOTION frame with ticks and yaw rate).")
d("firmware/trolley_esp32/src/comms", "Communication with the host.",
  "serial_link.cpp.",
  "Single writer to the UART; thread-safe.",
  "Implement serial_link with a FreeRTOS queue and a writer task that serialises frames as newline-delimited JSON, and a non-blocking reader for host commands (e.g., tare).")

# ---- data ----
d("data", "Datasets and map data.",
  "raw/ (POS CSV), processed/ (cleaned outputs), store_map/ (graph + AprilTag layout), datasets/ (image datasets per component: comp1_objects, comp2_grocery_yolo, comp3_aisle_images).",
  "Large/raw data is gitignored. Document its source and version in each folder README. store_map/ is small and versioned.",
  "Write a data card for the POS CSV: columns, row counts, known issues (non-1:1 product_id/name mapping, user_id present, non-grocery categories, basket sizes 2-7, likely synthetic).")
d("data/raw", "Immutable original datasets.",
  "Retail_pos_basket_data.csv (1,991 baskets, 10,000 rows).",
  "Read-only: never edit or overwrite. Gitignored.",
  "Write a loader that reads the raw CSV with explicit dtypes and prints basic stats (rows, baskets, basket-size distribution, category counts) without modifying the file.")
d("data/processed", "Derived datasets created by code.",
  "Cleaned baskets, co-occurrence matrices, train/test splits.",
  "Generated by recommendation/preprocess.py; gitignored; always reproducible from data/raw.",
  "Write preprocess code that regenerates every file here from data/raw deterministically and records a data version hash in a manifest.")
d("data/store_map", "The mock-store map used by navigation and the UI.",
  "store_graph.json, apriltag_layout.json.",
  "Owner: comp3. Coordinates in metres. 5-6 aisles with dual corridors and cross-aisles.",
  "Generate store_graph.json for a 5-6 aisle store: nodes (id, x_m, y_m, type), edges with length_m, aisle->product mapping, and apriltag_layout.json mapping tag ids to checkpoint nodes. Add a validator script that checks connectivity.")
d("data/datasets", "Image datasets for training (comp1_objects, comp2_grocery_yolo, comp3_aisle_images).",
  "One subfolder per component, versioned v1, v2...",
  "Gitignored; stored on Google Drive; each subfolder needs a data card.",
  "Write a script that validates an image dataset folder (class counts, corrupted files, train/val/test split sizes) and prints a data card.")

# ---- ml ----
d("ml", "Machine-learning workspace for training outside the backend runtime (Google Colab).",
  "colab/ (launcher notebooks), configs/ (YAML hyperparameters), notebooks/ (EDA), models/ (gitignored artifacts).",
  "Training logic lives in each component's ml/train.py; this folder only configures and launches it.",
  "Explain the training workflow: Colab notebook clones the repo, mounts Drive, runs train.py with a YAML config, saves weights + metadata.json to Drive under runs/<component>/<run_id>/.")
d("ml/colab", "Thin Colab launcher notebooks.",
  "comp1_validation_train.ipynb, comp2_yolo_train.ipynb, comp3_cnn_train.ipynb.",
  "Notebooks contain no training logic, only setup + a call to train.py. Outputs stripped before commit (nbstripout).",
  "Create a 5-cell Colab notebook: install requirements, clone repo and checkout branch, mount Google Drive, run train.py with --config and --out on Drive, copy final weights and metadata.json to Drive.")
d("ml/configs", "Versioned hyperparameters per model.",
  "comp1_validation, comp2_yolo, comp3_cnn, comp3_reco, comp4_monthly (.yaml).",
  "Every reported result must be reproducible from a config plus a commit hash.",
  "Write YAML configs with seed, dataset path, epochs, batch size, learning rate, augmentation and output directory, with comments explaining each key.")
d("ml/notebooks", "Exploratory notebooks (EDA, experiments).",
  "*.ipynb with outputs stripped.",
  "Exploration only: anything reusable moves into a component's ml/ package.",
  "Create an EDA notebook for the POS dataset: basket sizes, category frequencies, top co-occurring pairs, sparsity of the co-occurrence matrix.")
d("ml/models", "Trained artefacts (weights, vectorisers).",
  "<component>/<run_id>/{weights, metadata.json, metrics.json}.",
  "Gitignored. Store on Drive or GitHub Releases. metadata.json must record git commit, dataset version, hyperparameters.",
  "Write a helper that saves a model together with metadata.json (git commit hash, config, dataset hash, metrics) and a loader that verifies that metadata exists.")

# ---- others ----
d("simulations", "Standalone HTML simulations for the panel presentation.",
  "store_navigation_sim.html, end_to_end_walkthrough.html, trolley_pipeline_sim.html.",
  "Owner: comp3. Each file must be self-contained (inline CSS/JS) and visual/animated.",
  "Create a self-contained HTML page with an SVG store map, animated trolley following a Held-Karp route, controls for adding items, and a panel showing recommendation + detour cost.")
d("evaluation", "Scripts and results that produce the numbers in the paper.",
  "comp1/, comp2/, comp3/, comp4/, system/ (end-to-end).",
  "Each result file records commit hash and config used.",
  "Write an evaluation script that loads a trained model and test set, computes the metrics defined in the component design doc, and writes results.json plus a figure into this folder.")
d("scripts", "Developer and demo helper scripts.",
  "bootstrap.sh, seed_db.py, run_demo.sh.",
  "Idempotent, documented, no secrets.",
  "Write bootstrap.sh to create venvs per backend service, install requirements, run npm install, copy config/dev.env.example to .env and install pre-commit hooks.")
d("tests", "Cross-component tests (authored on develop, executed on test).",
  "contract/, integration/, e2e/, hardware/. Per-component unit tests live inside each component's tests/ folder.",
  "Do not author tests directly on the test branch.",
  "Explain how to run each test level locally and in CI, and which environment variables or services each requires.")
d("tests/contract", "Verifies that payloads match shared/contracts.",
  "test_event_schemas.py.",
  "Runs on every PR to develop.",
  "Write pytest that loads events.schema.json and validates example payloads from each component, failing on missing or extra required fields.")
d("tests/integration", "Tests of two or more services running together.",
  "test_c1_to_c2.py, test_c2_to_c3.py, test_c3_to_c4.py.",
  "Runs against docker-compose.test.yml on PR to test.",
  "Write pytest-asyncio tests that post an event to the earlier component and assert the downstream component's state or event within a timeout.")
d("tests/e2e", "Full-session and performance tests.",
  "test_full_shopping_session.py, test_latency_budget.py.",
  "Required to pass before test -> main.",
  "Write an E2E test that simulates a shopping session through the gateway and asserts final bill totals and that each event-to-screen update stays within the latency budget.")
d("tests/hardware", "Hardware-in-the-loop tests.",
  "test_esp32_link.py.",
  "Skipped automatically when no device is attached (pytest.mark.skipif).",
  "Write a test that opens the configured serial port, reads 50 frames and asserts they parse against esp32_serial_protocol.md with expected rates.")

# leaf directories that only hold .gitkeep (no README of their own)
LEAF_DIRS = [
    "docs/architecture/sequence-diagrams", "docs/research/proposal", "docs/research/paper",
    "docs/research/panel-slides", "shared/db/migrations", "frontend/trolley-display/public",
    "frontend/trolley-display/src/components", "frontend/mobile-app/src/features/lists",
    "frontend/mobile-app/src/features/recipes", "frontend/mobile-app/src/features/billing",
    "frontend/mobile-app/src/features/notifications", "data/datasets/comp1_objects",
    "data/datasets/comp2_grocery_yolo", "data/datasets/comp3_aisle_images",
    "evaluation/comp1", "evaluation/comp2", "evaluation/comp3", "evaluation/comp4", "evaluation/system",
]

CTX = ("Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). "
       "Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. "
       "Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. "
       "Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.")


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #
def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not FORCE:
        return
    p.write_text(text, encoding="utf-8")


def hdr_lines(path, desc):
    return [f"{os.path.basename(path)} - {desc}", f"Owner: {owner_of(path)}"]


def make_file(path, desc):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    L = hdr_lines(path, desc)

    if name == "LICENSE":
        return "TODO: choose a licence (or state 'All rights reserved') per SLIIT policy.\n"
    if name == ".gitignore":
        return "# " + "\n# ".join(L) + "\n\n" + GITIGNORE
    if name == "Makefile":
        return ("# " + "\n# ".join(L) + "\n\n.PHONY: setup lint test up down\n"
                "setup:\n\tbash scripts/bootstrap.sh\n"
                "lint:\n\truff check backend shared tests\n"
                "test:\n\tpytest backend tests/contract\n"
                "up:\n\tdocker compose up --build\n"
                "down:\n\tdocker compose down\n")
    if name == "events.schema.json":
        return json.dumps(EVENTS_SCHEMA(desc), indent=2) + "\n"
    if name in ("store_graph.json", "apriltag_layout.json"):
        key = "nodes" if name == "store_graph.json" else "tags"
        body = {"_description": desc, "_owner": owner_of(path), key: []}
        if key == "nodes":
            body["edges"] = []
        return json.dumps(body, indent=2) + "\n"
    if name == "package.json":
        return json.dumps({"name": "trolley-display", "private": True, "version": "0.1.0",
                           "description": desc, "scripts": {"dev": "vite", "build": "vite build"}}, indent=2) + "\n"
    if ext == ".ipynb":
        return notebook(path, desc)
    if name == "products.csv":
        return "product_id,product_name,category,price,aisle_id\n"
    if name == "store_locations.csv":
        return "product_id,aisle_id,shelf,x_m,y_m\n"
    if ext == ".py":
        return '"""\n' + "\n".join(L) + '\n"""\n'
    if ext in (".js", ".jsx", ".cpp", ".h", ".c"):
        return "/**\n * " + "\n * ".join(L) + "\n */\n"
    if ext == ".sh":
        return "#!/usr/bin/env bash\n# " + "\n# ".join(L) + "\nset -euo pipefail\n"
    if ext == ".sql":
        return "-- " + "\n-- ".join(L) + "\n"
    if ext == ".ini":
        return "; " + "\n; ".join(L) + "\n"
    if ext == ".html":
        return "<!--\n  " + "\n  ".join(L) + "\n-->\n"
    if ext == ".md":
        title = os.path.splitext(name)[0].replace("-", " ").replace("_", " ")
        return f"# {title}\n\n> {desc}\n> Owner: {owner_of(path)}\n"
    # yml, yaml, Dockerfile, CODEOWNERS, requirements.txt, .env.example, etc.
    return "# " + "\n# ".join(L) + "\n"


def notebook(path, desc):
    comp = re.search(r"comp(\d)", path).group(1)
    train = {"1": "backend/comp1_trigger_validation/ml/train.py",
             "2": "backend/comp2_recognition_tracking/ml/train.py",
             "3": "backend/comp3_reco_navigation/cnn/train.py"}[comp]
    cfg = {"1": "comp1_validation", "2": "comp2_yolo", "3": "comp3_cnn"}[comp]
    req = os.path.dirname(os.path.dirname(train)) + "/requirements.txt" if comp != "3" else "backend/comp3_reco_navigation/requirements.txt"

    def md(t):
        return {"cell_type": "markdown", "metadata": {}, "source": t.splitlines(True)}

    def code(t):
        return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.splitlines(True)}

    nb = {"cells": [
        md(f"# {os.path.basename(path)}\n\n{desc}\n\nOwner: comp{comp}. Contains NO training logic - only setup and a call to `train.py`."),
        code("BRANCH = 'comp%s'\nREPO = 'https://github.com/<org>/<repo>.git'\nRUN_ID = 'run_001'  # change per run\n" % comp),
        code("from google.colab import drive\ndrive.mount('/content/drive')"),
        code("!git clone -b $BRANCH $REPO repo && cd repo && pip install -r %s" % req),
        code("!cd repo && python %s --config ml/configs/%s.yaml --out /content/drive/MyDrive/smart-trolley/runs/comp%s/$RUN_ID" % (train, cfg, comp)),
        md("Weights and `metadata.json` are saved on Drive. Do not commit them to git."),
    ], "metadata": {"kernelspec": {"display_name": "Python 3", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}
    return json.dumps(nb, indent=1) + "\n"


def EVENTS_SCHEMA(desc):
    base = {"type": "object",
            "required": ["event_id", "session_id", "timestamp", "type", "payload"],
            "properties": {"event_id": {"type": "string"}, "session_id": {"type": "string"},
                           "timestamp": {"type": "string", "format": "date-time"},
                           "type": {"type": "string"}, "payload": {"type": "object"}}}
    defs = {}
    for t in ["weight_event", "valid_item_event", "cart_updated", "recommendation_event", "route_update", "checkout_event"]:
        s = json.loads(json.dumps(base))
        s["properties"]["type"] = {"const": t}
        defs[t] = s
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$comment": f"{desc} DRAFT: payload fields per event must be agreed by all four members before first integration.",
            "title": "Smart trolley events", "$defs": defs,
            "oneOf": [{"$ref": f"#/$defs/{k}"} for k in defs]}


GITIGNORE = """.env
*.env
!*.env.example
__pycache__/
*.pyc
.venv/
node_modules/
dist/
.ipynb_checkpoints/
data/raw/*
!data/raw/README.md
data/processed/*
data/datasets/*/*
!data/datasets/*/.gitkeep
ml/models/*
!ml/models/README.md
*.pt
*.onnx
*.pkl
.pio/
"""

COPILOT_INSTRUCTIONS = """# Copilot instructions - J26-IT-340 smart shopping trolley

- Monorepo with four components (comp1 trigger/validation, comp2 recognition/cart, comp3 recommendation/navigation, comp4 pattern/billing).
- Python 3.11, FastAPI, Pydantic v2, pytest; React + Vite; ESP32 firmware via PlatformIO.
- Edit only the folder you are working in. Never import one component from another; use `shared/`.
- All cross-component messages must match `shared/contracts/events.schema.json`.
- Every file starts with a header comment describing its purpose; keep it accurate.
- Training code lives in each component's `ml/train.py`, reads a YAML from `ml/configs/`, and runs on Google Colab; never commit data or weights.
- Component 3 uses population-level data only (drop `user_id`), Held-Karp over Dijkstra distances, AprilTag via `cv2.aruco`, and epsilon(d) = 0.3 + 0.02*d.
- Add type hints, docstrings and unit tests with every function.
"""


def build_readme(folder):
    purpose, contains, rules, prompt = D[folder]
    here = "" if folder == "." else folder
    files = [(p, dsc) for p, dsc in F.items()
             if dsc and (os.path.dirname(p) == here)]
    subs = sorted({k for k in list(D) + LEAF_DIRS
                   if k != "." and (os.path.dirname(k) == here)})
    lines = [f"# {folder if folder != '.' else 'smart-trolley (repo root)'}", "",
             f"**Owner:** {owner_of(here or 'README.md')}", "",
             "## Responsibility", purpose, "",
             "## What lives here", contains, "",
             "## Rules", rules, ""]
    if files:
        lines += ["## Files in this folder"] + [f"- `{os.path.basename(p)}` - {dsc}" for p, dsc in files] + [""]
    if subs:
        lines += ["## Subfolders"] + [f"- `{os.path.basename(s)}/`" for s in subs] + [""]
    lines += ["## GitHub Copilot prompt",
              "Open this folder in VS Code, open Copilot Chat, and paste:", "",
              "```text", CTX, "", "Task for this folder: " + prompt, "```", ""]
    return "\n".join(lines)


def folder_guide():
    rows = ["# Folder guide", "", "> Index of every responsibility folder. Each folder has a README with rules and a Copilot prompt.",
            "", "| Folder | Owner | Responsibility |", "|---|---|---|"]
    for k in sorted(D):
        rows.append(f"| `{k}` | {owner_of(k if k != '.' else 'README.md')} | {D[k][0]} |")
    return "\n".join(rows) + "\n"


def main():
    # directories
    for k in list(D) + LEAF_DIRS:
        (ROOT / k).mkdir(parents=True, exist_ok=True)
    for k in LEAF_DIRS:
        write(f"{k}/.gitkeep", "")
    write(".github/copilot-instructions.md", COPILOT_INSTRUCTIONS)
    # files with header comments
    for p, dsc in F.items():
        if dsc is None:
            continue
        write(p, make_file(p, dsc))
    # folder READMEs
    for k in D:
        write(("README.md" if k == "." else f"{k}/README.md"), build_readme(k))
    write("docs/FOLDER_GUIDE.md", folder_guide())
    print(f"Done: {len(F)} files, {len(D)} folder READMEs, {len(LEAF_DIRS)} leaf dirs.")


if __name__ == "__main__":
    main()
