# Evaluation methodology

For each validation/test basket, rank candidates against the one hidden target at
K ∈ {1, 3, 5}. Report macro means over eligible baskets:

- Precision@K = relevant recommended items / K.
- Recall@K = relevant recommended items / hidden relevant items.
- HitRate@K = fraction of baskets with at least one hit.
- NDCG@K = discounted gain divided by ideal discounted gain.
- Catalog coverage = unique eligible items recommended / eligible catalog items.
- Diversity = fraction of unordered pairs in a list from different categories.
- Already-in-basket rate/count = recommended items present in observed input; expected 0.
- Cold start = separate results for targets unseen in train and baskets with no known item.
- Latency = count, mean, p50, and p95 wall-clock inference milliseconds after warm-up,
  with hardware/software recorded.

Report denominators and uncertainty by bootstrap resampling baskets. Do not tune on
test. Recommendation relevance is the primary offline result. Route detour cost and
route distance are separately reported secondary system measures and must never be
folded into or described as relevance accuracy.
