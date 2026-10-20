# Basket reconstruction methodology

`preprocess.py` validates the exact ten-column schema, parses timestamp, quantity and
price, and groups lines by `order_id`. Each retained order must contain one source user
ID and one timestamp. The modeling key is `name:<normalized-product-name>` because the
source product ID is unstable. Within an order, repeated normalized names are merged,
quantities summed, and the original source IDs plus line count retained for traceability.

No category is filtered. Invalid/missing/nonpositive rows, inconsistent orders,
ambiguous normalized names, and baskets with fewer than two distinct items have explicit
reject paths; none occurred in this file. Source user IDs are used only for within-order
consistency and are not copied to derived JSONL.

Result: 10,000 lines → 1,991 baskets, 68 model items, 2–7 distinct items per basket
(mean 4.8724), with 299 repeated lines aggregated. The reproducible output is
`component3/data/derived/recommendation_phase8a/cleaned_baskets.jsonl`.
