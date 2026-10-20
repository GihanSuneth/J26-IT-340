# Phase 8B.1 reproduction and AI-assisted provenance

From the repository root, using the component virtual environment:

```bash
component3/.venv/bin/python -m component3.backend.comp3_reco_navigation.recommendation.phase8b1_audit
component3/.venv/bin/python -m pytest component3/backend/comp3_reco_navigation/tests/test_recommendation_phase8a.py component3/backend/comp3_reco_navigation/tests/test_recommendation_phase8b.py component3/backend/comp3_reco_navigation/tests/test_recommendation_phase8b1.py -q
```

The audit reads the frozen Phase 8A split, Phase 8B predictions, and Phase 8B model
JSON. It does not fit, tune, select, or overwrite a model. Seed `3408` is used only to
reconstruct the previously frozen hidden targets. `phase_8b1_manifest.json` records
the evidence checksums and immutable-model assertions.

OpenAI Codex assisted with audit code, tests, calculations, and documentation. All
generated findings were derived from repository artifacts and must be independently
reviewed before publication. No external source, dataset origin, license, customer
identity, or real-world personalization claim was inferred.
