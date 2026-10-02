# frontend/trolley-display/src/features/navigation

**Owner:** comp3

## Responsibility
Component 3 UI: map, route, to-buy list, suggestions.

## What lives here
MapView, RouteOverlay, ToBuyList, SuggestionCard.

## Rules
Owner: comp3. A suggestion must be confirmed by the customer before it is added to the route.

## Files in this folder
- `MapView.jsx` - Draws the store map and the trolley's current position.
- `RouteOverlay.jsx` - Draws the Held-Karp route and highlights the next stop.
- `ToBuyList.jsx` - Session to-buy list with check-off and add/remove.
- `SuggestionCard.jsx` - Shows a recommendation with detour cost; customer must confirm before it joins the route.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Build MapView (SVG store map from store_graph.json with the trolley marker), RouteOverlay (polyline of the Held-Karp path, highlight next stop), ToBuyList (check-off, add/remove), SuggestionCard (shows item, aisle and detour metres with Accept/Dismiss).
```
