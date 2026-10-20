# Leakage-safe split protocol

Baskets are ordered by `(timestamp, basket_id)`, then divided 70/15/15. A later basket
whose normalized item-set signature appeared in an earlier partition is purged. This
produces 1,393 train, 297 validation, 299 test, and 2 purged duplicate baskets.

- Train ends inclusively at 2024-09-08 07:29.
- Validation ends inclusively at 2024-11-05 22:41.
- Test ends at 2024-12-31 21:33.
- Deterministic hidden-target seed: `3408`.

For basket completion, one distinct item is hidden using
`SHA-256("3408:<basket_id>") modulo basket size`; all other items are observed. The
hidden item is absent from model input. Fit item counts, rules, vocabulary, and model
parameters on train only. Use validation only for selection, and run test once after
freezing the selected approach. `split_assignments.csv` records every observed/hidden
case. The timestamp is internally consistent, but real-world chronology remains
unverified because provenance is unknown.
