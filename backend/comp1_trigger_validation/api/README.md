# backend/comp1_trigger_validation/api

**Owner:** comp1

## Responsibility
HTTP layer of Component 1.

## What lives here
router.py (routes), schemas.py (Pydantic models).

## Rules
Thin: validate input, call services, return output. No algorithms here.

## Files in this folder
- `__init__.py` - Package marker.
- `router.py` - FastAPI routes for Component 1 (weight-event ingest, validate, health).
- `schemas.py` - Pydantic request/response models for Component 1 endpoints.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create FastAPI APIRouter with POST /weight-event, POST /validate, GET /health. Define Pydantic v2 request/response models in schemas.py matching shared/contracts/events.schema.json.
```
