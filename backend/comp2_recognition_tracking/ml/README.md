# backend/comp2_recognition_tracking/ml

**Owner:** comp2

## Responsibility
YOLO dataset preparation, training, export, evaluation.

## What lives here
dataset_prep.py, train.py, infer.py, export_onnx.py, evaluate.py.

## Rules
Train on Colab via ml/colab/comp2_yolo_train.ipynb. Pin ultralytics/torch versions in requirements.txt; export ONNX for the trolley laptop.

## Files in this folder
- `__init__.py` - Package marker.
- `dataset_prep.py` - Builds the YOLO dataset (labels, splits, augmentation) from raw grocery images.
- `train.py` - YOLO training entrypoint. Reads ml/configs/comp2_yolo.yaml; run from Colab.
- `infer.py` - Runs inference with the exported model on one frame.
- `export_onnx.py` - Exports trained weights to ONNX/pt for the trolley laptop (pins versions).
- `evaluate.py` - mAP/precision/recall evaluation; writes to evaluation/comp2/.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write dataset_prep.py (split train/val/test, YOLO label format, augmentation), train.py (reads ml/configs/comp2_yolo.yaml, resumes from last checkpoint on Drive), export_onnx.py and evaluate.py (mAP50, mAP50-95, per-class precision/recall).
```
