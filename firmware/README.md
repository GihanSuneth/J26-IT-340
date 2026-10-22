# firmware

**Owner:** develop (shared - all four members review)

## Responsibility
Code that runs on microcontrollers.

## What lives here
trolley_esp32/ (single shared ESP32 image).

## Rules
Only one firmware image exists because one ESP32 serves both Component 1 and Component 3.

## Subfolders
- `trolley_esp32/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Explain how to build and flash with PlatformIO (pio run -t upload) and how to read the serial stream for debugging.
```
