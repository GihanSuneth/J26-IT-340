# simulations

**Owner:** comp3

## Responsibility
Standalone HTML simulations for the panel presentation.

## What lives here
store_navigation_sim.html, end_to_end_walkthrough.html, trolley_pipeline_sim.html.

## Rules
Owner: comp3. Each file must be self-contained (inline CSS/JS) and visual/animated.

## Files in this folder
- `store_navigation_sim.html` - Interactive store navigation simulator (Held-Karp routing, dual corridors).
- `end_to_end_walkthrough.html` - Seven-stage end-to-end presentation walkthrough for the panel.
- `trolley_pipeline_sim.html` - Animated onboard-pipeline mock trolley with checkout/reset flow.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create a self-contained HTML page with an SVG store map, animated trolley following a Held-Karp route, controls for adding items, and a panel showing recommendation + detour cost.
```
