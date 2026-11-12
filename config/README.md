# config

**Owner:** develop (shared - all four members review)

## Responsibility
Per-environment configuration templates (DEV / TEST / PROD).

## What lives here
dev.env.example, test.env.example, prod.env.example. Real secrets live in untracked .env files.

## Rules
Never commit real credentials. Every variable used in code must appear here.

## Files in this folder
- `dev.env.example` - DEV environment values: localhost URLs, simulated sensors, debug logging.
- `test.env.example` - TEST/UAT values: trolley-laptop URLs, real ESP32 serial port, test DB.
- `prod.env.example` - PROD/panel-demo values: frozen config, debug off, demo store map.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: For every os.environ / settings field used in shared/common/config.py and each backend component, add a documented entry to the three env example files with sensible per-environment values (localhost URLs for dev, trolley-laptop LAN URLs and serial port for test, frozen demo values for prod).
```
