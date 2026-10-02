# .github/workflows

**Owner:** develop (shared - all four members review)

## Responsibility
GitHub Actions pipelines that enforce the promotion gates.

## What lives here
ci-develop.yml (PR to develop), ci-test.yml (PR to test), release-main.yml (merge to main).

## Rules
Keep jobs fast on develop (unit + contract only); heavy integration/E2E belongs to ci-test.

## Files in this folder
- `ci-develop.yml` - CI on PR to develop: lint, per-component unit tests, contract tests, frontend build.
- `ci-test.yml` - CI on PR to test: docker-compose.test.yml up, run tests/integration and tests/e2e.
- `release-main.yml` - On merge to main: tag the release, attach build artifacts, publish CHANGELOG entry.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write three GitHub Actions workflows. ci-develop: Python 3.11 matrix over backend/comp1..4 and gateway running ruff and pytest, then pytest tests/contract, then Node 20 build of frontend/trolley-display. ci-test: docker compose -f docker-compose.yml -f docker-compose.test.yml up -d, run pytest tests/integration tests/e2e, upload logs as artifacts. release-main: on push to main, create a git tag from docs/releases/CHANGELOG.md and attach build artifacts.
```
