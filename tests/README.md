# tests

**Owner:** develop (shared - all four members review)

## Responsibility
Cross-component tests (authored on develop, executed on test).

## What lives here
contract/, integration/, e2e/, hardware/. Per-component unit tests live inside each component's tests/ folder.

## Rules
Do not author tests directly on the test branch.

## Subfolders
- `contract/`
- `e2e/`
- `hardware/`
- `integration/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Explain how to run each test level locally and in CI, and which environment variables or services each requires.
```
