# backend/comp1_trigger_validation/services

**Owner:** comp1

## Responsibility
Business logic of Component 1.

## What lives here
serial_bridge, weight_event_service, camera_capture, validation_pipeline, trigger_publisher.

## Rules
Pure Python classes with injectable dependencies so they unit-test without hardware.

## Files in this folder
- `__init__.py` - Package marker.
- `serial_bridge.py` - Reads ESP32 serial frames and turns load-cell frames into weight samples.
- `weight_event_service.py` - Debounce, baseline and delta-threshold logic: decides when a weight change is an add/remove event.
- `camera_capture.py` - Grabs a still/short clip from camera 1 when a weight event fires.
- `validation_pipeline.py` - Combines weight evidence and vision classifier into a valid/invalid item decision.
- `trigger_publisher.py` - Publishes the valid_item_event that triggers Component 2.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement WeightEventService (baseline tracking, debounce window, delta threshold, add/remove sign), SerialBridge (pyserial 115200, newline-delimited JSON frames per esp32_serial_protocol.md), and ValidationPipeline combining weight and vision confidence into a decision.
```
