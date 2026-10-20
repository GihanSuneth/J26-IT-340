# Guarded Phase 8C recommendation-demonstration policy

Phase 8C is ready only for a constrained demonstration, not a production or customer-
personalization claim.

1. Label every model suggestion **Experimental recommendation**. Retain the dataset's
   **UNKNOWN PROVENANCE** disclosure in research/operator diagnostics.
2. Remove products already selected, already on the active shopping list, or already
   collected whenever those states make the suggestion redundant.
3. Offer only the four products whose current catalog, shelf, and pickup references
   are verified. Never turn a category-level association into a destination.
4. Require an explicit customer acceptance for each suggestion. Acceptance must call
   the existing atomic shopping-list mutation, then replan from the current estimated
   position using the updated list revision.
5. Rejection must leave the list, route, position estimate, and revision unchanged.
6. Make no unsupported claims about individual preferences, personalization, purchase
   probability, or commercial lift.
7. If filtering produces no eligible recommendation, display no substitute suggestion
   and continue the existing shopping route. The fallback is navigation without a
   recommendation—not an unverified product or location.

Before integration, add contract tests for stale list revisions, simultaneous
acceptance, collected-item filtering, missing graph references, reject/no-mutation,
and replan origin. This phase does not start dashboard integration.
