# .github

**Owner:** develop (shared - all four members review)

## Responsibility
Repository governance: ownership, templates, CI, Copilot rules.

## What lives here
CODEOWNERS, pull_request_template.md, copilot-instructions.md, ISSUE_TEMPLATE/, workflows/.

## Rules
Develop-only. A broken workflow blocks every member, so test changes in a PR first.

## Files in this folder
- `CODEOWNERS` - Maps each path to its owning member; enforces the ownership table in docs/BRANCHING.md.
- `pull_request_template.md` - PR checklist: owned paths only, unit + contract tests pass, linked issue, screenshots/logs.
- `copilot-instructions.md` - Repo-wide rules GitHub Copilot follows in every suggestion.

## Subfolders
- `workflows/`

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Create CODEOWNERS mapping the ownership table in docs/BRANCHING.md to placeholders @comp1-owner..@comp4-owner (shared paths require all four). Create a PR template with a checklist: only owned paths changed, unit tests pass, contract tests pass, linked issue, logs/screenshots attached.
```
