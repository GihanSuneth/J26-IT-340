# Phase 7G practical smart-trolley demonstration

The customer display is `/customer`. It intentionally shows only the live route, next maneuver, next product and shelf, progress, and the decisions that a shopper can take. `/` is the authorized research/operator dashboard and contains camera processing, tag decisions, localization corrections, route revisions, errors, landmarks, and event evidence.

## Demonstration modes

1. Customer simulation: select products, choose **Start**, and let the single backend autoplay clock move the virtual trolley. At a shelf, movement stops. Choose **Picked up**, **Skip · later**, or **Skip · remove**. “Later” produces a route that first leaves the shelf, so the arrival cannot loop immediately.
2. Camera-assisted evaluation: open `/`, refresh and select a frame-verified camera, then choose **Start Camera Evaluation**. Virtual movement waits for a plausible mapped AprilTag. This is real image detection controlling a virtual trolley; it is not evidence of physical trolley motion.

Start, pause, resume, stop, and playback rate are backend commands. Repeated GET requests never advance simulation time, and all tabs observe the same backend-owned timer. Manual **Step 0.25 s** remains available on the operator dashboard for repeatable tests.

## AprilTag layout

The original three-card layout remains unchanged. The optional v2 layout is `data/demo_store/v2/dense_apriltag_layout.json`. It retains IDs 200, 201, and 202 and maps unique 36h11 IDs at every junction and shelf approach, with mid-edge opportunities where necessary. The generated report proves nominal graph-path opportunity spacing is at most 2.0 m on every edge.

This is a coverage opportunity calculation, not a promise of camera detection. Detection depends on lighting, occlusion, viewing angle, motion blur, print quality, card size, and camera distance. The nine-card practical subset is in `data/apriltag_cards/generated_dense_practical`; its manifest records successful decoding and print dimensions.

## Integration boundary

`contracts/trolley_event_contract.schema.json` is the stable future IoT envelope. A trolley gateway can publish motion, AprilTag, product-decision, command, and fault events without changing the customer UI contract. `contracts/recommendation_output.schema.json` is the future recommendation boundary. The current recommendation is explicitly **DEMO · NOT TRAINED**, has null model version and score, and supports both accept and reject.

## Acceptance checklist

- GET polling is side-effect free; only explicit commands or the singleton backend clock move time.
- A product arrival stops motion and requires an explicit pickup or skip decision.
- Pickup supports an explicit quantity and creates an auditable shopping event.
- “Keep for later” leaves the item outstanding and routes away before returning.
- “Remove remaining” changes only remaining requested quantity; it never fabricates collection.
- Camera observations are classified accepted/rejected with a reason, before/after estimate, correction distance, expected tag, active layout, and anchor.
- Unknown, duplicate, stale, unavailable-camera, and implausible-jump observations are rejected.
- Customer and operator views read the same session, shopping revision, route revision, and history.
