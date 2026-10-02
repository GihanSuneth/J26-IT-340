# backend/comp2_recognition_tracking/services

**Owner:** comp2

## Responsibility
Vision pipeline and cart logic.

## What lives here
event_listener, camera2_capture, chroma_key, frame_diff, recognizer, cart_service.

## Rules
Each stage is a separate class so it can be tested with static images.

## Files in this folder
- `__init__.py` - Package marker.
- `event_listener.py` - Subscribes to Component 1's valid_item_event and starts a recognition run.
- `camera2_capture.py` - Captures frames from the cart-interior camera 2.
- `chroma_key.py` - Isolates the item from the green-screen background before recognition.
- `frame_diff.py` - Frame differencing to decide whether an item was added or removed.
- `recognizer.py` - Wraps the YOLO model: image in, product label + confidence out.
- `cart_service.py` - Maintains cart state (items, quantities) and emits cart_updated events.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Implement chroma_key.py (HSV green mask with OpenCV, largest-contour crop), frame_diff.py (absdiff of before/after frames with area threshold -> ADD/REMOVE/NONE), recognizer.py (wrap Ultralytics YOLO or ONNX runtime), cart_service.py (add/remove/quantity, emits cart_updated).
```
