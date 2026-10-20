# Recommendation engine evidence notes

- **Objective:** Audit POS basket data, compare reproducible population-level basket
  completion baselines, preserve weak generalization results, and delimit safe
  navigation-demonstration use.
- **Problem being solved:** Recommend one held-out basket item without leaking later
  transactions or inventing demo-store locations.
- **Methodology:** Chronological train/validation/test separation with cross-split
  signature purging, one deterministic hidden target per basket, validation-only model
  selection, one frozen test, and a post-hoc Phase 8B.1 generalization audit that is
  ineligible for further model selection.
- **Implementation details:** Normalized product names form a 68-item vocabulary. JSON
  model artifacts and per-basket predictions are deterministic and checksum-verified.
- **Tools and libraries:** CPython, NumPy, pytest, standard-library CSV/JSON utilities,
  and the Component 3 navigation graph validator.
- **Inputs and outputs:** The source POS-shaped CSV remains read-only and has SHA-256
  `0cd3a4d7d66dec3e7ce6fb1031b095740fb180b9e5fa46ce8bbb9f26f763ae57`.
  Derived splits, frozen models, predictions, metrics, mapping audits, and reports are
  retained under `component3/data/derived`, `component3/ml/models`, and the recommendation
  research archive.
- **Algorithms or models used:** Global popularity, category popularity, association
  rules, item-item cosine, and a linear basket softmax baseline.
- **Test procedure:** Run the Phase 8B.1 reproduction commands, recommendation tests,
  full backend and dashboard suites, evidence validation, Python compilation, and
  `git diff --check`.
- **Observed results:** The validation-selected association model declined from NDCG@5
  0.05807 to 0.02320 on the frozen test. Item cosine also declined, while the other
  frozen families improved in a post-hoc diagnostic comparison that cannot select a
  replacement. Verified navigation coverage remains 4/68.
- **Limitations:** Dataset provenance is unknown; the dataset is small; only four source
  names have verified navigation destinations; no customer personalization, production,
  physical-trolley, or commercial-impact claim is supported.
- **Screenshot references:** None required; results are tabular and machine-readable.
- **Research report relevance:** See `component3/evaluation/research_archive/02_recommendation_engine/`.
