# tests/integration

**Owner:** develop (shared - all four members review)

## Responsibility
Tests of two or more services running together.

## What lives here
test_c1_to_c2.py, test_c2_to_c3.py, test_c3_to_c4.py.

## Rules
Runs against docker-compose.test.yml on PR to test.

## Files in this folder
- `test_c1_to_c2.py` - Valid item from C1 reaches C2 and updates the cart.
- `test_c2_to_c3.py` - Cart update from C2 triggers C3 recommendation + route update.
- `test_c3_to_c4.py` - Confirmed cart and recommendation outcome reach C4 billing/history.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write pytest-asyncio tests that post an event to the earlier component and assert the downstream component's state or event within a timeout.
```
