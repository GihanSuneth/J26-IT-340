# frontend/trolley-display/src/features/cart

**Owner:** comp2

## Responsibility
Component 2 UI.

## What lives here
CartPanel.jsx.

## Rules
Owner: comp2.

## Files in this folder
- `CartPanel.jsx` - Live cart list with add/remove confirmation from Component 2.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Build CartPanel: live list of recognised items with quantity, a confirm/remove control, and total item count updating from cart_updated events.
```
