# Recommendation engine research archive

**Status: Phase 8B trained/evaluated offline; not integrated into the dashboard.**

Phase 8A found one candidate POS-shaped dataset, reconstructed basket data without
editing it, prepared four transparent baselines and metric functions, reconciled the
source vocabulary to the synthetic demo catalog, and froze a leakage-safe split.
The source remains **provenance unknown**: the repository contains no acquisition,
generator, owner, license, or real-transaction verification record.

## Evidence set

- `dataset_inventory.md` / `dataset_inventory.json`
- `data_provenance_assessment.md`
- `data_quality_report.md` / `data_quality.json`
- `basket_reconstruction_methodology.md` / `basket_reconstruction.json`
- `catalog_reconciliation_report.md` / `catalog_reconciliation_summary.json`
- `split_protocol.md` / `split_protocol.json`
- `baseline_model_selection.md`
- `evaluation_methodology.md`
- `phase_8b_training_handoff.md`
- `phase_8a_test_results.json`
- `preparation_manifest.json`

Derived data is under `component3/data/derived/recommendation_phase8a/`. The raw SHA-256
before and after preparation is
`0cd3a4d7d66dec3e7ce6fb1031b095740fb180b9e5fa46ce8bbb9f26f763ae57`.

## Reproduction

From the repository root with CPython 3.14.0:

```bash
component3/.venv/bin/python -m component3.backend.comp3_reco_navigation.recommendation.prepare_phase8a
component3/.venv/bin/python -m pytest component3/backend/comp3_reco_navigation/tests/test_recommendation_phase8a.py -q
```

Seed `3408` controls deterministic hidden-target selection. The preparation code and
documentation were AI-assisted using OpenAI Codex; all counts are program outputs and
must be independently reviewed before publication. No external citation or provenance
claim was generated.

## Phase 8B evidence

- `phase_8b_experimental_protocol.md` and `phase_8b_dataset_verification.json`
- `phase_8b_model_methodology.md` and `phase_8b_training_configuration.md`
- `phase_8b_validation_comparison.md`, CSV, JSON, per-basket JSONL and SVG
- `phase_8b_model_selection_decision.md` and `phase_8b_model_selection.json`
- `phase_8b_frozen_test_report.md`, JSON/CSV and per-basket JSONL
- `phase_8b_performance_latency.md` and `phase_8b_navigable_candidate_report.md`
- `phase_8b_negative_results.md` and `phase_8b_threats_to_validity.md`
- `phase_8b_reproduction.md`, experiment manifest and Phase 8C readiness
- `phase_8b_test_results.json`

The selected model is an association-rule recommender chosen by validation NDCG@5.
Frozen-test NDCG@5 is 0.0232 and HitRate@5 is 0.0468 on 299 baskets. These weak results,
the unknown provenance, and 4/68 navigation mapping coverage prevent a deployment claim.

## Phase 8B.1 evidence

- `phase_8b1_generalization_audit.md`, diagnostics JSON, distribution CSV, and
  post-hoc frozen-baseline comparison CSV/JSON
- `phase_8b1_evaluation_integrity.json` and `phase_8b1_manifest.json`
- `phase_8b1_catalog_mapping_and_extension.md`, 68-row audit CSV, and summary JSON
- `phase_8b1_phase8c_guarded_policy.md`
- `phase_8b1_reproduction.md` and `phase_8b1_test_results.json`

Phase 8B.1 preserves the original weak frozen-test result. It finds that degradation
is shared by the association and item-cosine models, not all model families, and does
not use post-hoc test comparisons for a new selection. Verified navigation coverage
remains 4/68; dashboard integration has not started.
