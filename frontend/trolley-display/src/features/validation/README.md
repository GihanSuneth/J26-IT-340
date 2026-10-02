# frontend/trolley-display/src/features/validation

**Owner:** comp1

## Responsibility
Component 1 UI.

## What lives here
ValidationPanel.jsx (+ any hooks/styles).

## Rules
Owner: comp1. Read data via api/client.js only.

## Files in this folder
- `ValidationPanel.jsx` - Shows item-validation status (accepted/rejected) from Component 1.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Build ValidationPanel showing the latest weight event, validation result (accepted/rejected) and confidence from the /c1 endpoint or WebSocket events.
```
