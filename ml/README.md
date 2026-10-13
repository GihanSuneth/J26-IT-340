# ml

**Owner:** develop (shared - all four members review)

## Responsibility
Shared and non-Component-3 machine-learning workspace for training outside the backend runtime.

## What lives here
colab/ (launcher notebooks), configs/ (YAML hyperparameters), notebooks/ (EDA), models/ (gitignored artifacts).

## Rules
Component 3 ML files are grouped under `../component3/ml/`; other components continue to use this shared layout.

## Subfolders
- `colab/`
- `configs/`
- `models/`
- `notebooks/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Explain the training workflow: Colab notebook clones the repo, mounts Drive, runs train.py with a YAML config, saves weights + metadata.json to Drive under runs/<component>/<run_id>/.
```
