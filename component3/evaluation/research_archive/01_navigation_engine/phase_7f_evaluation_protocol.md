# Phase 7F navigation research evaluation protocol

**Status:** executed for deterministic synthetic, software, and local-browser
experiments; physical-camera experiment **PENDING**.

## Research questions and hypotheses

- **RQ1:** How reliably does checkpoint-assisted navigation correct simulated
  estimates under controlled observation errors? **H1:** valid expected and
  spatially plausible unexpected mapped observations will be accepted and reduce
  synthetic position error, while invalid observations will not alter the estimate.
- **RQ2:** How effectively does adaptive navigation recover from voluntary deviations
  and unexpected mapped checkpoints? **H2:** graph-valid deviations and accepted
  unexpected checkpoints will produce a current-anchor route revision without an
  entrance reset or shopping-state loss.
- **RQ3:** Under which shopping-list conditions does optimization improve on requested
  order? **H3:** Held–Karp will never exceed the matched naive-order cost and will
  improve some, but not all, permutations.
- **RQ4:** How reliably do dynamic mutations preserve quantities, checkpoint history,
  and consistency? **H4:** valid atomic operations preserve invariants; stale or
  duplicate commands are rejected or deduplicated without partial mutation.
- **RQ5:** What is the computational cost as destination count increases? **H5:**
  Dijkstra remains small on this fixed graph, while exact Held–Karp cost increases
  with destination count because its complexity is `O(n²2ⁿ)`.

These are testable engineering hypotheses. This experiment reports descriptive
outcomes and Wilson intervals; it makes no statistical-significance claim.

## Design

The manifest fixes five seeds, map and schema identifiers, six product IDs, three
checkpoint IDs, 0.25 s timestep, 1.6 m/s speed, host details, and timing repetitions.
Twenty paired route trials use four starting anchors (two node, two mid-edge) and five
requested-order permutations. Each comparison holds graph, demand, checkout, anchor,
and movement cost constant. Baseline A is marked non-adaptive/infeasible after an
anchor or list change rather than assigned invented distance. Baseline B follows the
requested order from the current anchor. The proposed route uses exact anchored
Held–Karp optimization. All instances are independently checked by exhaustive
permutation because the demo has at most six destinations.

Fifty localization trials cross ten scenario types with five seeds: expected,
unexpected plausible, duplicate, unknown, stale, incorrect map, implausible, missed,
delayed, and drifted observations. A priori labels define whether acceptance is the
correct decision. Simulated truth scores error only; neither the processor nor the
route planner receives it as hidden input. Camera disconnect/reconnect is an explicit
software failure event, not a detector callback presented as physical evidence.

Performance cells use 10 warmups and 100 measurements with `perf_counter_ns`, reported
in milliseconds as minimum, median, nearest-rank p95, and maximum for destination
counts 0–6. Operations are Dijkstra, Held–Karp, mid-edge anchoring, dynamic-list
reoptimization, and checkpoint-triggered replanning.

## Reproduction

From repository root:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.phase7f_evaluation
component3/.venv/bin/python -m pytest -q component3/simulations/navigation_dashboard/tests/test_phase7f_evaluation.py
```

Configuration is in `phase_7f_experiment_manifest.json`; trial-level inputs and raw
timings are in `phase_7f_raw_results.json`. CSV tables and aggregate JSON are derived
by the same runner. Re-running overwrites only Phase 7F generated files; it does not
alter historical Phase 7B–7E evidence or validated maps.
