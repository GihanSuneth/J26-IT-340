# docs/testing

**Owner:** develop (shared - all four members review)

## Responsibility
Test strategy and recorded results, including UAT.

## What lives here
test-plan.md, integration-test-report.md, uat/uat-plan.md, uat/uat-results.md.

## Rules
Results are committed on develop (never directly on test) and flow forward.

## Files in this folder
- `test-plan.md` - What is tested at each level (unit, contract, integration, E2E, UAT) and pass criteria.
- `integration-test-report.md` - Results of integration runs on the test branch (date, commit, pass/fail, defects).

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write a test plan covering unit, contract, integration, E2E, hardware-in-the-loop and UAT: what each level proves, tools, who runs it, and the pass criteria required to promote develop -> test and test -> main.
```
