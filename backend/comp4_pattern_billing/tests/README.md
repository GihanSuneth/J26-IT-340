# backend/comp4_pattern_billing/tests

**Owner:** comp4

## Responsibility
Unit tests for Component 4.

## What lives here
test_billing.py, test_monthly_prediction.py.

## Rules
Use in-memory SQLite or mocks.

## Files in this folder
- `test_billing.py` - Unit tests for totals, rounding and bill creation.
- `test_monthly_prediction.py` - Unit tests for the monthly prediction interface and output shape.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write pytest tests for bill totals and rounding, and for predict_monthly returning at most N unique items.
```
