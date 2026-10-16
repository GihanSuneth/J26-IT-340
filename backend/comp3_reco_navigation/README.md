# backend/comp3_reco_navigation

**Owner:** comp3

## Responsibility
Component 3 - recommends extra items worth a detour and routes the trolley through the to-buy list.

## What lives here
api/, recommendation/, navigation/, cnn/, session/, tests/, requirements.txt, Dockerfile.

## Rules
Owner: comp3. Population-level POS data only (no individual customer data); recommendations need customer confirmation before becoming route stops.

## Files in this folder
- `requirements.txt` - Python dependencies for Component 3 (fastapi, scikit-learn, pandas, numpy, networkx/scipy, opencv-contrib-python, pyserial).
- `Dockerfile` - Container image for Component 3.

## Subfolders
- `api/`
- `cnn/`
- `navigation/`
- `recommendation/`
- `session/`
- `tests/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement Component 3: preprocess the POS CSV, build TF-IDF + KNN signals, fuse them, apply the relevance-vs-detour-cost filter, compute exact routes with Dijkstra + Held-Karp, and correct position at AprilTag checkpoints using encoder + IMU dead reckoning. Expose FastAPI routes under /c3.
```
