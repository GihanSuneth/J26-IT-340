# firmware/trolley_esp32/include

**Owner:** develop (shared - all four members review)

## Responsibility
Headers shared by all firmware sources.

## What lives here
pins.h (GPIO map), protocol.h (frame types/fields).

## Rules
protocol.h must stay in sync with the serial protocol doc; change both in the same PR.

## Files in this folder
- `pins.h` - All GPIO pin assignments (load cell, encoders, IMU) in one place.
- `protocol.h` - Frame types and field layout; must match shared/contracts/esp32_serial_protocol.md.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Define pins.h constants for HX711 DT/SCK, two wheel-encoder inputs, IMU I2C SDA/SCL, and protocol.h enums/structs for frame types WEIGHT, MOTION, HEARTBEAT.
```
