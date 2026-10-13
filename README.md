# J26-IT-340 — IoT Smart Shopping Trolley

Shared final-year research repository for the four smart-trolley components.
Component implementations remain isolated by ownership, while contracts,
database definitions, application shells, configuration, and integration tests
remain at the repository root.

## Component ownership

| Component | Location | Responsibility |
| --- | --- | --- |
| Component 1 | `backend/comp1_trigger_validation/` | Item trigger and validation |
| Component 2 | `backend/comp2_recognition_tracking/` | Product recognition and cart tracking |
| Component 3 | `component3/` | Recommendation, navigation, localisation, and aisle CNN |
| Component 4 | `backend/comp4_pattern_billing/` | Purchase patterns, billing, and mobile features |

Component 3 is intentionally grouped into one top-level workspace so its
backend, datasets, ML configuration, evaluation, evidence, UI feature, firmware
task, and simulations can be developed without reorganising files owned by the
other components.

## Shared root resources

```text
.github/                 Team workflows and repository governance
backend/gateway/         Shared API gateway
config/                  Environment templates
data/                    Shared and other-component datasets
docs/                    Project-wide architecture and team documentation
evaluation/              Other-component and system evaluation
firmware/trolley_esp32/  Shared ESP32 application, protocol, and communication
frontend/trolley-display Shared trolley-display application shell
frontend/mobile-app/     Component 4 mobile application
ml/                      Other-component ML launchers and configuration
scripts/                 Shared development and database scripts
shared/                  Common code, contracts, schema, and seed data
tests/                   Cross-component and integration tests
```

## Component 3 workspace

See [`component3/README.md`](component3/README.md) for the complete structure,
commands, data policy, and evidence workflow.

Important shared inputs used by Component 3 remain at:

- `shared/db/seed/products.csv`
- `shared/db/seed/store_locations.csv`
- `shared/contracts/`

Raw datasets, source image collections, credentials, caches, and trained model
weights are excluded from Git. Docker files at the root are part of the shared
repository scaffold; Component 3 development does not currently require Docker.
