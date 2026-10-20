# Phase 8B frozen test results

The frozen association model was evaluated once on 299 held-out baskets.

| K | Precision | Recall / HitRate | NDCG | HitRate bootstrap 95% CI | NDCG bootstrap 95% CI |
|---:|---:|---:|---:|---:|---:|
| 1 | .00334 | .00334 | .00334 | [0, .01003] | [0, .01003] |
| 3 | .00446 | .01338 | .00924 | [.00334, .02676] | [.00167, .01936] |
| 5 | .00936 | .04682 | .02320 | [.02341, .07023] | [.01160, .03641] |

Coverage@5 was 0.95588, category diversity@5 was 0.94314, and observed-item violations
were zero. There were no unseen test targets or baskets without a known observed item,
so cold-start accuracy is not measurable—not zero. Test performance is substantially
below validation and is preserved as a negative generalization result. These values do
not describe verified supermarket or customer behavior.
