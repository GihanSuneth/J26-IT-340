# Phase 8B experimental protocol

Dataset classification remains **UNKNOWN PROVENANCE**. The raw checksum is
`0cd3a4d7d66dec3e7ce6fb1031b095740fb180b9e5fa46ce8bbb9f26f763ae57`.
Phase 8A artifacts verified at 1,991 baskets and 68 normalized-name products, split
chronologically into 1,393 train, 297 validation and 299 test baskets, with two purges.
There is no transaction-ID or item-signature overlap across retained splits and no
hidden target occurs in its observed input.

The two purges are not confirmed duplicate records. Baskets 2194 and 1708 have distinct
IDs/timestamps from matching baskets 2388 and 2866. They are likely legitimate repeated
item sets, retained as exclusions only to preserve the frozen Phase 8A protocol. This
costs two sessions (0.10% of reconstructed baskets).

Every model fits train only and evaluates the same deterministic one-hidden-target
examples. Validation selects the family; test is read only after the preprocessing,
vocabulary, family, hyperparameters, filtering, ranking and seed are frozen. K is
1, 3 and 5. Seed is 3408. Bootstrap intervals use 2,000 paired basket resamples.
