# data

**Owner:** develop (shared - all four members review)

## Responsibility
Datasets and map data.

## What lives here
Shared raw/processed data and datasets for the common project layout. Component 3 POS
data, aisle images, generated artifacts, and store maps live under `component3/data/`.

## Rules
Large/raw data is gitignored. Document its source and version in each folder README.

## Subfolders
- `datasets/`
- `processed/`
- `raw/`
- `store_map/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a data card for the POS CSV: columns, row counts, known issues (non-1:1 product_id/name mapping, user_id present, non-grocery categories, basket sizes 2-7, likely synthetic).
```
