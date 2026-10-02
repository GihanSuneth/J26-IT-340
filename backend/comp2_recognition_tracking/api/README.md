# backend/comp2_recognition_tracking/api

**Owner:** comp2

## Responsibility
HTTP layer of Component 2.

## What lives here
router.py, schemas.py.

## Rules
Thin routes only.

## Files in this folder
- `__init__.py` - Package marker.
- `router.py` - FastAPI routes: recognize, get cart, confirm/remove item, health.
- `schemas.py` - Pydantic models for recognition results and cart state.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create APIRouter with POST /recognize, GET /cart/{session_id}, POST /cart/confirm, DELETE /cart/item/{id}, GET /health, with Pydantic v2 models.
```
