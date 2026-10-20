# Phase 7F physical AprilTag camera acceptance protocol

**Status: PENDING — no physical camera trial was performed by the agent.**

## Equipment and setup

Use the existing OpenCV scanner/dashboard with either the MacBook camera or an iPhone
Continuity Camera. Print tag36h11 IDs 200, 201, 202, and unknown ID 42 at one measured
marker size. Record verified device identity/index where available; do not infer it
from a UI label alone. Mount the camera or explicitly describe handheld use. A
stationary camera viewing a handheld marker is detector evidence, not trolley-location
evidence.

Use controlled combinations defined before testing, for example: normal indoor light
(record lux if measured), dim light, 0.5/1.0/1.5 m viewing distance, frontal view and
one stated oblique angle. Keep marker size, presentation duration, repetitions, and
success criterion constant within a condition. Suggested minimum is 20 presentations
per tag per condition, but the operator must record the actual denominator.

## Procedure

1. From repository root run
   `component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard`.
2. Open Research Execution, select Camera Evaluation, select the verified device, and
   start the scanner. Save the scanner log without editing it.
3. Present CP200, CP201, CP202, and ID 42 according to the randomized presentation
   schedule. Record presentation start and stable detection timestamps only if the
   clocks are genuinely observable; otherwise mark latency `NOT MEASURED`.
4. For each presentation record expected ID, detected ID(s), correct/incorrect/missed,
   distance, lighting, angle, and notes. An unknown 42 must not become a mapped
   checkpoint correction.
5. During a declared trial, disconnect or stop the camera once, record the scanner and
   dashboard response, reconnect, and record recovery. Do not substitute a direct
   callback for this step.
6. Export dashboard state and retain raw scanner logs. Never edit raw logs; write
   corrections or exclusions into a separate analysis note.

Use `phase_7f_physical_camera_acceptance_template.csv`. Record camera type, verified
identity, index, marker size, distance, lighting, presentations, correct detections,
incorrect detections, missed detections, latency unit/value, disconnect count, and raw
log path. Aggregate only after denominators and exclusions are frozen.

## Acceptance boundary

Physical camera status remains PENDING until actual presentations and raw logs exist.
A PASS requires the team to define thresholds before inspecting results, complete all
declared conditions, retain denominators, and review incorrect and missed detections.
This protocol does not establish physical trolley localization accuracy or map survey
accuracy.
