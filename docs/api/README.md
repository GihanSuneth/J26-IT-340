# docs/api

**Owner:** develop (shared - all four members review)

## Responsibility
Generated API reference per service.

## What lives here
OpenAPI exports (json/yaml) and rendered docs.

## Rules
Generated, not hand-edited. Source of truth is shared/contracts/openapi.yaml.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a script that exports the OpenAPI JSON from each FastAPI service into this folder and a short README table listing each endpoint, owner component and request/response model.
```
