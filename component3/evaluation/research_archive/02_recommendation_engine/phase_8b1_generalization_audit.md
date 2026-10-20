# Phase 8B.1 generalization audit

## Scope and guardrail

This is a retrospective diagnostic of already-frozen Phase 8B artifacts. No model was
refit, no hyperparameter or model family was selected from test performance, and the
original association-rule result remains the primary Phase 8B finding: validation
NDCG@5 `0.0580748554`, frozen-test NDCG@5 `0.0232011834`, and frozen-test HitRate@5
`0.0468227425`. The dataset continues to be classified **UNKNOWN PROVENANCE**.

## Descriptive findings

- Basket size is effectively stable: means are 4.874 (train), 4.882 (validation),
  and 4.866 (test), with median 5 and range 2–7 in every split.
- All 68 training-vocabulary items occur in validation and test. There are no unseen
  validation/test targets and no new or disappearing catalog items.
- Candidate availability is stable (mean 64.118 validation versus 64.134 test).
- Pair novelty is extremely low. Unseen observed-to-target pair rates are 0.260% in
  validation and 0.087% in test; test therefore is not harder because it contains
  more unseen pairs.
- Association rules return at least one rule candidate in every validation and test
  session, so fallback-only frequency is 0% in both periods. The hidden target has
  some rule support in 97.31% of validation cases and 97.66% of test cases.
- Whole-basket item-frequency drift is modest (validation-to-test total variation
  0.1153; Jensen–Shannon divergence 0.01545 bits). The hidden-target distribution
  changes much more (total variation 0.2826; Jensen–Shannon divergence 0.10939 bits).
  Tissue rises from 0.34% to 3.34% of hidden targets, while biscuits, notebook,
  potato, jeans, milk, saree, and spices each decline materially.
- Association top-5 hits fall from 28/297 to 14/299. Test misses concentrate in
  tissue (10), onion (9), diapers (8), and several targets with seven misses.

The complete 68-product comparison is in `phase_8b1_distribution_comparison.csv`;
machine-readable drift, coverage, candidate, pair, hit, and miss diagnostics are in
`phase_8b1_generalization_diagnostics.json`.

## Frozen-model comparison

| Frozen model | Validation NDCG@5 | Post-hoc test NDCG@5 | Change |
|---|---:|---:|---:|
| Association rules | 0.05807 | 0.02320 | -60.0% |
| Item-item cosine | 0.05416 | 0.02674 | -50.6% |
| Global popularity | 0.02931 | 0.06002 | +104.8% |
| Category popularity | 0.02978 | 0.05823 | +95.5% |
| Linear softmax | 0.03921 | 0.05001 | +27.6% |

The decline is shared by the two co-occurrence model families but is not shared by
all baselines. These post-hoc test values are diagnostic only and must not replace the
validation-selected association model or be used to claim that another frozen model
was selected correctly.

## Interpretation: description versus causation

The evidence is consistent with temporally unstable pair ranking and a changed mix of
hidden targets. It rules out several simple explanations: vocabulary cold start,
larger baskets, candidate exhaustion, rule fallback, and excess unseen pairs. It does
not establish that target-distribution drift caused the score decline. The hidden
target itself is deterministically sampled from each basket, sample sizes are modest,
and unknown source provenance prevents conclusions about genuine customer behavior.

If model development continues, the frozen 2024 test must remain historical evidence.
Create a new chronological development window, tune only within that window using
rolling-origin validation, register the protocol before evaluation, and reserve a
later, untouched future period as the sole new final test. Do not choose a Phase 8C
model using the post-hoc table above.

## Evaluation-integrity result

Chronology, unique transaction assignment, split signatures, deterministic target
construction, observed-target exclusion, 68-item training vocabulary, metric
denominators, category-diversity execution, artifact hashes, and stored predictions
all rechecked successfully. All 1,485 validation predictions and 299 original test
predictions reproduce exactly. The two purged records have distinct IDs and times and
are likely legitimate repeated purchases; excluding them slightly reduces the sample
and alters prevalence while enforcing conservative signature isolation. They remain
excluded solely to preserve the original split, and are not represented as proven
duplicate source records.
