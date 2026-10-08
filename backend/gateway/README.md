# backend/gateway

**Owner:** develop (shared - all four members review)

## Responsibility
Single FastAPI entrypoint that mounts every component under a prefix.

## What lives here
main.py, routers.py, config.py, requirements.txt, Dockerfile.

## Rules
No business logic: routing, CORS, health, startup only. Develop-only.

## Files in this folder
- `main.py` - FastAPI entrypoint: creates the app, mounts routers, CORS, health check, startup wiring.
- `routers.py` - Includes each component's router under /c1, /c2, /c3, /c4 prefixes.
- `config.py` - Gateway-specific settings (ports, allowed origins, service URLs).
- `requirements.txt` - Python dependencies of the gateway (fastapi, uvicorn, pydantic, httpx).
- `Dockerfile` - Container image for the gateway service.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a FastAPI app that includes the routers from comp1..comp4 under /c1../c4, exposes /health aggregating each component, enables CORS for the frontend origin, and a WebSocket /ws that forwards cart_updated, recommendation_event and route_update events to the trolley display.
```
