# Phase 8B negative results

- Frozen test NDCG@5 (0.0232) was much lower than validation (0.0581).
- The trained linear ranker did not beat association rules or item-item cosine; its best
  validation NDCG@5 was 0.0392 at L2=0.1.
- Category conditioning reduced HitRate@5 relative to global popularity despite much
  higher catalog coverage.
- Association and item-item paired differences are uncertain; no statistical-significance
  claim is supported.
- Cold-start performance cannot be measured because all validation/test targets and
  observed baskets use training-vocabulary items.
- Phase 8A signature purging likely removed two legitimate repeat transactions.
- Only four products are navigation-eligible, making navigable K=5 exhaustive and
  unsuitable as evidence of ranking quality.

These results favor retaining the transparent association model as a research artifact,
not deploying it as a customer-facing predictor.
