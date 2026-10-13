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
