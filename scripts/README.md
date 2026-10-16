# scripts

**Owner:** develop (shared - all four members review)

## Responsibility
Developer and demo helper scripts.

## What lives here
bootstrap.sh, seed_db.py, run_demo.sh.

## Rules
Idempotent, documented, no secrets.

## Files in this folder
- `bootstrap.sh` - One-command dev setup: venvs, npm install, pre-commit install, .env copy.
- `seed_db.py` - Loads shared/db/seed/*.csv into the database.
- `run_demo.sh` - Starts the full stack (and hardware bridge) for the panel demo.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write bootstrap.sh to create venvs per backend service, install requirements, run npm install, copy config/dev.env.example to .env and install pre-commit hooks.
```
