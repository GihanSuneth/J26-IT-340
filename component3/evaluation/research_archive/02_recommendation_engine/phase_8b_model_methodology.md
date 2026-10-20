# Phase 8B model methodology

- Global popularity ranks training-basket prevalence.
- Category popularity ranks prevalence within categories represented in the observed
  basket, with global popularity fallback. Categories are internally stable by name.
- Association rules require support count 5 and rank the strongest observed-item rule
  by confidence × lift. Support, confidence and lift are stored in the artifact;
  popularity breaks missing/zero-score ties.
- Item-item co-occurrence sums cosine-normalized training-basket co-occurrence.
- The trained comparison is a 68×68 bag-of-items softmax linear ranker with bias,
  full-batch gradient descent, 400 epochs, learning rate 0.3, and L2 selected from
  {0, 0.0001, 0.001, 0.01, 0.1} on validation NDCG@5.

All models share the 68-item training vocabulary, remove observed items, use stable
item-key tie-breaking, honor configurable Top-K, and return deterministic fallbacks for
empty or unseen input. The linear target is never included in its input. The trained
model is justified as a small interpretable comparison, not as evidence that greater
complexity is required; its negative result is retained.
