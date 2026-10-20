# Phase 8B reproduction and development provenance

From the repository root:

```bash
component3/.venv/bin/python -m component3.backend.comp3_reco_navigation.recommendation.phase8b_experiment
component3/.venv/bin/python -m pytest component3/backend/comp3_reco_navigation/tests/test_recommendation_phase8a.py component3/backend/comp3_reco_navigation/tests/test_recommendation_phase8b.py -q
```

The experiment verifies inputs before fitting, writes safe JSON model artifacts, saves
per-basket validation/test predictions, and records checksums in
`phase_8b_experiment_manifest.json`. Results use CPython 3.14.0, NumPy 2.5.4 and seed
3408. Dashboard integration is explicitly false.

OpenAI Codex assisted code, tests, experiment execution and documentation. Counts and
metrics are computed artifacts rather than language-model estimates. No citation,
dataset origin or behavioral interpretation was invented. Independent code/results
review remains required before publication.
