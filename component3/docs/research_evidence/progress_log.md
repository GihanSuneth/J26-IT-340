# Component 3 progress log

This log records verified Component 3 development and research activities.
Copy the template below for each entry. Do not fill unknown fields with assumed
work or results; mark them `Pending` or `Not applicable`.

## Entry template

### [YYYY-MM-DD HH:MM TZ] — [Short entry title]

- **Development phase:** Pending
- **Objective:** Pending
- **Work completed:** Pending
- **Files created or modified:** Pending
- **Tools and technologies used:** Pending
- **Implementation decisions and reasons:** Pending
- **Problems encountered:** Pending
- **Solutions attempted:** Pending
- **Test results:** Pending
- **Evidence screenshot references:** Pending; do not add an evidence ID until the file exists
- **Next planned action:** Pending

## Verified entries

### 2026-10-13 22:48 +0530 — Research evidence structure established

- **Development phase:** Evidence-management setup across all Component 3 phases
- **Objective:** Establish a reproducible, non-fabricated research documentation and evidence structure.
- **Work completed:** Inspected the existing research and Component 3 evaluation directories; created the requested phase templates, screenshot placeholders, evaluation output directories, evidence index, workflow documentation, and standard-library registration and validation helpers.
- **Files created or modified:** `docs/research_evidence/component3/` and `evaluation/comp3/{test_results,metrics,logs}/.gitkeep`.
- **Tools and technologies used:** Markdown, CSV, Python 3 standard library (`argparse`, `csv`, `pathlib`), Git status inspection.
- **Implementation decisions and reasons:** Kept the evidence index header-only because no evidence artifact was produced; used `.gitkeep` for empty directories; required evidence files to exist before registration; documented Dijkstra and Held-Karp as deterministic algorithms and CNN training separately.
- **Problems encountered:** No prior `docs/research_evidence/` structure existed. Existing unrelated working-tree changes were present and were left untouched.
- **Solutions attempted:** Added an isolated Component 3 evidence structure without overwriting existing documentation or evaluation material.
- **Test results:** `py_compile` completed for both helper scripts. `validate_evidence.py` reported: `Component 3 evidence structure is valid; 0 indexed artifact(s).` All nine notes templates contained the required sections, and the CSV contained exactly the required header row.
- **Evidence screenshot references:** None. No screenshot or experimental evidence was generated during this setup task.
- **Next planned action:** Wait for approval before Component 3 implementation or experimental work.

### 2026-10-13 22:58 +0530 — Phase 1 store map and AprilTag checkpoint design

- **Development phase:** Phase 1 — Store map and AprilTag checkpoint design
- **Objective:** Create a validated simulated six-section supermarket graph, map available seed products, define AprilTag checkpoints, and collect reproducible evidence.
- **Work completed:** Replaced empty graph and tag placeholders with a 24 m × 18 m simulated layout; added 20 nodes, 29 undirected weighted edges, six sections, and eight `tag36h11` checkpoints; implemented validation and visualization scripts; generated and visually inspected two PNG figures; saved actual validation output; registered three evidence artifacts; documented the milestone.
- **Files created or modified:** `data/store_map/store_graph.json`, `data/store_map/apriltag_layout.json`, `data/store_map/visualize_store_map.py`, `data/store_map/validate_store_map.py`, `evaluation/comp3/test_results/store_map_validation.txt`, the two `02_store_map/screenshots/C3-MAP-*.png` figures, `02_store_map/notes.md`, `evidence_index.csv`, and this progress log.
- **Tools and technologies used:** Python 3.14.0 standard library, JSON, CSV, SVG, installed macOS Quick Look renderer, `sips-316` for inspection, and Git commit `0b4340f28acd805b9b4821e07a47341e06ee7133`.
- **Implementation decisions and reasons:** Used a rectangular metric coordinate system with three cross-corridors so every aisle has multiple walkable connections. Used real seed product IDs only; because the product CSV had no data rows, the mapping remains empty. Used `tag36h11` and checkpointed entrance, checkout, and six aisle access nodes. Kept Dijkstra, Held-Karp, camera detection, and CNN work out of scope.
- **Problems encountered:** Matplotlib and alternative Python plotting packages were unavailable. `sips` could not decode the generated SVG, and Quick Look was initially blocked by the sandbox. First visual inspection also showed transparent outer canvas and crowded checkpoint labels.
- **Solutions attempted:** Implemented dependency-free SVG composition, added an installed Quick Look fallback, reran it with approved access, made the canvas explicitly white, repositioned checkpoint labels, regenerated both images, and visually rechecked them.
- **Test results:** Store-map validation passed all 15 checks. All 20 nodes were reachable; 29 positive edges, six section references, and eight tag mappings were valid. Product reference validation passed for zero mappings against zero available product IDs. The evidence validator reported `Component 3 evidence structure is valid; 3 indexed artifact(s).`.
- **Evidence screenshot references:** `C3-MAP-001`, `C3-MAP-002`, and validation artifact `C3-MAP-003`.
- **Next planned action:** Stop at this milestone and await approval before implementing routing algorithms.

### 2026-10-13 23:15 +0530 — Phase 2A Dijkstra shortest-path navigation

- **Development phase:** Phase 2A — Dijkstra shortest-path navigation
- **Objective:** Add deterministic point-to-point routing over the validated Phase 1 store graph and preserve reproducible test, demonstration, and visualization evidence.
- **Work completed:** Implemented a validated read-only graph loader, priority-queue Dijkstra routing with deterministic equal-cost tie-breaking, endpoint exceptions, a CLI demo, 15 automated tests, and a route visualization generator. Generated and visually checked three route figures, saved genuine test/demo logs, registered five evidence records, and documented the methodology and limitations.
- **Files created or modified:** `navigation/store_graph.py`, `navigation/dijkstra.py`, `navigation/dijkstra_demo.py`, `tests/test_dijkstra.py`, `data/store_map/visualize_dijkstra_routes.py`, three `04_navigation_algorithms/screenshots/C3-NAV-*.png` figures, `evaluation/comp3/test_results/dijkstra_tests.txt`, `evaluation/comp3/logs/dijkstra_demo.txt`, `04_navigation_algorithms/notes.md`, `evidence_index.csv`, `tools/register_evidence.py`, and this progress log.
- **Tools and technologies used:** Python 3.14.0 standard library, `heapq`, immutable dataclasses/mappings, `unittest`, JSON, SVG, installed macOS Quick Look renderer, and baseline Git commit `032b26b751c54cf928bee1db603bd1e0f5e5772c`.
- **Implementation decisions and reasons:** Loaded the existing JSON instead of hardcoding nodes; used stored walking distances rather than coordinates; represented adjacency in lexical order; used the full route tuple to break equal-cost ties deterministically; returned an immutable `ShortestPath`; and kept routing independent of visualization and CLI concerns.
- **Problems encountered:** `pytest` was not installed, and dependency installation was out of scope. PNG generation still requires the Phase 1 Quick Look fallback because `sips` cannot decode the generated SVG in this environment.
- **Solutions attempted:** Used standard-library `unittest` for all required cases, documented the missing `pytest` tool in the test record, reused the approved renderer fallback, and visually inspected every generated route image.
- **Test results:** All 15 Dijkstra tests passed with zero failures and errors. Demonstrated routes were checkout 8.69 m (`ENT -> B4 -> B5 -> CHK`), Produce 13.80 m (`ENT -> B4 -> B3 -> B2 -> B1`), and Frozen 6.60 m (`ENT -> B4 -> B5`). All 15 store-map checks passed, the evidence validator accepted eight indexed artifacts, all three PNGs were valid 1700×1120 images, and `git diff --check` reported no issues.
- **Evidence screenshot references:** `C3-NAV-001`, `C3-NAV-002`, `C3-NAV-003`, plus log artifacts `C3-NAV-004` and `C3-NAV-005`.
- **Next planned action:** Stop after Phase 2A and await approval before implementing Held-Karp multi-stop optimization.

### 2026-10-13 23:49 +0530 — Component 3 workspace reorganization checkpoint

- **Development phase:** Repository organization checkpoint before Phase 2B
- **Objective:** Isolate Component 3 under `component3/` without deleting or modifying Component 1, 2, or 4 implementation files.
- **Work completed:** Moved Component 3 backend, store-map data, CNN dataset metadata, ML launch/configuration files, evaluation artifacts, research evidence, navigation UI, motion firmware task, and simulations into one top-level workspace. Kept shared contracts, database seeds, gateway, application shells, and integration tests at repository root. Updated active imports, commands, ignore rules, and shared structure documentation. Preserved earlier execution records with their original paths and wrote new post-reorganization validation output separately.
- **Files created or modified:** `component3/`, root structure documentation, `.gitignore`, `Makefile`, `docs/FOLDER_GUIDE.md`, and `scaffold2.py`. Current demonstration output: `component3/evaluation/logs/dijkstra_demo_reorganization.txt`.
- **Tools and technologies used:** Git read-only audits, Python 3.14.0 standard library, `unittest`, JSON validation, `rg`, and repository validators.
- **Implementation decisions and reasons:** Used `component3/` as the ownership boundary while leaving shared integration resources at root. Updated executable references but retained historical Phase 1 and Phase 2A commands in their original records.
- **Problems encountered:** Moving the graph loader one directory deeper initially caused a duplicated `component3/component3/` lookup. The repository also contained documentation that still described the original layout.
- **Solutions attempted:** Corrected the repository-root calculation, reran all checks, updated active structure documentation, and classified old paths as historical records, current executable references, or integration risks.
- **Test results:** All 15 Dijkstra tests passed; all 15 store-map validation checks passed; the evidence validator accepted eight indexed artifacts; the Colab notebook parsed as JSON; and `git diff --check` reported no errors.
- **Evidence screenshot references:** Existing `C3-MAP-001` through `C3-MAP-003` and `C3-NAV-001` through `C3-NAV-005` were preserved; no new screenshot was created for this structural checkpoint.
- **Next planned action:** Commit the verified reorganization checkpoint, then wait for approval before implementing Held-Karp.
