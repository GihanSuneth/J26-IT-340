# Phase 8B validation comparison

All values use the same 297 validation baskets. With one target, Recall@K equals
HitRate@K, while Precision@K is `hits/K`, so a successful result at K=5 contributes
1.0 recall but only 0.2 precision.

| Model | P@1 | HR@3 | P@5 | HR@5 | NDCG@5 | Coverage@5 | Diversity@5 | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Global popularity | .0034 | .0303 | .0114 | .0572 | .0293 | .1176 | 1.0000 | .0145 |
| Category popularity | .0101 | .0303 | .0101 | .0505 | .0298 | .8824 | .6825 | .0225 |
| Association rules | .0202 | .0640 | .0189 | .0943 | **.0581** | .9706 | .9471 | .0380 |
| Item-item cosine | .0202 | .0539 | .0182 | .0909 | .0542 | 1.0000 | .9455 | .4735 |
| Linear softmax | .0202 | .0370 | .0121 | .0606 | .0392 | .1324 | .9973 | .0249 |

Every model produced zero observed-item violations. Association rules lead the frozen
criterion, but paired bootstrap intervals for its NDCG@5 difference overlap zero versus
item-item and linear. No significance claim is made. Exact @1/@3/@5 values and intervals
are in the JSON/CSV artifacts; `phase_8b_validation_ndcg5.svg` is the paper-ready figure.
