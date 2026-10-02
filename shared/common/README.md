# shared/common

**Owner:** develop (shared - all four members review)

## Responsibility
Reusable Python helpers imported by every backend service.

## What lives here
config.py, logging.py, event_bus.py, http_client.py, auth.py.

## Rules
No component-specific logic. Keep dependencies minimal and fully typed.

## Files in this folder
- `__init__.py` - Package marker for shared helpers.
- `config.py` - Loads environment configuration into a typed settings object used by all services.
- `logging.py` - Single structured-logging setup so every service logs in the same format.
- `event_bus.py` - Publish/subscribe wrapper for inter-component events (in-process queue or HTTP/WebSocket).
- `http_client.py` - Shared HTTP client with timeouts/retries for service-to-service calls.
- `auth.py` - Session/token helpers shared by the gateway and the mobile sync API.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement config.py with pydantic-settings reading environment variables (ENV, DB_URL, SERVICE_URLS, SERIAL_PORT, LOG_LEVEL), logging.py for JSON logs with session_id, and event_bus.py with publish(event) / subscribe(type, handler) over an in-process asyncio queue with a pluggable HTTP backend.
```
