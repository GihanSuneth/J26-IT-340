# frontend/trolley-display

**Owner:** develop (shared - all four members review)

## Responsibility
React + Vite app shown on the trolley screen. One shared app, one feature folder per component.

## What lives here
package.json, public/, src/ (app, api, components, features).

## Rules
Do not create a separate frontend per component. Owners edit only their features/<x> folder; shared shell (app/, api/, components/) is develop-only.

## Files in this folder
- `package.json` - Frontend dependencies and scripts (React + Vite).

## Subfolders
- `public/`
- `src/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Scaffold a Vite React app with routes for shopping and checkout, a gateway client with fetch + WebSocket, and a layout that renders ValidationPanel, CartPanel, navigation (MapView + RouteOverlay + ToBuyList + SuggestionCard) and BillingPanel.
```
