# firmware/trolley_esp32/src/comms

**Owner:** develop (shared - all four members review)

## Responsibility
Communication with the host.

## What lives here
serial_link.cpp.

## Rules
Single writer to the UART; thread-safe.

## Files in this folder
- `serial_link.cpp` - Thread-safe USB-UART writer/reader; serialises frames per the protocol.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement serial_link with a FreeRTOS queue and a writer task that serialises frames as newline-delimited JSON, and a non-blocking reader for host commands (e.g., tare).
```
