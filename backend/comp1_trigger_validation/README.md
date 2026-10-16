# backend/comp1_trigger_validation

**Owner:** comp1

## Responsibility
Component 1 - detects that something was put in/taken out of the trolley and validates that it is a real shopping item.

## What lives here
api/, services/, ml/, tests/, requirements.txt, Dockerfile.

## Rules
Owner: comp1. Publishes valid_item_event to the contract; never calls Component 2 code directly.

## Files in this folder
- `requirements.txt` - Python dependencies for Component 1 (fastapi, pyserial, opencv-python, scikit-learn/torch).
- `Dockerfile` - Container image for Component 1.

## Subfolders
- `api/`
- `ml/`
- `services/`
- `tests/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 1 end to end: ESP32 weight events -> debounce -> camera capture -> classifier -> valid_item_event, exposing FastAPI routes under /c1. Follow the folder layout (api, services, ml, tests) and the event contract.
```
