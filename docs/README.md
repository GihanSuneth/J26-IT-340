# docs

**Owner:** develop (shared - all four members review)

## Responsibility
All human-readable documentation.

## What lives here
BRANCHING.md, CONTRIBUTING.md, COLAB_GUIDE.md, FOLDER_GUIDE.md, plus subfolders: architecture/, api/, components/, research/ (proposal, paper, panel-slides), testing/ (+uat/), releases/.

## Rules
Docs are authored on develop (component design docs may be edited by their owner via PR).

## Files in this folder
- `BRANCHING.md` - Branch model (comp -> develop -> test -> main), gates, ownership table, hotfix rule.
- `CONTRIBUTING.md` - Commit convention, PR rules, code style, how to run tests locally.
- `COLAB_GUIDE.md` - How to train on Google Colab: Drive layout, run IDs, checkpointing, exporting weights.

## Subfolders
- `api/`
- `architecture/`
- `components/`
- `research/`
- `testing/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Draft docs/BRANCHING.md describing the model comp1-4 -> develop -> test -> main, promotion gates, hotfix rule, the ownership table, and Conventional Commit examples such as feat(comp3): add Held-Karp solver.
```
