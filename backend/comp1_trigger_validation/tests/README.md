# backend/comp1_trigger_validation/tests

**Owner:** comp1

## Responsibility
Unit tests for Component 1.

## What lives here
test_*.py using pytest.

## Rules
No hardware or network: use synthetic traces and mocks.

## Files in this folder
- `test_weight_events.py` - Unit tests for debounce/threshold logic with synthetic weight traces.
- `test_validation_pipeline.py` - Unit tests for the validation decision logic with mocked classifier output.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write pytest tests for WeightEventService with synthetic weight traces: noise below threshold ignored, step add detected, step remove detected, debounce works.
```
