# frontend/trolley-display/src/features/billing

**Owner:** comp4

## Responsibility
Component 4 UI.

## What lives here
BillingPanel.jsx.

## Rules
Owner: comp4.

## Files in this folder
- `BillingPanel.jsx` - Checkout summary and bill from Component 4.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Build BillingPanel: itemised bill, subtotal/discounts/total and a Pay/Done action calling the /c4 billing endpoint.
```
