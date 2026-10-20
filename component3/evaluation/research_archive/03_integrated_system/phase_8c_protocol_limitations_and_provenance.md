# Phase 8C protocol, limitations and provenance

The runner evaluates 16 mapped-product subsets plus accept, dismiss, duplicate, stale,
unavailable-model, no-eligible and complete-journey cases. Functional navigation metrics
remain separate from Phase 8B offline relevance metrics.

Threats include unknown POS provenance/license, weak frozen-test relevance, only 4/68
verified mappings, a six-product synthetic store, process-local state, timing noise,
and no real customer or physical-trolley trial. Availability is specific to deliberately
enumerated mapped subsets and is not representative of retail sessions.

Playwright is not installed, so new automated Phase 8C browser interaction and Phase 8C
screenshots are **PENDING**. Existing API, DOM/static contract, JavaScript syntax and
dashboard regressions remain required. Physical camera acceptance is also **PENDING**.

OpenAI Codex assisted with implementation, tests, evaluation and documentation. Outputs
require independent review. No external data origin, preference, benefit, or production
claim was inferred.

## Reproduction and launch

```bash
component3/.venv/bin/python -m component3.simulations.navigation_dashboard.phase8c_evaluation
component3/.venv/bin/python -m pytest component3/backend/comp3_reco_navigation/tests component3/simulations/navigation_dashboard/tests -q
python3 -B component3/docs/research_evidence/tools/validate_evidence.py
node --check component3/simulations/navigation_dashboard/static/customer.js
node --check component3/simulations/navigation_dashboard/static/spatial.js
component3/.venv/bin/python -m compileall -q component3
git diff --check -- component3
```

One-command launch:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard
```

Open `http://127.0.0.1:8765/customer` and `http://127.0.0.1:8765/`.
