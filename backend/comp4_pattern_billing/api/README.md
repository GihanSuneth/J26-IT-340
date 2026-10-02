# backend/comp4_pattern_billing/api

**Owner:** comp4

## Responsibility
HTTP layer of Component 4.

## What lives here
router_reco.py, router_billing.py, router_sync.py, schemas.py.

## Rules
Thin routes only.

## Files in this folder
- `__init__.py` - Package marker.
- `router_reco.py` - Routes for history-based (individual) recommendations and monthly lists.
- `router_billing.py` - Routes for checkout, bill generation and payment status.
- `router_sync.py` - Routes syncing lists, recipes and bills with the mobile app.
- `schemas.py` - Pydantic models for Component 4 endpoints.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create three APIRouters: recommendations/monthly list, billing (checkout, bill, status), and sync (lists, recipes, notifications) with Pydantic v2 schemas.
```
