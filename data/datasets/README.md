# data/datasets

**Owner:** develop (shared - all four members review)

## Responsibility
Image datasets for training (comp1_objects, comp2_grocery_yolo, comp3_aisle_images).

## What lives here
One subfolder per component, versioned v1, v2...

## Rules
Gitignored; stored on Google Drive; each subfolder needs a data card.

## Subfolders
- `comp1_objects/`
- `comp2_grocery_yolo/`
- `comp3_aisle_images/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a script that validates an image dataset folder (class counts, corrupted files, train/val/test split sizes) and prints a data card.
```
