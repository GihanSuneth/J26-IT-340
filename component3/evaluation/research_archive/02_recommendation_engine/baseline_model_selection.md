# Baseline and model selection rationale

Prepared implementations are global basket popularity, category-conditioned
popularity, pairwise association rules, and cosine-normalized item-item co-occurrence.
They count item presence per basket rather than allowing quantity to dominate, exclude
observed items, and use deterministic tie-breaking.

Suitability findings:

- Global/category popularity: supported by basket and category fields.
- Association rules: supported by 1,991 multi-item baskets and 68 stable name keys.
- Item-item collaborative signal: supported as co-occurrence, not user-based CF.
- Basket-conditioned learned model: feasible as a small regularized bag-of-items
  multi-label linear model, but it must beat transparent baselines on validation.
- Sequential/personalized model: not justified; user identity semantics and provenance
  are unverified, and within-basket line order is unavailable.

Phase 8B should start with baselines, then optionally compare a regularized linear
basket-completion model. A neural architecture is not justified by the current volume
or evidence. No baseline was fit to the full dataset and no final model was trained in
Phase 8A.
