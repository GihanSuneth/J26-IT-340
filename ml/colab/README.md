# ml/colab

**Owner:** develop (shared - all four members review)

## Responsibility
Thin Colab launcher notebooks.

## What lives here
comp1_validation_train.ipynb, comp2_yolo_train.ipynb, comp3_cnn_train.ipynb.

## Rules
Notebooks contain no training logic, only setup + a call to train.py. Outputs stripped before commit (nbstripout).

## Files in this folder
- `comp1_validation_train.ipynb` - Colab launcher for Component 1 training (clone, mount Drive, run train.py).
- `comp2_yolo_train.ipynb` - Colab launcher for Component 2 YOLO training.
- `comp3_cnn_train.ipynb` - Colab launcher for Component 3 aisle-classifier training.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create a 5-cell Colab notebook: install requirements, clone repo and checkout branch, mount Google Drive, run train.py with --config and --out on Drive, copy final weights and metadata.json to Drive.
```
