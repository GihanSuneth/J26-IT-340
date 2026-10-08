# Copilot instructions - J26-IT-340 smart shopping trolley

- Monorepo with four components (comp1 trigger/validation, comp2 recognition/cart, comp3 recommendation/navigation, comp4 pattern/billing).
- Python 3.11, FastAPI, Pydantic v2, pytest; React + Vite; ESP32 firmware via PlatformIO.
- Edit only the folder you are working in. Never import one component from another; use `shared/`.
- All cross-component messages must match `shared/contracts/events.schema.json`.
- Every file starts with a header comment describing its purpose; keep it accurate.
- Training code lives in each component's `ml/train.py`, reads a YAML from `ml/configs/`, and runs on Google Colab; never commit data or weights.
- Component 3 uses population-level data only (drop `user_id`), Held-Karp over Dijkstra distances, AprilTag via `cv2.aruco`, and epsilon(d) = 0.3 + 0.02*d.
- Add type hints, docstrings and unit tests with every function.
