# J26-IT-340 — IoT Smart Shopping Trolley

Final-year research repository for a four-component smart-shopping-trolley
system. Component 3 contains the active recommendation and indoor-navigation
research implementation; the other component workspaces, shared contracts,
firmware, frontend shell, training notebooks, and integration tests remain
separate so their ownership and research boundaries are clear.

## Project layout

| Area | Location | Purpose |
| --- | --- | --- |
| Component 1 | `backend/comp1_trigger_validation/` | Item trigger and validation |
| Component 2 | `backend/comp2_recognition_tracking/` | Product recognition and cart tracking |
| Component 3 | `component3/` | Recommendation, navigation, localisation, dashboard, models, data, and evidence |
| Component 4 | `backend/comp4_pattern_billing/` | Purchase patterns, billing, and mobile features |
| Shared backend | `backend/gateway/`, `shared/` | Gateway boundary, contracts, common code, schema, and seed data |
| User interfaces | `frontend/` | React trolley display and mobile-application workspace |
| Firmware | `firmware/trolley_esp32/`, `component3/firmware/` | ESP32 application and Component 3 motion task |
| ML workspaces | `ml/`, `component3/ml/` | Training notebooks, configurations, and preserved model artifacts |
| Data and evaluation | `data/`, `evaluation/`, `component3/data/`, `component3/evaluation/` | Datasets, generated results, and research evidence |
| Cross-component tests | `tests/` | Contract, integration, end-to-end, and hardware tests |

Detailed Component 3 commands, data policy, and evidence workflow are in
[`component3/README.md`](component3/README.md). Frontend and backend instructions
are consolidated in [`frontend/README.md`](frontend/README.md) and
[`backend/README.md`](backend/README.md).

## Prerequisites

- Python compatible with the component being tested; the preserved Component 3
  environment is `component3/.venv`.
- Node.js 20 or newer for `frontend/trolley-display`.
- PlatformIO for ESP32 firmware builds.
- Real cameras, AprilTags, and trolley hardware only for explicitly marked
  physical acceptance tests.

No active Docker or Docker Compose workflow is provided. The previous Docker
files were empty scaffolding and were removed during repository cleanup.

## Common commands

Run commands from the repository root.

```bash
# Component 3 dashboard
component3/run/start_dashboard.sh

# Lightweight Python test set
make test

# Complete Component 3 regression suites
make test-component3

# Frontend production build
make frontend-build

# Component 3 evidence integrity
make evidence
```

The customer dashboard is available at `http://127.0.0.1:8765/customer` after
the Component 3 dashboard starts. Use `component3/run/check_dashboard.sh` for a
read-only environment and readiness check.

## Data, models, and reproducibility

- Do not commit credentials or local `.env` files; `.env.example` is retained as
  the repository-level placeholder.
- Shared seed inputs are under `shared/db/seed/` and contracts under
  `shared/contracts/`.
- Component 1 and Component 2 training notebooks remain in `ml/colab/`.
- The Component 3 notebook remains in `component3/ml/colab/`.
- Component 3 frozen recommendation models remain in
  `component3/ml/models/comp3/recommendation_phase8b/`.
- Component 3 research evidence and preserved experiment outputs remain under
  `component3/evaluation/` and `component3/docs/research_evidence/`.
- Raw datasets, source image collections, virtual environments, dependency
  directories, caches, and ordinary generated build output are ignored where
  appropriate. Existing research datasets and evidence are intentionally kept.

## Development boundaries

Components should communicate through `shared/contracts/`, not import another
component's internal implementation. The root gateway and several non-Component-3
packages are research scaffolds rather than a claimed production deployment.
Hardware-dependent tests must be reported as skipped or pending when the required
device is unavailable.
