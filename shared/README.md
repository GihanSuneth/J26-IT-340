# shared

**Owner:** develop (shared - all four members review)

## Responsibility
Code and definitions used by more than one component.

## What lives here
contracts/ (event + API + serial schemas), db/ (schema, migrations, seed), common/ (config, logging, event bus, http client, auth).

## Rules
DEVELOP-ONLY. Any change needs a PR reviewed by all four members. Components must not import each other, only shared/.

## Subfolders
- `common/`
- `contracts/`
- `db/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Review changes in this folder for backward compatibility: list which components break if a field is renamed or removed, and suggest a versioned alternative.
```
