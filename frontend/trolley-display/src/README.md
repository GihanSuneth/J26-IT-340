# frontend/trolley-display/src

**Owner:** develop (shared - all four members review)

## Responsibility
Application source.

## What lives here
main.jsx, app/ (shell + routes), api/ (gateway client), components/ (shared UI atoms), features/ (per-component UI).

## Rules
Shared folders (app, api, components) are develop-only.

## Files in this folder
- `main.jsx` - React entrypoint: mounts <App/>.

## Subfolders
- `components/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create reusable UI components (Button, Card, Badge, Modal, Spinner) in components/ with a consistent large-touch-target style suitable for a trolley screen.
```
