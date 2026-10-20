# Development provenance

## 2026-10-15 — C3-P7C-FOUNDATION

- **Task:** Architecture audit; shared navigation session; synchronized customer and
  research views; archive, design, evaluation, and handoff documentation.
- **AI coding assistant:** OpenAI Codex (current run).
- **Starting branch/HEAD:** `Comp3_Arun` /
  `4cc31bc7d113088ee2e0234a313889671c485fd3`.
- **Pre-existing work:** Dirty Phase 7B files and artifacts listed by the starting
  `git status`; preserved. Attribution of those uncommitted changes is **UNKNOWN**.
- **Files changed by this milestone:** `dashboard.py`, `spatial_simulation.py`,
  `shared_session.py`, `spatial.js`, `spatial.html`, `customer.html`, `customer.css`,
  `customer.js`, spatial/dashboard tests, research archive, and shared handoff docs.
- **Tests executed:** Focused pytest suite; full relevant pytest suites; JavaScript
  syntax; Python compile; Git whitespace check; browser acceptance where available.
- **Actual outcomes:** See `../03_integrated_system/phase_7c_test_results.json`.
- **Human decisions/approvals:** User specified the milestone scope and prohibited
  commit/push and advanced adaptive behavior. Localhost test permission was approved
  through the execution environment.
- **Known defects:** No defect established by completed tests. Controller leases are
  process-local with a two-second timeout; this is a documented design limitation.
- **Remaining work:** Implement and evaluate the separately designed adaptive layer
  only after milestone review.

## 2026-10-15 — C3-P7D-ADAPTIVE-NAVIGATION

- **Task:** Graph-constrained free walk, exact node/mid-edge route anchors, adaptive
  checkpoint plausibility and safe correction, remaining-route replanning, synchronized
  controls, deterministic A–J evaluation, and evidence.
- **AI coding assistant:** OpenAI Codex (current run).
- **Starting branch/HEAD:** `Comp3_Arun` /
  `4cc31bc7d113088ee2e0234a313889671c485fd3`.
- **Preservation:** Existing Phase 7B/7C dirty work, validated maps, raw POS data, CNN
  images and existing evidence were retained.
- **Evidence:** See `../01_navigation_engine/phase_7d_free_walk_adaptive_localization.md`,
  its deterministic JSON, browser JSON and the Phase 7D test result record.
- **Claim boundary:** Synthetic software and local Chromium only; no physical camera
  or trolley evaluation occurred.
- **Excluded:** Recommendation-model training, store editor, commit and push.

## 2026-10-15 — C3-P7E-DYNAMIC-SHOPPING

- **Task:** Quantity-aware live shopping mutations, atomic current-anchor route
  reoptimization, independent shelf pickup, recommendation acceptance contract,
  synchronized UI, comparative evaluation and evidence.
- **AI coding assistant:** OpenAI Codex (current run).
- **Starting branch/HEAD:** `Comp3_Arun` /
  `4cc31bc7d113088ee2e0234a313889671c485fd3`.
- **Preservation:** Existing dirty Phase 7B–7D work, maps, POS data, CNN assets,
  camera integration and historical evidence were retained.
- **Claim boundary:** Deterministic synthetic software and local Chromium only; no
  physical camera/trolley test and no recommendation training.
- **Evidence:** Phase 7E plan, report, evaluation, browser and test JSON in
  `../01_navigation_engine/`.

## 2026-10-15 — C3-P7F-NAVIGATION-EVALUATION

- **Task:** Reproducible paired baselines, localization decision evaluation, exact
  optimizer/oracle comparison, performance scaling, complete journeys, browser
  regression, camera protocol, validity analysis and final navigation acceptance.
- **AI coding assistant:** OpenAI Codex (current run).
- **Starting branch/HEAD:** `Comp3_Arun` /
  `4cc31bc7d113088ee2e0234a313889671c485fd3`.
- **Preservation:** Existing dirty Phase 7B–7E work, validated maps, raw POS data, CNN
  images and every historical evidence artifact were retained.
- **Claim boundary:** Repeated deterministic synthetic software and local headless
  Chromium; physical camera/trolley testing is PENDING, and no recommendation model
  was trained.
- **Engine changes:** None. The only Python additions are evaluation/browser runners
  and their regression test.
- **Evidence:** See `../01_navigation_engine/phase_7f_navigation_research_summary.md`
  and its linked manifest, raw/aggregate, tables, browser and test artifacts.
