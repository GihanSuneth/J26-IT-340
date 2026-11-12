# Component 3 Project Status and Integration Report

**Project:** IoT Smart Shopping Trolley  
**Component:** Component 3 — Recommendation, Navigation, and CNN Aisle Recognition  
**Prepared:** 13 November 2026  
**Working branch:** `Comp3_Arun`  
**Working HEAD:** `5dd3f4f` (`Jupyter Updated`)  
**Shared baseline reviewed:** `develop` at `0b4340f`  

## 1. Executive summary

Component 3 has a functioning, offline-first research implementation for supermarket
route planning, simulated trolley localization, deviation detection, automatic route
recalculation, guarded product recommendations, and browser-based demonstrations. The
work includes algorithms, API/session logic, customer and operator interfaces, automated
tests, reproducible synthetic evaluations, research evidence, and local demo launchers.

The committed `Comp3_Arun` branch is 14 commits ahead of `develop`. In addition, the
working tree contains an active, uncommitted dashboard improvement set. That work splits
the demonstration into independent Navigation and Recommendation modes, improves reset
and camera behaviour, adds a recommendation display policy, adds standalone workflows,
and adds tests and demo scripts. These changes are implemented locally but are not yet a
committed or pushed project milestone.

The current system is suitable for software demonstration and controlled synthetic
evaluation. It is not yet validated as a production or physical-trolley system. Physical
camera accuracy, encoder/IMU accuracy, real-store trials, recommendation-data licensing,
and broader recommendation coverage remain open.

Following the branch-isolation cleanup, the complete working tree now has no differences
from `develop` outside `component3/`. Shared project files remain present at their
`develop` versions, while all effective Component 3 changes are contained under the
component-owned folder. The cleanup is staged but not committed.

## 2. Repository and branch position

The repository uses `develop` as the common project baseline. The requested branch audit
was performed by temporarily preserving the working tree, switching to `develop`, and
then returning to `Comp3_Arun`. All pre-existing local changes were restored.

| Branch | Position relative to `develop` | Main scope observed |
|---|---:|---|
| `Comp3_Arun` | 14 commits ahead | Navigation, recommendation research, Component 3 dashboard and frontend integration |
| `origin/Comp1_Nawodya` | 2 commits ahead | Object/model evaluation, root frontend and backend entry point |
| `origin/Comp2_Gihan` | 9 commits ahead | Product recognition, ESP32 camera/IR, shopping API and separate shopping UI |
| `origin/Comp4_Ovini` | 12 commits ahead | Authentication, billing, catalogue, recommendations and trolley-display UI |
| `origin/test` | 7 commits ahead | Earlier integration of Component 2 work |

The local `Comp1_Nawodya`, `Comp2_Gihan`, `Comp4_Ovini`, and `test` references are behind
their corresponding remote references. Integration planning should therefore use the
remote tips after an explicit fetch/update, not the stale local branch tips.

## 3. Work completed in Component 3

### 3.1 Store map and routing algorithms

- A validated metric store graph and AprilTag checkpoint layout are maintained inside
  the Component 3 workspace.
- Dijkstra shortest-path routing is implemented and tested.
- Held–Karp exact multi-stop ordering is implemented and tested, with checkout retained
  as the final destination.
- Route anchoring supports node and mid-edge positions.
- Route calculation preserves remaining shopping stops and uses deterministic tie
  breaking.
- Exact optimization is intentionally capped at 10 unique stops because Held–Karp has
  exponential complexity.

### 3.2 Localization and checkpoint work

- Offline AprilTag detection and generated test/card assets are present.
- Simulated wheel/IMU dead reckoning tracks position between checkpoints.
- Mapped checkpoint observations correct estimated position in the synthetic workflow.
- Free-walk movement, junction selection, pause/resume, and adaptive checkpoint handling
  are implemented in the spatial simulator.
- Camera-scanner support and dashboard camera controls exist, but physical accuracy is
  not yet established.

### 3.3 Deviation detection and automatic rerouting

- The deviation detector measures the nearest route-segment distance and progress.
- Hysteresis and consecutive-sample confirmation reduce single-sample false alarms.
- Confirmed deviation can trigger automatic route recalculation.
- Failed localization or route calculation preserves the active route instead of
  corrupting the session.
- A reroute is latched during one deviation episode and is eligible again only after
  recovery.

The recorded Phase 5A synthetic evaluation produced 56 observations: precision 0.90,
recall 0.642857, and F1 0.75. The Phase 5B synthetic evaluation recorded six successful
and two intentionally failed reroute attempts, no false or missed triggers, and complete
preservation of remaining stops and checkout. These are controlled simulation results,
not physical-sensor results.

### 3.4 Dynamic shopping session

- Requested, collected, and remaining quantities are held in one authoritative shopping
  session.
- Shopping and route revisions protect commands against stale updates.
- Customer mutations are validated before atomic commit.
- Accepted recommendations reuse the same shopping mutation and route re-optimization
  path rather than bypassing navigation logic.
- Duplicate commands, stale revisions, dismissal, fallback, and model-unavailable cases
  have explicit handling.

### 3.5 Recommendation research pipeline

- Phase 8A audits 10,000 POS-shaped rows and reconstructs 1,991 normalized-name baskets.
- A chronological, leakage-aware train/validation/test split is recorded.
- Catalogue reconciliation explicitly distinguishes mapped, category-only, and unmapped
  products.
- Phase 8B evaluates four statistical baselines and a regularized NumPy ranker.
- Association rules were selected using validation NDCG@5 and frozen as reloadable JSON
  artifacts.
- The held-out result is NDCG@5 = 0.0232 and HitRate@5 = 0.0468. This weak result is
  preserved honestly and is not represented as customer-value or production evidence.
- The live recommendation service verifies the frozen artifact checksum, filters for
  navigation eligibility, and does not load held-out labels.
- Recommendation acceptance and dismissal require explicit customer action.

Only four of 68 demo catalogue items are currently navigation-eligible. Recommendation
data provenance and licensing are unresolved, so the model remains an experimental
demonstration.

### 3.6 CNN aisle-recognition foundation

- CNN training and inference entry points, configuration, Colab assets, and a six-class
  aisle image workspace are present.
- This is a foundation rather than a completed physical aisle-recognition validation.
  No production performance claim should be made until trained weights and a controlled
  physical-camera evaluation are documented.

### 3.7 Testing and research evidence

- Unit and integration tests cover routing, AprilTags, tracking, deviation, route
  management, dashboard APIs, shopping sessions, recommendation integration, and
  standalone workflow behaviour.
- The preserved Phase 8D run reports 295 backend/dashboard regression tests passing and
  16 authorized loopback API tests passing.
- The current working tree was re-verified on 13 November 2026: all 335 Component 3
  backend and dashboard tests passed. Shell launcher syntax, five dashboard JavaScript
  files, and `git diff --check` also passed.
- The evidence archive contains manifests, raw/aggregate JSON, CSV tables, screenshots,
  protocols, threats-to-validity notes, and reproducibility records.
- The Phase 7F evaluation reports 20/20 exact matches to the brute-force route oracle,
  5/5 completed synthetic journeys, and 50/50 correct labeled localization decisions.
  Those localization observations are synthetic and must not be interpreted as physical
  accuracy.

## 4. Dashboard brief

The dashboard is a local, loopback-only browser application served by Python. It uses
bundled HTML, CSS, and JavaScript and does not require a cloud dashboard service.

### 4.1 Navigation demonstration

The Navigation mode provides synchronized customer and operator views. It supports:

- wishlist and navigation-basket selection;
- validation of verified shelf and pickup-node mappings;
- multi-stop route calculation and checkout completion;
- turn-by-turn guidance and checkpoint feedback;
- simulated truth and estimated-position visualization for research use;
- pause/resume, free walk, junction choice, pickup confirmation, deviation detection,
  and automatic rerouting;
- camera preview/control and diagnostic export where the local environment supports it;
- a reset action scoped to the Navigation demonstration.

The current launcher is `component3/run/start_navigation_demo.sh`. It starts the
Navigation mode on `127.0.0.1:8765` and presents customer and operator navigation from
one authoritative session.

### 4.2 Recommendation demonstration

The Recommendation mode is a separate process and session. It supports:

- adding/removing simulated confirmed-cart products;
- a configurable minimum-distinct-item gate;
- checksum-verified frozen-model inference;
- backend ranking, eligibility, mapping and detour diagnostics;
- at most one active passive customer suggestion;
- explicit accept, dismiss, or save-for-later behaviour;
- suppression of dismissed and previously offered suggestions according to policy;
- a reset action scoped only to the Recommendation demonstration.

The current launcher is `component3/run/start_recommendation_demo.sh`. It uses
`127.0.0.1:8766/recommendations`, so both demonstrations can run simultaneously without
sharing or corrupting state.

### 4.3 Dashboard implementation status

The original dashboard, customer view, operator/research view, spatial map, APIs, and
Phase 8C recommendation integration are committed. The newest split-mode UI, standalone
workflow adapters, recommendation policy, evidence builder, mode navigation, launchers,
and related tests are present in the working tree but uncommitted as of this report.

## 5. Recorded evaluation results

| Evaluation | Recorded result | Interpretation |
|---|---|---|
| Phase 7F route comparison | 20 trials; 20 oracle matches; mean 6.0 m absolute improvement | Exact routing implementation matched the small-instance oracle |
| Phase 7F localization decisions | TP 20, TN 30, FP 0, FN 0 | Correct on the fixed synthetic labeled set only |
| Phase 7F journeys | 5 of 5 passed | Complete software journeys succeeded |
| Phase 8B recommendation | Test NDCG@5 0.0232; HitRate@5 0.0468 | Weak experimental ranking; not deployment evidence |
| Phase 8C integration | 16 scenarios; 0 duplicate mutation rate | Functional integration passed controlled scenarios |
| Phase 8C latency | 0.470492 ms mean end-to-end in recorded run | Local synthetic timing, not production latency |
| Phase 8D regression | 295 tests passed; 0 failed | Historical preserved verification record |
| Phase 8D browser acceptance | Partial with successful core scenarios | Selector/favicon issues remained; core state transitions were observed |

## 6. Branch-integration and merge-conflict analysis

No newer commit exists on the current `develop` branch beyond the base already contained
in `Comp3_Arun`, so merging current `develop` into Component 3 would add nothing. The
risk described below applies to the old committed branch tip. The current staged
isolation cleanup neutralizes Component 3's side of these shared-path conflicts once it
is committed, because every path outside `component3/` now matches `develop` exactly.

### 6.1 Component 1

`origin/Comp1_Nawodya` independently changes `frontend/README.md`, which Component 3 also
changed. This requires a manual content reconciliation. Most Component 1 model files and
its root frontend are otherwise separate from `component3/`.

### 6.2 Component 2 and `test`

`origin/Comp2_Gihan` and `origin/test` independently change `.gitignore`, which Component
3 also changed. The patterns should be combined intentionally. Component 2 otherwise
uses separate `product_recognition`, `shopping_api`, and `frontend/shopping-ui` paths,
so source-code overlap is comparatively low.

Several Component 2 files are zero-byte placeholders despite having functional-looking
names. They should be reviewed before integration rather than assumed complete.

### 6.3 Component 4

Component 4 has the highest direct conflict risk. Both branches independently add or
change:

- `frontend/trolley-display/index.html`;
- `frontend/trolley-display/package-lock.json`;
- `frontend/trolley-display/package.json`;
- `frontend/trolley-display/src/app/App.jsx`;
- `frontend/trolley-display/src/app/routes.jsx`;
- `frontend/trolley-display/src/main.jsx`.

Component 3's structure-simplification commit also removed shared/root files while
Component 4 continued modifying some of them, including Component 4 backend paths. A
wholesale merge can therefore produce add/add, content, and modify/delete decisions.
The correct resolution is to preserve Component 4 authentication/billing pages and add
Component 3 navigation as explicit routes/features, then regenerate one package lock
from the reconciled package manifest.

### 6.4 Recommended integration sequence

1. Commit or otherwise checkpoint the current Component 3 working tree before merging.
2. Update remote references and create an integration branch from the latest `develop`.
3. Integrate Component 1 and Component 2 first because their overlap is small.
4. Integrate Component 4 separately and manually reconcile the shared trolley display.
5. Bring Component 3 in last as component-owned paths plus selected frontend changes;
   do not blindly accept the repository-wide deletions from the simplification commit.
6. Rebuild dependency lock files after resolving manifests.
7. Run all component test suites plus an end-to-end contract test for cart events,
   recommendations, accepted stops, route revisions, authentication, and billing.
8. Merge the tested integration branch into `develop`; do not merge all feature branches
   directly into one another.

## 7. Cleanup and naming completed with this report

- Removed `component3/evaluation/.gitkeep` because the directory contains real evidence.
- Removed `component3/data/datasets/comp3_aisle_images/.gitkeep` because the directory
  already contains its README and dataset content.
- Renamed the generic dashboard launch/check files to:
  - `component3/run/start_comp3_dashboard.command`
  - `component3/run/start_comp3_dashboard.sh`
  - `component3/run/check_comp3_dashboard.sh`
- Updated launcher references to use the new names.
- Regenerated the static recommendation evidence disclosure after verification exposed
  an invalid trailing comma; the generated JSON and its source-consistency tests now
  pass.
- Moved `ml/colab/comp3_recommendation_experiments.ipynb` to
  `component3/ml/training/notebooks/comp3_recommendation_experiments.ipynb`.
- Reorganized the Component 3 backend into `backend/navigation/`,
  `backend/recommendation/`, and `backend/shared/`, including subsystem-specific tests.
- Reorganized browser assets and JSX into `frontend/navigation/`,
  `frontend/recommendation/`, and `frontend/shared/`.
- Grouped CNN code, notebooks, and configurations under `ml/training/`, and moved the
  frozen Phase 8B artifacts to `ml/models/recommendation/phase8b/`.
- Restored every path outside `component3/` to the exact `develop` version. This keeps
  the complete repository available without making unrelated files part of Component 3's
  effective branch diff.
- Removed untracked macOS `.DS_Store` metadata files.
- Removed the obsolete root-level Component 3 copies from `backend`, `data`, `docs`,
  `evaluation`, `firmware`, `frontend`, `ml`, and `simulations`. The top-level
  `component3/` directory is now the single authoritative Component 3 workspace.
- Removed the minimal Dockerfile, one-byte `.gitkeep` placeholders, empty directories,
  and generated Python/pytest caches. Container and placeholder files can be recreated
  later if deployment or empty-directory tracking becomes necessary.
- Retained the `component3.simulations.navigation_dashboard` Python package name because
  it is already component-namespaced; renaming it would create widespread import and
  evidence-reference churn without improving isolation.

## 8. Remaining work

### Required before branch integration

- Review, stage, and commit the current uncommitted Component 3 work in coherent commits.
- Decide whether generated multi-page AprilTag PDFs belong in Git or in release/storage
  artifacts.
- Run a browser smoke test after the working-tree changes are finalized; the complete
  automated suite currently passes (335 tests).
- Reconcile the trolley-display frontend with Component 4 on a dedicated integration
  branch.

### Required before physical or production claims

- Perform real-camera AprilTag accuracy and failure-mode testing.
- Integrate and calibrate physical encoder/IMU inputs and test on the trolley.
- Conduct real-store deviation, rerouting, usability, and safety trials.
- Resolve recommendation dataset provenance and licensing.
- Increase verified product-to-shelf coverage beyond four navigation-eligible products.
- Re-evaluate or replace the weak recommendation model on appropriate, licensed data.
- Add authentication, persistence, distributed controller coordination, monitoring, and
  production security controls.

## 9. Overall completion assessment

The Component 3 research prototype and software demonstration are substantially
implemented. Core navigation algorithms, synthetic localization, rerouting, session
coordination, guarded recommendation integration, dashboards, tests, and evidence are
complete at the software-research level. The newest dual-demo dashboard refinements are
implemented locally but await a clean commit and fresh full verification. Hardware
validation, production readiness, broader catalogue mapping, and final cross-component
integration are not complete.

