# firmware/trolley_esp32/src

**Owner:** develop (shared - all four members review)

## Responsibility
Firmware sources.

## What lives here
main.cpp, tasks/, comms/.

## Rules
main.cpp only wires tasks; logic lives in tasks/ and comms/.

## Files in this folder
- `main.cpp` - Boot, create FreeRTOS tasks (Core 0 motion 20 Hz, Core 1 load cell), start serial link.

## Subfolders
- `comms/`
- `tasks/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write main.cpp: initialise serial_link, pin motion_task to core 0 and loadcell_task to core 1 with xTaskCreatePinnedToCore, and a heartbeat frame every second.
```
