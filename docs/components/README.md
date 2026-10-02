# docs/components

**Owner:** develop (shared - all four members review)

## Responsibility
One design document per component (goals, algorithms, inputs/outputs, evaluation).

## What lives here
comp1-..., comp2-..., comp3-..., comp4-... .md

## Rules
Owner updates only their file. Anything touching another component goes through an issue.

## Files in this folder
- `comp1-trigger-validation.md` - Component 1 design: weight trigger, item validation, outputs and accuracy targets.
- `comp2-recognition-tracking.md` - Component 2 design: camera capture, chroma-key, YOLO recognition, cart state.
- `comp3-reco-navigation.md` - Component 3 design: three-signal fusion, detour filter, Held-Karp routing, AprilTag/dead-reckoning.
- `comp4-pattern-billing.md` - Component 4 design: purchase history, monthly prediction, billing, mobile sync.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: For my component, write a design doc with: problem, inputs/outputs (reference event names in shared/contracts/events.schema.json), algorithm steps, assumptions, evaluation metrics, risks and open questions.
```
