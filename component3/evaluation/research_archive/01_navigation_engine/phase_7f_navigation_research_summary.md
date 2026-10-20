# Phase 7F navigation research summary and acceptance

## Findings

The matched routing experiment produced 20 trials: 10 improvements and 10 ties, with
all 20 Held–Karp results equal to the independent brute-force optimum. Mean absolute
improvement was 6.0 m across all trials; median percentage improvement was 4.17%. The
largest observed improvement was 30.0 m (68.0 m requested order versus 38.0 m
optimized, 44.12%). Fixed routes after a changed anchor are explicitly marked
non-adaptive/infeasible rather than given fabricated distance.

Across 50 labeled synthetic localization decisions, results were TP=20, TN=30, FP=0,
FN=0. Precision and recall were each 1.0 with denominator 20. The overall correct
decision proportion was 1.0 with Wilson 95% interval 0.9287–1.0. Mean synthetic
position error changed from 0.2195 m before decision to 0.0719 m after; accepted
corrections snap to authored checkpoint coordinates. This is software behavior, not
physical accuracy.

All five complete journey groups passed. They cover planned shopping, independent
free walk, unexpected checkpoint correction, current-anchor replanning, add/remove,
quantity change and multiple explicit pickups, labeled demo recommendation acceptance,
wrong-turn recovery, simulated camera interruption/reconnect, and checkout. Graph-edge
trajectory validation found no shelf crossings or virtual jumps in the recorded paths.

On this Apple arm64 host with Python 3.14.0, each of 35 benchmark cells used 10 warmups
and 100 samples. At six destinations, median/p95 were 0.5231/0.5401 ms for Held–Karp,
1.0668/1.0887 ms for mid-edge anchored optimization, 2.8310/2.8670 ms for dynamic-list
reoptimization, and 1.5858/1.6315 ms for checkpoint-triggered replanning. Dijkstra at
that cell was 0.0145/0.0146 ms. These are host-specific in-process measurements.

## Acceptance matrix

| Criterion | Status | Evidence |
| --- | --- | --- |
| Correct free-walk movement | PASS | Complete journeys and Phase 7D Chromium artifact |
| Valid checkpoint correction | PASS | 20/20 labeled positive synthetic observations |
| Safe invalid-observation rejection | PASS | 30/30 labeled negative synthetic observations |
| Reliable arbitrary-position routing | PASS | node/mid-edge trials; 20/20 oracle matches |
| Dynamic shopping-list support | PASS | journey plus Phase 7E unit/API/browser tests |
| Quantity and pickup consistency | PASS | 4/4 final units; explicit pickup events |
| Successful rerouting | PASS | wrong-turn and unexpected-checkpoint journeys |
| Correct checkout behavior | PASS | completed journeys; premature checkout guard regression |
| Synchronized Customer/Research views | PASS | rerun Phase 7B.2–7E browser acceptance |
| Reproducible evaluation artifacts | PASS | manifest, raw JSON, aggregate JSON, CSV tables, runner tests |
| Preserved regression behavior | PASS | Phase 7F test record |
| Physical AprilTag camera evaluation | PENDING | protocol/template only; no physical run |

The PENDING camera criterion is a blocking limitation for claims of physical detector
or localization performance, but is nonblocking for synthetic/software acceptance.
Other nonblocking limitations are the six-product map, 10-stop exact-optimizer limit,
process-local session, and lack of recommendation training. No defect required an
engine correction during Phase 7F; changes are evaluation and documentation only.

## Evidence map

- Protocol/configuration: `phase_7f_evaluation_protocol.md`,
  `phase_7f_experiment_manifest.json`
- Raw/aggregate: `phase_7f_raw_results.json`,
  `phase_7f_aggregated_results.json`
- Tables: `phase_7f_baseline_comparisons.csv`,
  `phase_7f_localization_results.csv`, `phase_7f_performance_benchmarks.csv`
- Journey, camera, validity: `phase_7f_complete_journey_acceptance.md`,
  `phase_7f_physical_camera_protocol.md`,
  `phase_7f_physical_camera_acceptance_template.csv`,
  `phase_7f_threats_to_validity.md`
- Regression/browser: `phase_7f_test_results.json`; retained Phase 7C–7E browser JSON

Recommendation readiness is contractual only: valid `SIM-P-001`–`SIM-P-006` IDs,
explicit acceptance, shopping revision checks, and current-anchor routing integration
exist. Dataset provenance/reconciliation, leakage-safe splits, training, baselines,
Precision@K, Recall@K, coverage, diversity, cold-start, and synthetic-to-real analysis
remain future work.
