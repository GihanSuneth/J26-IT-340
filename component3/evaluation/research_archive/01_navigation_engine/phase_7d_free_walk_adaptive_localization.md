# Phase 7D — free walk and adaptive checkpoint localization

## Research question

Can the existing graph navigation simulator support independent lane-constrained
movement and safely use an unexpected mapped AprilTag observation to correct its
estimate and replan, without using simulated truth as an online oracle?

## Previous limitation and source audit

Phase 7C shared one deterministic session across the customer and research views,
but movement followed a planned route. The checkpoint processor rejected every tag
other than the next planned checkpoint, and the Phase 5B edge projection routed from
one endpoint without charging the distance already remaining on the edge. The Phase
7D implementation reuses the validated graph, Dijkstra, Held–Karp, dead reckoner,
checkpoint mapping, camera callback boundary, guidance engine and session command
contract. It does not replace those algorithms or alter the research map.

## Proposed and implemented method

Free walk exposes only graph-adjacent choices. A fixed 0.25 s command step moves
truth along the selected edge, advances the noisy estimator separately, and updates
uncertainty. Movement stops at each junction until another adjacent edge is selected.
Session GETs remain pure; the explicit movement action gives its issuing view the
single playback lease, so observer polling cannot advance the shared clock.

An immutable route anchor is either a node or a position on edge `(u,v)`. An edge
anchor records distance `d_u` and `d_v` to both endpoints, direction, projection and
route revision. For remaining destinations `D`, exact unbounded cost is:

`min(d_u + HK(u,D), d_v + HK(v,D))`.

When direction forbids reversal, the minimization is restricted to the forward
endpoint. `HK` is the existing Held–Karp optimizer and its legs use existing
Dijkstra paths. Therefore partial-edge distance is explicit rather than silently
dropped.

Adaptive checkpoint validation first applies source/camera, map-version, timestamp,
known-marker and duplicate gates. Expected mapped observations retain the existing
acceptance behavior. An unexpected mapped marker is accepted only in adaptive mode
when graph distance from the last confirmed checkpoint and current estimated anchor
is within the distance reachable from elapsed simulation time, configured maximum
speed, tolerance and current uncertainty. Simulated truth is absent from this policy
context. Truth is read only afterward to calculate evaluation error.

An accepted observation corrects the estimator to the mapped checkpoint, reduces
uncertainty, appends observation and localization events, preserves truth and
checkpoint history, and replans the remaining uncollected products plus checkout.
It stores the previous route, reason, exact anchor costs, computation time and an
incremented route revision. Rejections retain estimate, confirmed checkpoint and
route.

## Deterministic scenarios and actual results

The seed-6042 software evaluation used the synthetic demo map, 0.25 s steps, baseline
speed 0.8 m/s and free-walk speed 1.6 m/s. One trial was run for each required
scenario A–J. The original two-product route completed in 38.75 simulated seconds.
Free walk followed 19.0 m of valid edges to `N1_4`. CP202 was then accepted while
CP201 was expected because its 30.0 m graph distance was within the calculated
32.127 m reachability limit.

The accepted correction was 0.572 m; synthetic truth-referenced localization error
changed from 0.572 m to 0.000 m. Ground truth did not move during the scan. The
remaining route was recomputed in approximately 0.587 ms in the recorded run and
revision increased by one. Route cost was 54.0 m before and after, so this trial
shows no route-cost improvement. The shopping list and collected state were
preserved.

Across four measured observations, 1/4 was accepted and 3/4 rejected. The unknown
tag, duplicate tag and spatially implausible mapped tag were all rejected; the
implausible rejection preserved estimate and confirmed checkpoint. Camera loss and
resume used a direct software callback and returned to navigating. Separate focused
tests cover stale, map mismatch, invalid source and unavailable-camera classes.

Exact records and units are in `phase_7d_deterministic_evaluation.json`. Browser
evidence in `phase_7d_browser_acceptance.json` covers two synchronized views,
mid-edge stop and navigation request, route revision, and zero console/page errors.

## Baseline comparison and failures

- Baseline: planned-route completion succeeded for 1/1 deterministic run.
- Adaptive observation: 1/1 plausible off-route marker was accepted and replanned.
- Negative observations: 3/3 evaluation negatives were rejected as intended.
- Route-cost change: 0.0 m; the scenario did not produce a shorter route.
- Physical camera and physical trolley trials: **NOT MEASURED**.

## Threats to validity

All movement, sensor drift, checkpoint locations and truth are synthetic. One seeded
trial per scenario establishes deterministic behavior, not a population accuracy or
latency distribution. The measured replan time is local synchronous wall-clock time
and varies by host. The plausibility thresholds are engineering assumptions, not
calibrated human or trolley motion limits. Direct callback interruption does not
exercise camera hardware, lighting, blur or detector accuracy.

## Reproducibility

From the repository root:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.phase7d_evaluation
python3 -B -m component3.simulations.navigation_dashboard.phase7d_browser_acceptance
component3/.venv/bin/python -m pytest component3/backend/comp3_reco_navigation/tests component3/simulations/navigation_dashboard/tests -q
python3 -m compileall -q component3/backend/comp3_reco_navigation component3/simulations/navigation_dashboard
node --check component3/simulations/navigation_dashboard/static/spatial.js
node --check component3/simulations/navigation_dashboard/static/customer.js
git diff --check -- component3
```

## Git and AI provenance

Work began on branch `Comp3_Arun` at
`4cc31bc7d113088ee2e0234a313889671c485fd3`, with existing uncommitted Phase 7B/7C
changes preserved. OpenAI Codex implemented and tested Phase 7D under the user's
specified scope. No commit or push was performed. Recommendation training and the
future store editor were not implemented.
