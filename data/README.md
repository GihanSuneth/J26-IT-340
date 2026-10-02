# data

**Owner:** develop (shared - all four members review)

## Responsibility
Datasets and map data.

## What lives here
raw/ (POS CSV), processed/ (cleaned outputs), store_map/ (graph + AprilTag layout), datasets/ (image datasets per component: comp1_objects, comp2_grocery_yolo, comp3_aisle_images).

## Rules
Large/raw data is gitignored. Document its source and version in each folder README. store_map/ is small and versioned.

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
