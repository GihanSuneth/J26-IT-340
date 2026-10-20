# Evidence-linked research notes

## Problem and motivation

The implemented baseline follows a precomputed multi-destination route and corrects
localization at expected mapped checkpoints. The research problem is how to retain
short-route optimization while allowing independent shopper movement, opportunistic
mapped-tag corrections, and destination changes. Current architecture evidence is in
`../01_navigation_engine/architecture_impact.md`.

## Gap and objectives

Candidate literature gaps around adaptive AprilTag localization and supermarket
multi-destination replanning require a separate literature review; novelty is **NOT
CLAIMED**. Objectives are to implement current-position replanning, preserve collected
products, synchronize user/research state, and compare with the fixed-route baseline.

## Architecture and methodology

The existing graph, Dijkstra, Held–Karp, dead reckoning, deviation detector, route
manager, checkpoint correction, and guidance engine remain algorithmic modules. Phase
7C adds a server session boundary and synchronized views. Source and classifications
are listed in the architecture report; the experiment design is in
`../01_navigation_engine/adaptive_evaluation_framework.md`.

## Algorithm rationale

Dijkstra is appropriate for non-negative graph edge costs. Held–Karp supplies an exact
small-set comparison rather than introducing an unvalidated heuristic. AprilTag
observations are discrete mapped constraints over a drifting estimate. Planned
adaptive handling and the partial-edge formulation are documented in
`../01_navigation_engine/adaptive_navigation_design.md`.

## Results and claims

Implemented session properties are supported by
`../03_integrated_system/phase_7c_test_results.json`. Historical synthetic navigation
and browser results remain in `component3/evaluation/navigation_simulation/` and the
existing evidence CSV. No Phase 7C navigation-accuracy experiment, recommendation
result, or physical trolley result is claimed.

## Limitations, validity, and future work

The map/movement are synthetic; camera detections do not constitute trolley movement;
the session is local and in-memory; adaptive behaviors are designed but not built;
literature gap claims remain unverified. Next work should preregister thresholds and
scenarios, implement the position-anchor/observation policy, execute paired seeded
experiments, and only then draw evidence-bounded conclusions.
