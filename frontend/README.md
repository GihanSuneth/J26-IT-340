# frontend

**Owner:** develop (shared - all four members review)

## Responsibility
All user interfaces.

## What lives here
trolley-display/ (React app on the trolley screen), mobile-app/ (customer phone app).

## Rules
UIs talk to the backend only through the gateway.

## Subfolders
- `mobile-app/`
- `trolley-display/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Describe how to start the trolley display (npm run dev) pointing at the gateway URL from config.
```
