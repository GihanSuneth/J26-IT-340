# Component 3 research archive

This archive indexes research claims, designs, implementation evidence, and
negative results without moving or overwriting the historical artifacts in
`component3/evaluation/` and `component3/docs/research_evidence/`.

## Evidence index

| Area | Maintained artifact | Status | Primary supporting evidence |
| --- | --- | --- | --- |
| Project state | `00_project_overview/phase_7c_milestone.md` | Implemented and verified in software | `03_integrated_system/phase_7c_test_results.json` |
| Development provenance | `00_project_overview/development_provenance.md` | Maintained | Git history, working tree, commands recorded in the file |
| Architecture impact | `01_navigation_engine/architecture_impact.md` | Audited | Source locations and existing historical evaluation artifacts |
| Adaptive design | `01_navigation_engine/adaptive_navigation_design.md` | Designed, not implemented | No experimental result claimed |
| Evaluation protocol | `01_navigation_engine/adaptive_evaluation_framework.md` | Designed, not executed | Metrics and scenario definitions only |
| Phase 7D adaptive navigation | `01_navigation_engine/phase_7d_free_walk_adaptive_localization.md` | Implemented and software-tested | Deterministic A–J and two-view browser artifacts |
| Phase 7E dynamic shopping | `01_navigation_engine/phase_7e_dynamic_shopping_sessions.md` | Implemented and software-tested | Comparative synthetic evaluation and three-view browser artifact |
| Phase 7F navigation evaluation | `01_navigation_engine/phase_7f_navigation_research_summary.md` | Synthetic/software PASS; physical camera PENDING | Manifest, raw/aggregate results, CSV tables, browser and regression records |
| Phase 7G.1 reliability fixes | `01_navigation_engine/phase_7g1_defect_and_fix_report.md` | Software PASS; physical camera PENDING | Automatic shopping mutation, localization-health, dense-tag, API, Chrome and regression records |
| Phase 8A recommendation preparation | `02_recommendation_engine/README.md` | Audited and prepared; no model trained | Inventory, provenance, derived baskets, split, crosswalk, baseline/evaluation code and handoff |
| Phase 8B recommendation evaluation | `02_recommendation_engine/phase_8b_frozen_test_report.md` | Offline evaluation complete; dashboard integration deferred | Fitted artifacts, validation selection, frozen test, per-basket records and limitations |
| Shared session | `03_integrated_system/shared_navigation_session.md` | Implemented and software-tested | HTTP/session regression tests |
| Paper notes | `04_paper_materials/research_notes.md` | Evidence-linked working notes | Links in each section |

## Historical evidence retained in place

- Algorithm and dashboard index: `component3/docs/research_evidence/evidence_index.csv`
- Historical navigation results: `component3/evaluation/navigation_simulation/`
- Position tracking: `component3/evaluation/position_tracking/`
- Route deviation and recalculation: `component3/evaluation/route_deviation/` and
  `component3/evaluation/route_recalculation/`
- AprilTag offline metrics: `component3/evaluation/metrics/apriltag_offline_evaluation.csv`
- Phase 7B camera artifacts: `component3/evaluation/camera_assisted/`

## Indexing protocol

1. Never replace an existing result. Use a new milestone-specific filename.
2. Record the exact command, branch, HEAD, working-tree state, environment, and
   result denominator.
3. Label simulated, offline-image, browser, and physical-camera evidence
   separately. None implies physical trolley movement.
4. Mark missing measurements `NOT MEASURED` and future work `PENDING`.
5. Link claims to source or an actual result artifact; design documents are not
   experimental evidence.
6. Add new historical-style evidence to the existing CSV only after the file
   exists and its validation command passes.

## Phase 7F artifact set

The navigation-engine directory contains the Phase 7F protocol, fixed configuration
manifest, raw trial/timing JSON, aggregate JSON, baseline/localization/performance CSV
tables, complete-journey report, Chromium regression, physical-camera protocol and
blank acceptance template, threats-to-validity report, final research summary, and
test record. Physical camera status is explicitly **PENDING**.

## Phase 8A artifact set

The recommendation-engine directory contains the dataset inventory and checksum,
unknown-provenance assessment, quality audit, basket methodology, catalog crosswalk,
frozen split protocol, baseline rationale, evaluation definitions, reproducibility
manifest, and Phase 8B handoff. Derived baskets and assignments remain separate under
`component3/data/derived/recommendation_phase8a/`. No final recommendation model was
trained and no offline recommendation-quality number was produced.

Phase 8B subsequently fitted four statistical baselines and a regularized linear model,
selected association rules on validation, and evaluated the frozen selection once on
test. The low test quality, unknown provenance and incomplete navigation mapping are
explicitly retained. No prediction was integrated into the customer dashboard.
