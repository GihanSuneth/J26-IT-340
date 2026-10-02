# backend/comp2_recognition_tracking/tests

**Owner:** comp2

## Responsibility
Unit tests for Component 2.

## What lives here
test_frame_diff.py, test_cart_service.py.

## Rules
Use synthetic numpy images; no camera.

## Files in this folder
- `test_frame_diff.py` - Unit tests for add/remove detection using synthetic frames.
- `test_cart_service.py` - Unit tests for cart add/remove/quantity logic.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write pytest tests generating synthetic before/after frames to verify ADD, REMOVE and NONE detection, and cart tests for quantity increment/decrement.
```
