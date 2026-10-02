# firmware/trolley_esp32/src/tasks

**Owner:** comp1 (loadcell_task) + comp3 (motion_task)

## Responsibility
One FreeRTOS task per sensing responsibility.

## What lives here
loadcell_task.cpp (comp1), motion_task.cpp (comp3).

## Rules
Never block on serial inside a task: push frames to the serial_link queue.

## Files in this folder
- `loadcell_task.cpp` - Core 1 task: reads HX711 load cells and emits weight events (Component 1).
- `motion_task.cpp` - Core 0 task: samples wheel encoders + IMU at 20 Hz and emits motion frames (Component 3).

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement loadcell_task (HX711 read, tare, filtering, emit WEIGHT frame on change above threshold) and motion_task (read encoders + IMU at 20 Hz via vTaskDelayUntil, emit MOTION frame with ticks and yaw rate).
```
