# backend/comp3_reco_navigation/navigation

**Owner:** comp3

## Responsibility
Routing and localisation.

## What lives here
store_graph, dijkstra, held_karp, route_manager, apriltag, dead_reckoning, deviation.

## Rules
Held-Karp is exact, so the stop count must stay small (mock store: 5-6 aisles). Recompute only on deviation or list change.

## Files in this folder
- `__init__.py` - Package marker.
- `store_graph.py` - Loads data/store_map/store_graph.json into a graph (aisles, dual corridors, cross-aisles).
- `dijkstra.py` - Pairwise shortest-path distances between product stops.
- `held_karp.py` - Exact multi-stop TSP via Held-Karp DP over the Dijkstra distance matrix.
- `route_manager.py` - Owns the active route; recomputes only on deviation or to-buy-list change.
- `apriltag.py` - AprilTag detection with cv2.aruco; maps tag IDs to checkpoint nodes.
- `dead_reckoning.py` - Wheel-encoder + IMU position estimate between checkpoints.
- `deviation.py` - Adaptive deviation test: epsilon(d) = eps_base + sigma*d (eps_base=0.3 m, sigma=0.02).

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement held_karp.py (bitmask DP returning order and total length from a distance matrix), dijkstra.py (pairwise distances over store_graph.json), apriltag.py (cv2.aruco detector returning tag id and pose), dead_reckoning.py (encoder + IMU pose integration at 20 Hz) and deviation.py (epsilon(d) = 0.3 + 0.02*d metres, returns whether to recompute).
```
