# backend/comp1_trigger_validation/ml

**Owner:** comp1

## Responsibility
Training and inference code for the item-validation classifier.

## What lives here
dataset.py, features.py, train.py, infer.py, evaluate.py.

## Rules
train.py reads ml/configs/comp1_validation.yaml and writes ml/models/comp1/<run_id>/ with metadata.json (git commit, dataset version, hyperparameters). Heavy training runs on Colab.

## Files in this folder
- `__init__.py` - Package marker.
- `dataset.py` - Loads/labels the valid-vs-non-shopping-object dataset.
- `features.py` - Feature extraction (image and weight features) for the validation classifier.
- `train.py` - Training entrypoint. Reads ml/configs/comp1_validation.yaml; writes ml/models/comp1/<run_id>/. Run from Colab.
- `infer.py` - Loads the trained model and returns a validity prediction for one capture.
- `evaluate.py` - Computes accuracy/precision/recall/confusion matrix; writes to evaluation/comp1/.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write train.py (argparse --config, --out, seeded, checkpointing each epoch), infer.py (load weights, predict one image), and evaluate.py (accuracy, precision, recall, confusion matrix saved to evaluation/comp1/).
```
