# Phase 8C integrated evaluation report

The demonstration-selected input was Bananas + Bread. Selection enumerated the 16
subsets of the four verified mapped products using only live frozen-model inference;
scores and artifacts were unchanged. The model naturally ranked Pasta first
(`SIM-P-004`, `DEMO-SHELF-04`, pickup `N2_1`).

Acceptance changed shopping revision 0→1 and route revision 0→1 exactly once. Remaining
optimized route cost changed 30.0→44.0 m, a 14.0 m detour. The journey reached Pasta,
presented normal pickup controls, recorded collection, continued to checkout and
completed. Duplicate delivery produced zero duplicate mutations.

Across 16 subsets, 14 exposed an actionable suggestion (87.5%). Empty input and the
list containing all four mapped products did not. Every exposed suggestion was
navigable. This recorded run measured mean inference 0.097 ms, filtering 0.361 ms,
total response 0.470 ms, and acceptance-to-route-update 0.272 ms. These are local
software timings.

Dismissal preserved revision and suppressed repetition. Stale acceptance was rejected,
model-unavailable navigation remained usable, mid-edge acceptance retained an edge
anchor, camera state did not alter recommendation state, and multiple views read the
same server state. See `phase_8c_raw_scenario_results.json` and
`phase_8c_aggregated_metrics.json`.

The original negative result remains primary: association validation NDCG@5 0.05807
and frozen-test NDCG@5 0.02320. Functional integration does not establish relevance,
personalization, satisfaction, conversion or commercial value.
