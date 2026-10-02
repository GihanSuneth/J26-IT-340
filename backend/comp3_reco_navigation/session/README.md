# backend/comp3_reco_navigation/session

**Owner:** comp3

## Responsibility
Session-only state for the shopper.

## What lives here
tobuy_list.py.

## Rules
Nothing here may be written to disk or database; cleared on reset/checkout.

## Files in this folder
- `__init__.py` - Package marker.
- `tobuy_list.py` - In-memory, session-only to-buy list (nothing persisted after reset).

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement ToBuyList: add/remove item, mark found, list remaining, confirm a suggestion into the list, reset(); in-memory only and thread-safe.
```
