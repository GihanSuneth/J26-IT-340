# backend

**Owner:** develop (shared - all four members review)

## Responsibility
All server-side Python code: gateway plus one package per component.

## What lives here
gateway/, comp1_trigger_validation/, comp2_recognition_tracking/, comp3_reco_navigation/, comp4_pattern_billing/.

## Rules
A component imports only from shared/, never from another component. Each has its own requirements.txt and Dockerfile.

## Subfolders
- `comp1_trigger_validation/`
- `comp2_recognition_tracking/`
- `comp3_reco_navigation/`
- `comp4_pattern_billing/`
- `gateway/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Describe in README how to run the whole backend with uvicorn for development and how each component is mounted by the gateway.
```
