# Adaptive localization and dynamic rerouting design

**Status: DESIGNED BUT NOT IMPLEMENTED.** This document is not evidence that the
behaviors exist or perform accurately.

## State and commands

Add explicit `MovementCommand`, `CheckpointCandidate`, `RouteAnchor`, and
`ShoppingListCommand` records to the server session. All include a command/event ID,
session ID, simulation timestamp, source, and validation outcome. Free-walk commands
may select only an adjacent graph edge and a bounded distance along it.

## Free walk and continuous observations

The simulated true pose advances along a selected adjacent edge independently of the
planned route. Dead reckoning remains measurement-driven. Camera detections enter the
existing observation processor continuously; they never move simulated ground truth.
For each observation, resolve the mapped tag, reject unknown/wrong-map/duplicate or
stale events, then test spatial plausibility against the estimated reachable region.

A candidate checkpoint at mapped point `c` is plausible when its correction distance
`||p_hat-c||` is no larger than a documented gate `g(u, Δt, v_max)` derived from
current uncertainty `u`, elapsed time, and maximum simulated speed. The exact gate and
thresholds must be fixed before evaluation. An unexpected mapped tag can be accepted
only if it passes this gate; acceptance produces a correction event and replan request.

## Mid-edge route anchors

Represent a mid-edge start as `(u, v, s, L)` where `s` is distance from node `u` on
an edge of length `L`. Build two temporary start alternatives:

- anchor → `u` with cost `s`;
- anchor → `v` with cost `L-s`.

Run existing Dijkstra from both endpoint alternatives and retain the lower total
cost. When direction constraints are later introduced, include only reachable
endpoints. The temporary anchor is session-local and must not modify the validated
map. Report partial-edge distance separately and include it in route cost. Estimated
and true anchors remain separate.

## Dynamic destination set

Maintain immutable confirmed pickups `C`, current requested products `S`, and
remaining destinations `R = S \ C`. Adding a product inserts its validated pickup
node into `R`; removing a product removes it only from `R`, never from `C`. After each
accepted list command, compute the endpoint-anchored costs from the current
`RouteAnchor`, call existing Held–Karp for `R`, expand legs with existing Dijkstra,
append checkout, and atomically publish a new route revision. Failed replans retain
the last safe route and emit a failure event.

## Guidance and completion

Each accepted correction or list mutation invalidates stale guidance by incrementing
the route revision. Generate new maneuver, checkpoint, product shelf/bay/level, and
checkout instructions from the published route. Product collection remains an
explicit validated confirmation at the correct pickup region. Completion requires
`R` empty and checkout reached; merely passing checkout early is insufficient.

## Required rejection reasons

`unknown_tag`, `wrong_map_version`, `duplicate_observation`,
`out_of_order_observation`, `implausible_correction`, `stale_route_revision`,
`non_adjacent_edge`, `invalid_product`, and `collected_product_removal_ignored` must
be machine-readable and visible in the research timeline.

## Safety and research boundaries

Real camera frames provide observations only. Simulated ground truth and movement
remain virtual. No result from this design should be described as physical trolley
navigation until separately evaluated with appropriate hardware and protocol.
