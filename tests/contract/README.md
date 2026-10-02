# tests/contract

**Owner:** develop (shared - all four members review)

## Responsibility
Verifies that payloads match shared/contracts.

## What lives here
test_event_schemas.py.

## Rules
Runs on every PR to develop.

## Files in this folder
- `test_event_schemas.py` - Validates sample payloads from every component against events.schema.json.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write pytest that loads events.schema.json and validates example payloads from each component, failing on missing or extra required fields.
```
