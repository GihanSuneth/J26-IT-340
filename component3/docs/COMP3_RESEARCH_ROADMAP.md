# Component 3 research roadmap

## Research objective

Evaluate adaptive AprilTag-assisted localization and dynamic multi-destination route
optimization against the existing fixed planned-route baseline, then develop and
evaluate a separate recommendation engine before integrated-system evaluation.

## Completed navigation milestone — Phase 7F/7G.1

Executed fixed-seed paired routing, labeled localization, complete-journey, scaling,
oracle, and local Chromium evaluation. Synthetic/software navigation acceptance passes;
physical AprilTag camera acceptance remains PENDING with a separate manual protocol.
Raw, aggregate and table results are under
`component3/evaluation/research_archive/01_navigation_engine/`.

## Remaining adaptive-navigation research

1. Execute the frozen physical-camera protocol and retain raw scanner logs.
2. Calibrate motion and plausibility thresholds with ethically approved physical trials.
3. Evaluate shared-shelf and larger-catalog fixtures beyond the six-product demo.
4. Evaluate camera detector behavior under lighting, blur and occlusion.
5. Replace the process-local session if deployment requires persistence or distribution.

Acceptance should cover all scenarios in the adaptive evaluation framework, with no
regression in existing tests and no claim of physical accuracy.

## Completed milestone — Phase 8A recommendation preparation

Audited the single local POS-shaped CSV, classified provenance/license as unknown,
reconstructed 1,991 baskets over 68 normalized names, and froze a 1,393/297/299
chronological train/validation/test design after purging two later duplicate signatures.
Prepared global/category popularity, association and item-item baselines plus metric
functions. Four source names have conservative navigable name mappings; there are zero
verified SKU matches. No model was trained and no quality metric was reported.

## Current milestone — Phase 8B controlled experiments

Fitted four baselines and a regularized bag-of-items linear model on train only.
Association rules were selected at validation NDCG@5 0.0581; frozen test NDCG@5 was
0.0232 and HitRate@5 0.0468. The negative generalization result, unknown provenance,
two over-conservative signature purges and 4/68 navigable mapping coverage are retained.
No dashboard integration occurred.

## Next milestone — Phase 8C guarded integration

Proceed only after accepting the weak test quality and provenance risk. Use the safe
offline inference artifact, show only explicitly mapped products, retain customer
confirmation, and send acceptance through the existing atomic mutation/reoptimization
path. Define display/score policy and integration acceptance tests before exposing any
prediction. Do not call the current model production-ready.

## Final integration and paper support

Evaluate recommendation acceptance plus adaptive rerouting; maintain source-linked
results, failures, threats, reproducibility, and provenance. Literature gap and novelty
claims remain pending a verified literature review.

## Completed milestone — Phase 8C guarded integration

The checksum-verified association artifact now serves revision-bound experimental
suggestions for the four mapped products. Acceptance uses atomic mutation and current-
anchor reoptimization; dismissal is non-mutating. Functional evaluation covers
availability, failures, idempotency and a complete synthetic journey. Browser automation
and physical camera acceptance remain pending; the model is not production-ready.
