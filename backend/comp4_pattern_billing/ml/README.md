# backend/comp4_pattern_billing/ml

**Owner:** comp4

## Responsibility
Monthly purchase-pattern model.

## What lives here
features.py, train.py, predict_monthly.py, evaluate.py.

## Rules
train.py reads ml/configs/comp4_monthly.yaml and logs run metadata like other components.

## Files in this folder
- `__init__.py` - Package marker.
- `features.py` - Builds per-customer purchase-pattern features.
- `train.py` - Trains the monthly-purchase predictor. Reads ml/configs/comp4_monthly.yaml.
- `predict_monthly.py` - Predicts next month's likely purchases for a customer.
- `evaluate.py` - Evaluates predictions; writes to evaluation/comp4/.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write features.py (per-customer frequency/recency features), train.py, predict_monthly.py (top-N predicted items for next month), evaluate.py (precision@k, recall@k).
```
