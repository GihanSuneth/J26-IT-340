# frontend/trolley-display

**Owner:** develop (shared - all four members review)

## Responsibility
React + Vite app shown on the trolley screen. The application shell and other component features remain shared here.

## What lives here
package.json, public/, src/ (app, api, components, features).

## Rules
The shared shell (`app/`, `api/`, and `components/`) is develop-owned. Component 3 navigation views (`comp3_map_view.jsx`, `comp3_route_overlay.jsx`, `comp3_to_buy_list.jsx`, and `comp3_suggestion_card.jsx`) are maintained under `../../component3/frontend/navigation/`.

## Getting started

Requires Node.js 20 or newer.

```sh
npm install
npm run dev
```

Create a production build with `npm run build`, or preview it locally with
`npm run preview`.

## Files in this folder
- `package.json` - Frontend dependencies and scripts (React + Vite).
- `vite.config.js` - Vite configuration and React plugin.
- `index.html` - Vite application entry document.

## Subfolders
- `public/`
- `src/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Scaffold a Vite React app with routes for shopping and checkout, a gateway client with fetch + WebSocket, and a layout that renders ValidationPanel, CartPanel, navigation (MapView + RouteOverlay + ToBuyList + SuggestionCard) and BillingPanel.
```
