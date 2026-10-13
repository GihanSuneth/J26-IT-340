# firmware/trolley_esp32

**Owner:** develop (shared - all four members review)

## Responsibility
The shared ESP32 application, load-cell task, protocol, and communication layer.

## What lives here
platformio.ini, include/, src/ (main, tasks/, comms/).

## Rules
Shared structure is develop-owned. `loadcell_task.cpp` remains here; the Component 3 motion task is under `../../component3/firmware/motion_task.cpp`. Frame format must match `shared/contracts/esp32_serial_protocol.md`.

## Files in this folder
- `platformio.ini` - PlatformIO build config: ESP32 board, Arduino framework, libs (HX711, IMU), serial 115200.

## Subfolders
- `include/`
- `src/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a PlatformIO project for ESP32 (Arduino framework, 115200 baud) that creates two FreeRTOS tasks pinned to cores (Core 0 motion at 20 Hz, Core 1 load cell) and sends newline-delimited JSON frames over USB-UART via a mutex-protected serial writer.
```
