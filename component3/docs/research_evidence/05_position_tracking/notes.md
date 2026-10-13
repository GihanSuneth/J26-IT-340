# Phase 4A — Simulated trolley position tracking

## Objective and scope

Evaluate planar dead-reckoning drift and simulated AprilTag checkpoint
correction on the existing Component 3 store graph. Physical AprilTags, wheel
encoders, and an IMU were not available. All reported observations are from a
deterministic software simulation; no physical localization accuracy is
claimed.

## Coordinates and route

The existing store map defines x east, y north, metres, and AprilTag
orientations counter-clockwise from +x. A fixed Held-Karp route starts at
`ENT`, visits `B1`, `B3`, and `B5`, and ends at `CHK`. Dijkstra-selected graph
nodes define the route topology. Simulated motion between each consecutive
node follows the straight line between their stored coordinates, so the
continuous simulation path uses coordinate geometry rather than edge-weight
travel distance. Initial position is the map coordinate for `ENT`, and initial
heading is assumed to be east.

## Simulation assumptions

Recorded in `evaluation/position_tracking/simulation_config.json`:

- Fixed Python pseudo-random seed: `3404`.
- Sampling interval: `0.25 s`; nominal speed: `0.8 m/s`.
- Turn duration: `0.5 s`; one stationary sample at each route node.
- Encoder noise: independent Gaussian standard deviation `0.003 m` per sample.
- Encoder scale bias: `0.002` of each signed displacement.
- IMU yaw noise: independent Gaussian standard deviation `0.25 degrees` per
  sample; constant yaw-rate bias: `0.15 degrees/s`.
- These are illustrative simulation settings, not sourced from or fitted to
  physical sensors. Simulated stationary samples also receive sensor noise and
  bias.

One generated ground-truth trajectory is paired with two aligned sensor-only
streams: ideal measurements and seeded noisy measurements. Scenarios B
(noisy/no corrections) and C (same noisy stream/checkpoint corrections) use
exactly the same truth and noisy measurement objects.

## Estimator and checkpoint model

The estimator accepts only timestamped wheel displacement and IMU yaw delta;
it does not read ground-truth coordinates. For each sample, with prior
heading `theta`, signed wheel displacement `ds`, and IMU yaw increment `dtheta`:

```text
theta_mid = normalize(theta + dtheta / 2)
x_next = x + ds * cos(theta_mid)
y_next = y + ds * sin(theta_mid)
theta_next = normalize(theta + dtheta)
```

Heading is normalized to `[-pi, pi)`. Timestamps must be finite, nonnegative,
and strictly increasing. Zero displacement permits a stationary period or an
in-place turn.

Checkpoint events are emitted only when a simulated route arrival is at a node
with an entry in the existing `apriltag_layout.json`. The observation is
explicitly typed as a *simulated* checkpoint event, looks up the existing tag
ID-to-node mapping, and snaps estimated x/y to the checkpoint's stored
coordinates. Unknown IDs raise an error. Heading is not corrected. This is an
ideal map-coordinate correction, not a simulated camera image detection or
measurement of real detection accuracy.

## Evaluation method and actual results

Position error is Euclidean distance from the corresponding ground-truth
sample. The 182-sample route contains nine mapped checkpoint observations.
Mean, RMSE, maximum, and final position error include the initial sample.
Checkpoint before/after values are measured at each correction instant.

| Scenario | Mean (m) | RMSE (m) | Maximum (m) | Final (m) | Mean checkpoint error before → after (m) |
|---|---:|---:|---:|---:|---:|
| A — ideal, zero noise and bias | 0.000000 | 0.000000 | 0.000000 | 0.000000 | Not applicable |
| B — seeded noisy sensors, no corrections | 0.292980 | 0.489878 | 1.313433 | 1.313433 | Not applicable |
| C — same seeded noisy sensors with corrections | 0.081926 | 0.138332 | 0.482411 | 0.000000 | 0.194205 → 0.000000 |

The exact recorded values are in `evaluation/position_tracking/metrics.csv`.
Zero post-correction error is expected because the simulation snaps x/y to
the exact mapped coordinates. It is not a real-world accuracy result.

## Reproducible artifacts

- `evaluation/position_tracking/simulation_config.json` — simulation
  assumptions and route selection.
- `evaluation/position_tracking/trajectory.csv` — aligned truth, sensor
  readings, three estimates/errors, and checkpoint correction measurements.
- `evaluation/position_tracking/metrics.csv` — machine-readable scenario
  metrics.
- `evaluation/position_tracking/reproducibility.log` — seed, route, counts,
  results, and scope limitations.
- `evaluation/test_results/position_tracking_tests.txt` — actual unittest
  execution output.
- `screenshots/C3-POS-001_ground_truth_vs_dead_reckoning.png` —
  ground truth and noisy dead reckoning.
- `screenshots/C3-POS-002_checkpoint_corrected_trajectory.png` — corrected
  and uncorrected trajectories with map/checkpoints.
- `screenshots/C3-POS-003_position_error_comparison.png` — error versus time
  for all three scenarios and checkpoint times.

The three PNG figures are generated from the same in-memory evaluation used
for the CSV outputs. SVG source figures are saved alongside them.

## Automated tests

The standard-library `unittest` suite contains 16 passing tests for straight
motion, turns, stationary and zero-distance updates, heading normalization,
invalid readings/timestamps, deterministic replay, unknown and known
checkpoints, correction/no-correction behavior, noisy samples, ideal error,
and estimator isolation from ground truth.

## Limitations and future hardware integration

This simulation uses a simplified planar unicycle-like midpoint model,
straight coordinate segments, a known starting pose, independent Gaussian
sample noise, constant additive/scale biases, perfect graph-node arrival
events, and exact checkpoint map coordinates. It excludes wheel geometry,
slip, asynchronous sensor timing, mounting/calibration uncertainty, tag pose
estimation, camera false positives/missed detections, and sensor fusion
filtering. Future hardware work must calibrate the encoder and IMU, estimate
camera/tag pose and uncertainty, handle real timestamp synchronization, and
evaluate against independently measured ground truth before claiming physical
performance.

## Phase 5A — route-deviation detection

### Objective and scope

Evaluate deterministic deviation detection against a planned shopping route
using the existing simulated store graph. This work does not implement
automatic rerouting and does not claim physical position accuracy.

### Geometry and detector

The planned route is the ordered node sequence returned by the existing
Held-Karp/Dijkstra route implementation. `deviation.py` uses only each graph
node's stored `x_m`/`y_m` coordinates. Consecutive nodes form straight
segments. For estimate `p`, segment start `a`, and direction `v = b - a`, the
projection parameter is

```text
t = clamp(dot(p - a, v) / dot(v, v), 0, 1)
q = a + t * v
distance = norm(p - q)
```

Zero-length coordinate segments project to their shared endpoint. A route with
one valid node is treated as a point; multi-node routes must use graph edges.
The minimum distance across all segments is reported with the nearest segment,
projected point, and cumulative coordinate-polyline progress. Threshold
boundaries use strict `distance > threshold` semantics.

The default enter threshold follows the project rule
`epsilon(d) = 0.3 + 0.02*d` metres, with `d` measured along the coordinate
polyline. Callers can instead configure a fixed metre-valued threshold.
Deviation entry requires three consecutive samples above the enter threshold.
The exit threshold is `max(0, enter_threshold - 0.15 m)`; recovery requires two
consecutive samples at or below it. These configurable thresholds/counts are
simulation assumptions, not empirical or hardware-calibrated values.

### Reproducible scenarios and evaluation

Run from the repository root:

```bash
component3/.venv/bin/python -B -m \
  component3.backend.comp3_reco_navigation.navigation.deviation_simulation
component3/.venv/bin/python -B -m unittest -v \
  component3.backend.comp3_reco_navigation.tests.test_deviation
```

The evaluator constructs the `ENT -> B4 -> B3 -> B2 -> B1 -> B2 -> B3 ->
B4 -> B5 -> CHK` route using the actual Held-Karp and Dijkstra code. Seed
`5041` generates eight controlled scenarios: planned-route following, small
position noise, a brief one-sample deviation, sustained off-route movement,
return to the route, a corner, an endpoint, and invalid position data. The
simulation uses 56 observations (54 valid and two invalid), a 0.5 s sample
interval, 0.04 m Gaussian estimate noise, and a known 1.5 m synthetic
off-route offset. The labeled off-route truth is assigned by the scenario
generator, independently from detector output. Only the estimated x/y position
is passed to the detector. Invalid coordinates are rejected and excluded from
the confusion matrix.

Precision, recall, and F1 are set to zero when their denominator is zero.
Detection delay is the elapsed samples/time from the beginning of a labeled
off-route episode to the confirmed transition. A brief episode shorter than
the configured confirmation count is recorded as missed. A false alarm event
counts an entry transition on an on-route label; false-positive samples can
also occur while a prior, correctly triggered alarm is waiting for recovery.

### Actual results

| Measure | Result |
| --- | ---: |
| Scenarios | 8 |
| Observations | 56 total; 54 valid; 2 invalid |
| True positives | 9 |
| False positives | 1 |
| True negatives | 39 |
| False negatives | 5 |
| Precision | 0.900000 |
| Recall | 0.642857 |
| F1 | 0.750000 |
| Mean delay for detected off-route episodes | 2 samples; 1.0 s |
| Off-route episodes detected / missed | 2 / 1 |
| False alarm entry events | 0 |
| Automated deviation tests | 22 passed; 0 failed; 0 skipped |

The single-sample deviation is intentionally missed by the three-sample entry
confirmation rule. The one false-positive sample occurs during recovery from a
confirmed deviation; it is not a new false alarm event. Results are synthetic
and deterministic, not a measured physical trolley performance estimate.
The per-scenario confusion counts and computed aggregate are recorded in
`evaluation/route_deviation/metrics.csv`; all sample labels, estimates,
distances, thresholds, and detector state are in
`evaluation/route_deviation/observations.csv`.

Final regression validation also passed: store-map validation (15 checks),
Dijkstra (15 tests), Held-Karp (18 tests), AprilTag (18 tests, zero skipped),
dead reckoning (16 tests), route deviation (22 tests), and research evidence
validation (28 indexed artifacts). `git diff --check` reported no whitespace
errors.

### Evidence and outputs

- `evaluation/route_deviation/simulation_config.json` records the seed,
  threshold, hysteresis, route, sample interval, and simulation assumptions.
- `evaluation/route_deviation/observations.csv` records all 56 labeled samples,
  separated ground truth and estimates, detector outcomes, and invalid-input
  exclusions.
- `evaluation/route_deviation/metrics.csv` contains per-scenario and overall
  confusion metrics, delays, missed episodes, and alarm counts.
- `evaluation/route_deviation/reproducibility.log` records the actual aggregate.
- `evaluation/test_results/route_deviation_tests.txt` contains actual
  `unittest` output.
- `screenshots/C3-POS-006_route_deviation_scenarios.png` shows the planned
  route, labeled estimated points, and detected deviation transitions.
- `screenshots/C3-POS-007_distance_hysteresis.png` shows distance and
  progress-dependent enter/exit thresholds over the concatenated samples.
- Companion SVG evidence sheets are saved alongside both PNGs.

### Limitations and future connection to rerouting

The simulation uses a synthetic fixed perpendicular offset and small seeded
coordinate noise, straight-line graph-coordinate segments, known route and
labels, and an ideal estimate input. It does not model map uncertainty,
real-world localization error distributions, missed samples, sensor latency,
or physical store geometry. The route manager remains unchanged. A later
rerouting phase may consume a confirmed deviation event and recompute a path,
but should first define route-update UX, safety constraints, and recovery
behavior; none are implemented here.
