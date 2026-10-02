# backend/comp3_reco_navigation/api

**Owner:** comp3

## Responsibility
HTTP layer of Component 3.

## What lives here
recommend.py, route.py, checkpoint.py, session.py, schemas.py.

## Rules
Thin routes; algorithms live in recommendation/ and navigation/.

## Files in this folder
- `__init__.py` - Package marker.
- `recommend.py` - POST /recommend: basket + current position -> filtered recommendations.
- `route.py` - POST /route and /route/recompute: to-buy list -> ordered stops and path.
- `checkpoint.py` - POST /checkpoint: AprilTag hit and dead-reckoning updates from the trolley.
- `session.py` - Session-only to-buy list endpoints (add, remove, confirm suggestion, reset).
- `schemas.py` - Pydantic models for all Component 3 requests/responses.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create routers: POST /recommend, POST /route, POST /route/recompute, POST /checkpoint, /session/tobuy (GET, POST, DELETE), /session/reset. Define Pydantic v2 models for positions, stops, routes and suggestions.
```
