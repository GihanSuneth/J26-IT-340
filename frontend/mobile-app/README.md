# frontend/mobile-app

**Owner:** comp4

## Responsibility
Customer phone app (framework to be decided: React Native or Flutter).

## What lives here
src/features/{lists, recipes, billing, notifications}/.

## Rules
Owner: comp4. Decide the framework before writing code and record it in docs/architecture/.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Scaffold the chosen mobile framework with four feature modules (lists, recipes, billing, notifications) that call the /c4 sync endpoints through one API client.
```
