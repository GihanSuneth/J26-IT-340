# evaluation

**Owner:** develop (shared - all four members review)

## Responsibility
Scripts and results that produce the numbers in the paper.

## What lives here
comp1/, comp2/, comp3/, comp4/, system/ (end-to-end).

## Rules
Each result file records commit hash and config used.

## Subfolders
- `comp1/`
- `comp2/`
- `comp3/`
- `comp4/`
- `system/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write an evaluation script that loads a trained model and test set, computes the metrics defined in the component design doc, and writes results.json plus a figure into this folder.
```
