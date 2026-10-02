# tests/e2e

**Owner:** develop (shared - all four members review)

## Responsibility
Full-session and performance tests.

## What lives here
test_full_shopping_session.py, test_latency_budget.py.

## Rules
Required to pass before test -> main.

## Files in this folder
- `test_full_shopping_session.py` - Scripted full session: add items, navigate, confirm suggestion, checkout.
- `test_latency_budget.py` - Asserts end-to-end latency budgets (event -> screen update).

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write an E2E test that simulates a shopping session through the gateway and asserts final bill totals and that each event-to-screen update stays within the latency budget.
```
