# Adaptive navigation evaluation framework

**Status: protocol design; experiments PENDING.**

## Comparison

- **Baseline:** current fixed planned-route navigation with expected-route checkpoint
  sequence and no active-journey list mutation.
- **Proposed:** free-walk, plausible mapped-checkpoint correction, current-anchor
  replanning, and dynamic remaining-destination optimization.

Use identical map version, initial products, sensor configuration, and seed per paired
trial. Minimum sample size is **PENDING** and must be chosen before execution; report
both trial count and event denominators.

## Scenarios

Original-route following; alternate shelf; unexpected mapped checkpoint; product add;
product remove; wrong turn; duplicate/unknown/implausible tags; camera interruption;
repeated route revisions; and two synchronized dashboard viewers. Parameterize seeds,
walking choices, tag stream, mutation time, and interruption duration in versioned
scenario JSON.

## Metrics

- Completion rate `N_complete / N_trials` (proportion with numerator/denominator).
- Route distance `Σ d_i` (metres), including partial-edge distance.
- Remaining route cost (metres) immediately before and after each revision.
- Replanning time `t_publish - t_request` (milliseconds, monotonic clock).
- Checkpoint acceptance rate `N_accepted / N_observed`; rejection counts by reason.
- Localization error `e_t = sqrt((x_hat_t-x_t)^2+(y_hat_t-y_t)^2)` (metres), reported
  as mean, RMSE, median, 95th percentile, and maximum over paired samples.
- Route revisions (count per trial), product completion `N_confirmed/N_requested`,
  and camera detection latency (milliseconds) only when timestamps are genuinely
  measured from the scanner pipeline.
- Multi-view clock integrity: unique accepted step commands versus simulated time;
  expected equality `Δt = 0.25 * Σ accepted_count`.

## Analysis and validity

Report paired baseline/proposed differences with confidence intervals selected before
examining results. Separate deterministic software-test rates from navigation outcome
rates. Synthetic truth permits localization-error measurement but does not establish
real-world accuracy. Camera latency, lighting robustness, shopper behavior, and map
survey error remain external-validity threats until physically evaluated.
