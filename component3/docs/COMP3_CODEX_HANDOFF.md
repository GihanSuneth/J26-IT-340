# Component 3 Codex handoff

## Repository state at Phase 8B

- Branch: `Comp3_Arun`
- Starting HEAD: `4cc31bc7d113088ee2e0234a313889671c485fd3`
- Working tree: intentionally dirty with preserved Phase 7B work plus Phase 7C.
- Phase 7D work is also uncommitted and confined to `component3/`.
- Phase 7E work remains uncommitted and is confined to `component3/`.
- Phase 7F evaluation/evidence work remains uncommitted and is confined to `component3/`.
- Phase 7G/7G.1 dashboard work remains uncommitted and is preserved.
- Phase 8A recommendation audit/preparation remains uncommitted and is confined to
  `component3/`; the ignored raw POS file was not modified.
- Phase 8B model/evaluation work remains uncommitted and confined to `component3/`.
  No model prediction was connected to a dashboard.
- Commit/push: not performed.
- Validated research map, raw POS data, CNN images, and trained weights: not modified.

## Resume commands

From the repository root:

```bash
git branch --show-current
git rev-parse HEAD
git status --short --branch
component3/.venv/bin/python -m pytest component3/backend/comp3_reco_navigation/tests component3/simulations/navigation_dashboard/tests -q
component3/.venv/bin/python -m component3.backend.comp3_reco_navigation.recommendation.prepare_phase8a
component3/.venv/bin/python -m component3.backend.comp3_reco_navigation.recommendation.phase8b_experiment
node --check component3/simulations/navigation_dashboard/static/app.js
node --check component3/simulations/navigation_dashboard/static/spatial.js
node --check component3/simulations/navigation_dashboard/static/customer.js
git diff --check -- component3
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard
```

Open `http://127.0.0.1:8765/customer` for the Customer View,
`http://127.0.0.1:8765/` for Research Execution, and
`http://127.0.0.1:8765/research` for the preserved validated graph dashboard.

## Latest verified evidence

- Phase 7C archive: `component3/evaluation/research_archive/README.md`
- Test record:
  `component3/evaluation/research_archive/03_integrated_system/phase_7c_test_results.json`
- Architecture impact and adaptive design:
  `component3/evaluation/research_archive/01_navigation_engine/`
- Prior evidence: `component3/docs/research_evidence/evidence_index.csv`
- Phase 7D method/results:
  `component3/evaluation/research_archive/01_navigation_engine/phase_7d_free_walk_adaptive_localization.md`
- Phase 7D deterministic and browser JSON: same navigation-engine directory.
- Phase 7E implementation plan, research report, evaluation, browser acceptance and
  test record: `component3/evaluation/research_archive/01_navigation_engine/`.
- Phase 7F manifest, raw/aggregate data, CSV tables, journey/browser/camera reports,
  validity analysis, research summary and test record: the same directory.
- Phase 8A inventory, provenance, quality, basket, catalog, split, model/evaluation
  rationale and Phase 8B handoff:
  `component3/evaluation/research_archive/02_recommendation_engine/`.
- Phase 8A derived baskets, crosswalk and split assignments:
  `component3/data/derived/recommendation_phase8a/`.
- Phase 8B fitted/reloadable JSON models:
  `component3/ml/models/comp3/recommendation_phase8b/`.
- Phase 8B protocol, validation, selection, frozen test, per-basket records, figure,
  negative results and validity analysis: recommendation-engine archive above.

## Implementation notes

Both maintained views use `/api/session/state` and `/api/session/control`. Dynamic
shopping commands require `expected_shopping_revision`; preserve command/client IDs
and GET purity. Quantity state is authoritative in `shopping_session.py`; legacy
product-ID fields are derived compatibility views. Do not make camera callbacks change
simulated truth or bypass the common lock.

Recommendation source `product_id` is unusable as a SKU: all 900 IDs map to multiple
names. Use the Phase 8A normalized-name keys only for experiments. Category-only and
unmapped catalog entries are not navigation-eligible. The enriched output contract
requires mapping/shelf/route eligibility metadata, while explicit acceptance continues
through the existing atomic mutation and current-anchor route reoptimization path.
The offline selected artifact is association rules with support count 5 and
confidence×lift ranking. Its frozen-test NDCG@5 is 0.0232; do not hide this weak result
or infer customer value. Phase 8C invokes it only through the checksum-verified live
service and guarded eligibility filter.

## Outstanding limitations and next action

The session is in-memory, process-local, and unauthenticated. Controller coordination
is not distributed. Phase 7F supplies repeated synthetic decisions and paired route
trials but physical camera/trolley accuracy remains PENDING. The catalog is small and
has no natural shared-shelf product pair; exact optimization is capped at 10 unique
stops. Recommendation data provenance and licensing remain unresolved. Only four of 68
items are navigation-eligible, and navigable K=5 is exhaustive rather than meaningful.
Phase 8C integration is complete as an experimental demonstration; further phases
require an explicit request.

## Phase 8C update

Phase 8C was explicitly authorized and is now implemented as an experimental
demonstration. `recommendation/live_service.py` loads the frozen association artifact
once after checksum verification and never loads held-out labels. Current shopping state
drives deterministic inference; only four verified catalog mappings can be offered.
Accept/dismiss, stale revision, duplicate command, mid-edge replan, failure fallback and
operator diagnostics are covered by Phase 8C tests and evidence in
`evaluation/research_archive/03_integrated_system/`. Do not promote the model to
production or extend mappings without new evidence. No commit or push was performed.
