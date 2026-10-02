# docs/research

**Owner:** develop (shared - all four members review)

## Responsibility
Research artefacts: proposal, paper drafts, panel slides.

## What lives here
proposal/, paper/, panel-slides/ (PDF, PPTX, LaTeX, .docx).

## Rules
Binary files only here; keep them small. Paper figures regenerate from evaluation/.

## Subfolders
- `panel-slides/`
- `paper/`
- `proposal/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create a paper skeleton with sections Abstract, Introduction, Related Work, System Design, Methodology per component, Evaluation, Limitations, Conclusion, References; add TODO markers for results that come from evaluation/.
```
