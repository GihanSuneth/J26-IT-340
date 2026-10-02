# ml/models

**Owner:** develop (shared - all four members review)

## Responsibility
Trained artefacts (weights, vectorisers).

## What lives here
<component>/<run_id>/{weights, metadata.json, metrics.json}.

## Rules
Gitignored. Store on Drive or GitHub Releases. metadata.json must record git commit, dataset version, hyperparameters.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a helper that saves a model together with metadata.json (git commit hash, config, dataset hash, metrics) and a loader that verifies that metadata exists.
```
