# backend/comp3_reco_navigation/cnn

**Owner:** comp3

## Responsibility
Ambient aisle/section classifier used between AprilTag checkpoints (not for checkpoint detection).

## What lives here
train.py, infer.py.

## Rules
Train on Colab; save weights to ml/models/comp3/<run_id>/ with metadata.json.

## Files in this folder
- `__init__.py` - Package marker.
- `train.py` - Trains the ambient aisle/section classifier. Reads ml/configs/comp3_cnn.yaml; run from Colab.
- `infer.py` - Runs the aisle classifier on a frame between checkpoints.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a small PyTorch CNN (or transfer learning with MobileNet) for aisle classification: train.py reads ml/configs/comp3_cnn.yaml and checkpoints each epoch; infer.py returns aisle label + confidence for one frame.
```
