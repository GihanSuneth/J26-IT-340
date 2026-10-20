# Phase 8D verification report

## Scope

Phase 8D was verification-only. During the original verification run, it did not retrain or reselect the frozen Phase 8B model, modify production code, store maps, model artifacts, datasets or historical evidence, install dependencies, stage files, commit or push. Phase 8D evidence files were subsequently preserved, and this report and its machine-readable summary received evidence-quality corrections only.

## Automated verification

- Exactly 16 loopback tests were collected.
- The authorized loopback rerun passed 16/16 tests in 8.48 seconds. An earlier sandbox-only attempt was unable to bind loopback sockets and is treated as an environment setup block, not a product-test failure.
- The combined backend and dashboard regression suite passed 295/295 tests in 11.25 seconds, with no failures or skips.
- JavaScript syntax checks passed for `app.js`, `customer.js` and `spatial.js`.
- Evidence validation passed for 121 indexed artifacts.
- `git diff --check -- component3` passed.

The repository does not contain preserved raw terminal transcripts for these commands. Test counts and timings are therefore attributed to the executed Codex verification session and its recorded results, not to a newly reconstructed terminal log. The exact commands executed where available were:

```text
PYTHONDONTWRITEBYTECODE=1 component3/.venv/bin/python -m pytest -p no:cacheprovider component3/simulations/navigation_dashboard/tests/test_simulation.py::NavigationSimulationApiTests component3/simulations/navigation_dashboard/tests/test_spatial_simulation.py::SpatialApiTests --collect-only -q
PYTHONDONTWRITEBYTECODE=1 component3/.venv/bin/python -m pytest -p no:cacheprovider component3/simulations/navigation_dashboard/tests/test_simulation.py::NavigationSimulationApiTests component3/simulations/navigation_dashboard/tests/test_spatial_simulation.py::SpatialApiTests -q
PYTHONDONTWRITEBYTECODE=1 component3/.venv/bin/python -m pytest -p no:cacheprovider component3/backend/comp3_reco_navigation/tests component3/simulations/navigation_dashboard/tests -q
node --check component3/simulations/navigation_dashboard/static/app.js
node --check component3/simulations/navigation_dashboard/static/customer.js
node --check component3/simulations/navigation_dashboard/static/spatial.js
shasum -a 256 component3/ml/models/comp3/recommendation_phase8b/selected_model.json component3/ml/models/comp3/recommendation_phase8b/association_rules.json
PYTHONDONTWRITEBYTECODE=1 python3 -B component3/docs/research_evidence/tools/validate_evidence.py
git diff --check -- component3
```

The existing dashboard was launched for browser acceptance with:

```text
PYTHONDONTWRITEBYTECODE=1 component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard --host 127.0.0.1 --port 8765
```

## Browser acceptance

Google Chrome was exercised at a 1024 x 768 viewport against the existing local dashboard. The customer view had no horizontal or vertical page overflow. The Pasta experimental recommendation was displayed with verified shelf and route information and without a customer-facing score or probability.

The customer and operator views used the same session. A current recommendation submitted with a stale shopping revision returned HTTP 409. Valid acceptance incremented shopping revision 1 to 2 and route revision 1 to 2, added Pasta once, changed remaining route cost from 30 m to 44 m and recorded an accepted event carrying the frozen model identity and checksum. Operator diagnostics synchronized the decision and revisions.

Dismissal of the subsequent Milk recommendation left both revisions at 2, recorded a dismissed event and suppressed the suggestion. The no-eligible fallback was reached through that dismissal, and final customer/operator session and revision state matched. A separate attempted shopping-list replacement returned the expected HTTP 400 because navigation was paused; that guarded request was not the mechanism used to reach the fallback.

The temporary verifier exited nonzero. Its raw result is preserved unchanged with `passed: false`. Its two verifier-level false assertions were `recommendation_displayed`, caused by an incorrect DOM selector even though the heading was visually present, and `no_browser_errors`, caused by expected or cosmetic HTTP console entries rather than a captured JavaScript exception. Chrome reported the intentional stale-revision HTTP 409, the expected HTTP 400 guard against replacing products while navigation was paused, and a cosmetic favicon HTTP 404. No JavaScript exceptions were captured.

### Screenshot path reconciliation

The raw browser JSON remains unchanged and therefore retains its temporary capture paths. The preserved repository copies map as follows:

| Raw temporary path | Repository-relative evidence path |
| --- | --- |
| `/private/tmp/component3-phase8d.TKgf62/recommendation-display.png` | `component3/docs/research_evidence/04_navigation_algorithms/screenshots/C3-PHASE-8D-recommendation-display.png` |
| `/private/tmp/component3-phase8d.TKgf62/recommendation-accepted-customer.png` | `component3/docs/research_evidence/04_navigation_algorithms/screenshots/C3-PHASE-8D-recommendation-accepted-customer.png` |
| `/private/tmp/component3-phase8d.TKgf62/recommendation-accepted-operator.png` | `component3/docs/research_evidence/04_navigation_algorithms/screenshots/C3-PHASE-8D-recommendation-accepted-operator.png` |
| `/private/tmp/component3-phase8d.TKgf62/recommendation-no-eligible.png` | `component3/docs/research_evidence/04_navigation_algorithms/screenshots/C3-PHASE-8D-no-eligible-fallback.png` |

Browser mid-edge acceptance/replanning, voice navigation, physical-camera and AprilTag validation, and real-trolley validation remain pending.

## Frozen model provenance

The frozen model remains `association_rules`, version `comp3-phase8b-20261016-association_rules`. Both `selected_model.json` and `association_rules.json` produced SHA-256 `a1d4c70d26d7b816dc447b7478538e47791541b8dad346ec04391f53e58850cb`, matching the Phase 8C manifest. No model artifact was modified.

The original Phase 8B relevance finding remains primary: validation NDCG@5 was 0.05807 and frozen-test NDCG@5 was 0.02320. Phase 8D functional verification does not change those results or establish recommendation relevance, personalization, customer benefit or commercial value.

## Remaining limitations

- Browser replanning was observed from an entrance-node anchor; browser mid-edge behavior remains pending even though the automated mid-edge regression passed.
- Voice navigation was not exercised.
- Camera hardware, real AprilTags and checkpoint feasibility were not exercised.
- No physical trolley or real-customer trial was performed.
- Evidence was produced with AI assistance and requires independent review.
