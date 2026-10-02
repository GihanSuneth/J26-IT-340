# frontend/mobile-app/src/features

**Owner:** comp4

## Responsibility
Mobile feature modules (lists, recipes, billing, notifications).

## What lives here
One subfolder per feature.

## Rules
Owner: comp4.

## Subfolders
- `billing/`
- `lists/`
- `notifications/`
- `recipes/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: For each feature folder create a screen, an API hook and a small test, following the mobile framework's conventions.
```
