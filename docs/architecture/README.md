# docs/architecture

**Owner:** develop (shared - all four members review)

## Responsibility
System-level design: how the four components fit together.

## What lives here
system-overview.md, deployment.md, sequence-diagrams/ (Mermaid or PNG).

## Rules
Describe interfaces, not internals; internals belong in docs/components/.

## Files in this folder
- `system-overview.md` - End-to-end architecture: four components, data flow, event sequence, hardware.
- `deployment.md` - How DEV, TEST and PROD environments are run and what hardware each needs.

## Subfolders
- `sequence-diagrams/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write system-overview.md: the end-to-end flow weight event (C1) -> valid item (C1) -> recognition and cart (C2) -> recommendation + routing (C3) -> billing and history (C4). Add a Mermaid sequence diagram per hop and a hardware block diagram.
```
