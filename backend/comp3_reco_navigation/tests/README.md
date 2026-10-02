# backend/comp3_reco_navigation/tests

**Owner:** comp3

## Responsibility
Unit tests for Component 3.

## What lives here
test_held_karp, test_dijkstra, test_fusion, test_detour_filter, test_dead_reckoning.

## Rules
Algorithm tests must compare against brute force or hand-computed values.

## Files in this folder
- `test_held_karp.py` - Held-Karp optimality tests against brute force on small instances.
- `test_dijkstra.py` - Shortest-path tests on the mock store graph.
- `test_fusion.py` - Tests for score fusion ordering and weights.
- `test_detour_filter.py` - Tests that costly low-relevance detours are rejected and cheap relevant ones accepted.
- `test_dead_reckoning.py` - Tests for position drift and the adaptive epsilon(d) deviation threshold.

## GitHub Copilot prompt
Open this folder in VS Code, open Copilot Chat, and paste:

```text
Context: monorepo for SLIIT research project J26-IT-340 (IoT smart shopping trolley, four components). Backend: Python 3.11, FastAPI, Pydantic v2. Frontend: React + Vite. Firmware: ESP32, PlatformIO. Work ONLY inside this folder. Inter-component messages must follow shared/contracts/events.schema.json. Use type hints, docstrings and pytest unit tests. Keep each file's header comment accurate.

Task for this folder: Write pytest tests: Held-Karp equals brute-force permutation search for up to 8 stops; Dijkstra on a hand-built 5-aisle graph; detour_filter rejects a low-relevance high-detour candidate; deviation threshold equals 0.3 + 0.02*d.
```
