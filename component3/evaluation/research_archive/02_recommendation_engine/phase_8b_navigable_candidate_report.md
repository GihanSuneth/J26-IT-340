# Phase 8B navigable-candidate coverage

The actual crosswalk confirms exactly Banana, Bread, Milk and Pasta as product-level,
route-backed normalized-name mappings. No shelf location was invented. They represent
4/68 candidates (5.88%); incomplete mapping removes 94.12% of the model vocabulary from
the navigation-eligible scope.

All validation and test sessions could receive at least one navigable candidate after
ranking/filtering. Across all 299 test sessions, navigable-only HitRate@5 was 0.07023
because only 21 targets were navigable. On those 21 targets, HitRate@5 is 1.0, but this
is mechanically saturated: K=5 exceeds the four-item navigable catalog and the hidden
target is necessarily one of the returned candidates. It is not evidence of high model
quality. At K=1 the eligible-target subset HitRate was 0.14286.

Navigable metrics are reported separately and must never replace the 68-item full-catalog
results. Catalog coverage@5 within the four-item scope was 1.0, while the candidate-level
coverage loss remains 94.12%.
