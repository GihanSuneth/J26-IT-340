# tests/hardware

**Owner:** develop (shared - all four members review)

## Responsibility
Hardware-in-the-loop tests.

## What lives here
test_esp32_link.py.

## Rules
Skipped automatically when no device is attached (pytest.mark.skipif).

## Files in this folder
- `test_esp32_link.py` - Hardware-in-the-loop: ESP32 frames parse correctly (skipped without device).

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a test that opens the configured serial port, reads 50 frames and asserts they parse against esp32_serial_protocol.md with expected rates.
```
