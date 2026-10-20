# Phase 7B.1 — Mac camera implementation and evaluation procedure

## Scope and acceptance status

This mode uses a real local camera only for AprilTag observations. Store
geometry, trolley motion, dead reckoning, products, shelves, pickup confirmation,
and checkout remain software simulation. No Raspberry Pi, Arduino, encoder,
IMU, physical trolley, cloud service, or frame upload is involved.

Automated detector, consensus, checkpoint-gate, navigation, API, and regression
tests are implemented. On 2026-10-15, AVFoundation index 1 repeatedly returned
1920 × 1080 frames, including 125 frames in a headless smoke run. Index 0 opened
in probes but its frame-read result varied; index 2 did not open. No physical
AprilTag was presented or confirmed. Physical-card scan acceptance,
range/latency measurement, and the full real-camera walkthrough remain pending.
The prior 2026-10-14 probe was denied by macOS; access was available during this
later run.

## Architecture

1. `CameraScanner` owns `cv2.VideoCapture`, headless frame processing, shutdown,
   and status. It releases the device after stop or exception and never opens
   OpenCV HighGUI windows.
2. `detect_apriltags_frame` accepts a grayscale, BGR, or BGRA OpenCV array and
   returns immutable detections. It never changes navigation state.
3. `DetectionConsensus` requires three consecutive frames containing exactly
   one ID. A held card submits once; two absent frames rearm the scanner.
4. The camera callback creates a `mac_camera_opencv` observation only after
   consensus.
5. `CheckpointObservationProcessor` remains the authority for known ID,
   expected order, duplicate, timestamp, map version, confidence, observed-pose,
   and maximum-correction validation.
6. An accepted observation corrects the estimate and releases the current gate.
   It does not set an arbitrary trolley location or bypass route progression.

The installed environment contains one OpenCV distribution,
`opencv-contrib-python` 5.0.0.93, with Cocoa GUI support. The reported crash is
at `cv2.imshow` in the camera worker, not at capture or AprilTag detection. Since
macOS Cocoa GUI calls have main-thread lifecycle constraints and the camera
worker is not the GUI main thread, the scanner now avoids native HighGUI
entirely. Camera read and detector errors remain surfaced as scan errors.

Transient unreadable frames are retried with a 50 ms backoff. Five consecutive
failures or two seconds without a successful frame marks the camera disconnected,
releases it, and invokes the dashboard's camera-stop callback. A recovered
capture clears only partial consensus; an already-submitted tag remains
duplicate-suppressed until two successfully detected empty frames. Frame
processing is capped at 15 FPS by default, with a configurable upper bound of
60 FPS in the standalone smoke test.

Camera mode starts at CP200. Virtual movement pauses at CP201 and CP202 until
their genuine observations pass validation. An ID detected while no gate is
active is rejected as `checkpoint_gate_not_active`. Stopping or disconnecting
the camera pauses active virtual travel; reconnecting resumes it without
inventing a scan. Products still require explicit manual confirmation.

## Detector and cards

- OpenCV dictionary: `cv2.aruco.DICT_APRILTAG_36h11`
- CP200: ID 200, entrance node `N0_0`
- CP201: ID 201, central cross-aisle node `N2_3`
- CP202: ID 202, checkout node `N4_5`
- Negative card: ID 42, intentionally unknown to the demo layout

`component3/data/apriltag_cards/generate_cards.py` creates each marker from the
configured OpenCV dictionary and immediately redetects it. Generation fails if
the returned ID differs. Each printable card has a 200 mm square field, centered
160 mm marker, and 20 mm white margins. The human label occupies a separate
20 mm strip below the card. Individual PNG/PDF files and an A2 four-card PDF are
under `component3/data/apriltag_cards/generated/`.

Print PDFs at **Actual Size / 100%**, with page fitting disabled. Prefer matte
paper and measure the marker's black outer boundary; it must be 160 mm square.

## macOS setup and smoke test

1. Use `component3/.venv/`; it contains Python 3.14, NumPy, and only
   `opencv-contrib-python` (not both OpenCV wheel variants).
2. Open **System Settings > Privacy & Security > Camera** and enable the host
   used to launch Python, normally Terminal or the relevant IDE.
3. Quit and reopen that host after changing permission.
4. Close applications that may exclusively hold the camera.
5. From the repository root, probe the available camera indices:

   ```bash
   component3/.venv/bin/python -B -m \
     component3.backend.comp3_reco_navigation.navigation.apriltag_camera_smoke_test \
     --probe-cameras
   ```

6. Select the desired index explicitly and start the headless smoke test:

   ```bash
   component3/.venv/bin/python -B -m \
     component3.backend.comp3_reco_navigation.navigation.apriltag_camera_smoke_test \
     --camera-index 0 --no-preview
   ```

   Present each physical card and confirm its stable ID in the terminal. Stop
   with Ctrl-C and confirm the process reports that the camera was released.
   Native OpenCV preview is intentionally absent; the camera worker performs no
   `imshow` or `waitKey` calls. A local browser preview is a follow-up, not part
   of the current evaluation workflow.

Do not proceed to physical-card acceptance unless the intended camera opens and
the physical cards are detected. A successful frame read or generated-image unit
test is not equivalent to a physical AprilTag scan.

## Dashboard workflow

Launch:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard
```

Open `http://127.0.0.1:8765/`, select products, plan them, and select **Start
Camera Evaluation**. Expected terminal flow for a valid gated scan is:

```text
[CAMERA] Scanning...
[DETECTED] Tag ID: 201
[VALIDATION] Checking checkpoint...
[ACCEPTED] CP201 confirmed
[LOCALIZATION] Position corrected
[NAVIGATION] Continue toward next destination
```

Invalid observations print their genuine processor reason and
`[LOCALIZATION] Position unchanged`. The dashboard exposes camera connection,
live ID, expected checkpoint, confirmed checkpoint, scan result/reason,
instruction, trolley position, shelf target, remaining products, and checkout.

Acceptance sequence:

1. Scan CP200 at the entrance gate.
2. Let virtual movement reach CP201; confirm it pauses and scans.
3. Present ID42 and confirm `unknown_tag`, with unchanged estimate.
4. Present CP202 and confirm `unexpected_checkpoint`.
5. Present CP201 for three consistent frames and confirm correction/resumption.
6. Keep CP201 visible and verify it is not submitted repeatedly.
7. Remove it for at least two frames to rearm.
8. At each product, explicitly confirm pickup.
9. Stop the camera during travel and confirm safe pause; restart it and confirm
   safe continuation without an observation.
10. At checkout, scan CP202 and verify checkout completes only after every
    selected product was manually confirmed.

Multiple simultaneously visible tags are rejected as
`multiple_visible_tags`; blank, blurred, or unreadable frames create no
observation. Camera read failure changes connection state to `error`, releases
the device, and pauses camera-mode travel.

## Evaluation records and metrics

Camera state keeps a bounded local list of genuine scan submissions containing:

- detected ID and expected checkpoint;
- acceptance/rejection and reason;
- monotonic detection timestamp;
- validation latency (not camera-to-photon latency);
- estimated position before and after validation;
- guidance type after validation.

The navigation export separately contains checkpoint, correction, guidance,
product, and checkout events. During physical acceptance, save both exports and
record no result for a case that was not actually performed. Detection accuracy,
range, lighting tolerance, total scan latency, and completion rate are currently
unmeasured.

The denied-camera probe is preserved at
`component3/evaluation/camera_assisted/camera_probe_2026-10-14.txt`. It is kept
separate from synthetic detector fixtures and does not claim an accepted scan.

## Known limitations

- Camera permission and physical-card acceptance require an interactive local
  user session and remain pending.
- No camera calibration or pose estimation is performed; a tag supplies a
  validated checkpoint identity, not continuous six-degree-of-freedom pose.
- ArUco does not expose a calibrated probability for these detections, so camera
  observations leave optional confidence unset and rely on frame consensus plus
  the existing spatial safety checks.
- The simulation can evaluate workflow behavior but cannot establish physical
  trolley, motion-sensor, or store-scale localization performance.
