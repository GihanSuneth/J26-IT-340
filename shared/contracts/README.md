# shared/contracts

**Owner:** develop (shared - all four members review)

## Responsibility
The integration contract between components.

## What lives here
events.schema.json (JSON Schema), openapi.yaml, esp32_serial_protocol.md.

## Rules
Additive changes only after first integration. Bump a schema version on any breaking change.

## Files in this folder
- `events.schema.json` - JSON Schema of every event exchanged between components (the integration contract).
- `openapi.yaml` - Combined OpenAPI description of the gateway and component REST endpoints.
- `esp32_serial_protocol.md` - Wire protocol between ESP32 and backend: frame format, message types, rates, baud 115200.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Extend events.schema.json with JSON Schema definitions for weight_event, valid_item_event, cart_updated, recommendation_event, route_update and checkout_event (required fields: event_id, session_id, timestamp, type, payload). Then generate matching Pydantic models and a pytest that validates sample payloads.
```
