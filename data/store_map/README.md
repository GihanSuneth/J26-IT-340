# data/store_map

**Owner:** comp3

## Responsibility
The mock-store map used by navigation and the UI.

## What lives here
store_graph.json, apriltag_layout.json.

## Rules
Owner: comp3. Coordinates in metres. 5-6 aisles with dual corridors and cross-aisles.

## Files in this folder
- `store_graph.json` - Mock store graph: nodes, edges with metre lengths, aisle/product mapping (5-6 aisles).
- `apriltag_layout.json` - AprilTag ID -> checkpoint node and pose.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Generate store_graph.json for a 5-6 aisle store: nodes (id, x_m, y_m, type), edges with length_m, aisle->product mapping, and apriltag_layout.json mapping tag ids to checkpoint nodes. Add a validator script that checks connectivity.
```
