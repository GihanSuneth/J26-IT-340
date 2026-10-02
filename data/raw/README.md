# data/raw

**Owner:** develop (shared - all four members review)

## Responsibility
Immutable original datasets.

## What lives here
Retail_pos_basket_data.csv (1,991 baskets, 10,000 rows).

## Rules
Read-only: never edit or overwrite. Gitignored.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a loader that reads the raw CSV with explicit dtypes and prints basic stats (rows, baskets, basket-size distribution, category counts) without modifying the file.
```
