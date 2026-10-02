# ml/configs

**Owner:** develop (shared - all four members review)

## Responsibility
Versioned hyperparameters per model.

## What lives here
comp1_validation, comp2_yolo, comp3_cnn, comp3_reco, comp4_monthly (.yaml).

## Rules
Every reported result must be reproducible from a config plus a commit hash.

## Files in this folder
- `comp1_validation.yaml` - Hyperparameters and paths for Component 1 training.
- `comp2_yolo.yaml` - Hyperparameters, dataset path and augmentation for YOLO training.
- `comp3_cnn.yaml` - Hyperparameters and dataset path for the aisle classifier.
- `comp3_reco.yaml` - Recommendation settings: TF-IDF params, K for KNN, fusion weights, detour threshold.
- `comp4_monthly.yaml` - Hyperparameters for the monthly-purchase predictor.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write YAML configs with seed, dataset path, epochs, batch size, learning rate, augmentation and output directory, with comments explaining each key.
```
