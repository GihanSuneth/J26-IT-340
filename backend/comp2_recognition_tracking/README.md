# backend/comp2_recognition_tracking

**Owner:** comp2

## Responsibility
Component 2 - recognises which product entered/left the trolley and keeps the live cart.

## What lives here
api/, services/, ml/, tests/, requirements.txt, Dockerfile.

## Rules
Owner: comp2. Consumes valid_item_event; emits cart_updated.

## Files in this folder
- `requirements.txt` - Python dependencies for Component 2 (fastapi, opencv-python, ultralytics, onnxruntime, numpy).
- `Dockerfile` - Container image for Component 2.

## Subfolders
- `api/`
- `ml/`
- `services/`
- `tests/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 2: on valid_item_event capture camera 2, isolate the item with chroma key, run YOLO, use frame differencing to confirm add vs remove, update the cart and emit cart_updated. FastAPI routes under /c2.
```
