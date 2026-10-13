# data

**Owner:** develop (shared - all four members review)

## Responsibility
Shared and non-Component-3 datasets.

## What lives here
raw/, processed/, and datasets/ for shared use and the other components. Component 3 data lives under `../component3/data/`.

## Rules
Large/raw data is gitignored. Document its source and version in the relevant dataset folder.

## Subfolders
- `datasets/`
- `processed/`
- `raw/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Maintain shared and non-Component-3 dataset documentation without moving component-owned data out of its workspace.
```
