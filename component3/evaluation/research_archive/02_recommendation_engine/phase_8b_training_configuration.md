# Phase 8B training configuration

Runtime: CPython 3.14.0, NumPy 2.5.4, seed 3408. Baselines used 1,393 complete training
baskets; the linear ranker used the 1,393 frozen observed/target training examples.
Measured fit times on this local run were 0.630 ms global popularity, 1.674 ms category
popularity, 7.521 ms association rules, 6.955 ms item-item cosine, and 176.169 ms for
the selected L2=0.1 linear candidate.

The association artifact contains 3,502 directed rules at minimum support count 5.
The linear model has 4,692 parameters. Full configuration, candidate tuning results,
versions and times are saved in `training_configuration.json`, `training_metadata.json`,
and `phase_8b_linear_tuning.csv`. Times are environment-specific observations, not
portable performance guarantees.
