# Phase 7F threats to validity

## Internal validity

The runner uses seeded sensor streams and fixed configuration, but most route costs
are deterministic properties of one graph; repeating seeds does not create independent
stores or shoppers. Runtime measurements share one process and host and may be affected
by scheduling, cache state, thermal state, and interpreter overhead. Dynamic and
checkpoint benchmarks intentionally include fresh simulation construction, so they
are end-to-end operation timings and should not be compared directly with pure
algorithm timings.

## Construct validity

Graph distance is not human walking effort. Simulated traveled distance follows the
planned graph exactly and excludes hesitation, aisle congestion, reaching, and turning
cost. A correct accept/reject decision under authored scenarios measures validation
logic, not camera recognition quality. Synthetic zero-error checkpoint correction is
an expected snap-to-known-coordinate result and is not physical localization accuracy.
The five journey groups demonstrate coverage and invariants, not a user-study success
rate.

## External validity

The demonstration map has 30 nodes, 37 edges, six products, and three mapped
checkpoints. Products do not provide a natural shared-shelf pair. Results do not
generalize automatically to larger, multi-floor, crowded, changing, or inaccurately
surveyed supermarkets. The exact optimizer is capped at 10 unique stops and scales
exponentially. The shared session is in-memory, process-local, unauthenticated, and not
distributed.

Physical camera behavior under blur, occlusion, lighting, distance, device drivers,
and Continuity Camera reconnects remains unmeasured. No camera calibration, trolley
mount, physical path, or end-to-end detection latency was evaluated. Recommendation
data, training, quality, fairness, privacy, and real acceptance behavior are also
unmeasured.

## Conclusion validity

The 50 localization decisions were balanced by authored scenario type, not sampled
from a deployment distribution. Precision and recall of 1.0 have denominator 20 and
a correct-decision Wilson 95% interval of 0.9287–1.0; they must not be reported without
those denominators or as statistical proof. The route set deliberately includes both
favorable and tie cases, but it is not an exhaustive sample of all behavioral demand.
No significance test or novelty claim is made.
