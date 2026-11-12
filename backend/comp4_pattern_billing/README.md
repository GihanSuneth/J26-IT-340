# backend/comp4_pattern_billing

**Owner:** comp4

## Responsibility
Component 4 - purchase history, monthly pattern prediction, billing, mobile sync.

## What lives here
api/, services/, ml/, tests/, requirements.txt, Dockerfile.

## Rules
Owner: comp4. Individual-history personalisation belongs here, not in Component 3.

## Files in this folder
- `requirements.txt` - Python dependencies for Component 4 (fastapi, sqlalchemy, psycopg, pandas, scikit-learn).
- `Dockerfile` - Container image for Component 4.

## Subfolders
- `api/`
- `ml/`
- `services/`
- `tests/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 4: persist purchase history, predict monthly needs, build shopping lists (with recipes), generate bills at checkout, and sync with the mobile app. FastAPI routes under /c4.
```
