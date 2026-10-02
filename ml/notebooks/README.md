# ml/notebooks

**Owner:** develop (shared - all four members review)

## Responsibility
Exploratory notebooks (EDA, experiments).

## What lives here
*.ipynb with outputs stripped.

## Rules
Exploration only: anything reusable moves into a component's ml/ package.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create an EDA notebook for the POS dataset: basket sizes, category frequencies, top co-occurring pairs, sparsity of the co-occurrence matrix.
```
