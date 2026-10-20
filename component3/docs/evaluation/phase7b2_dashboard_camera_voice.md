# Phase 7B.2 — Dashboard, camera preview, and voice

Date: 2026-10-15  
Branch: `Comp3_Arun`

The synthetic navigation algorithms and map are unchanged. The dashboard is
organized into Shopping List, Navigation Map, Camera Evaluation, Turn-by-Turn
Guidance, and Evaluation Results. Desktop gives the metric SVG map the largest
area; tablet and mobile layouts stack without horizontal overflow.

The Python scanner remains the only camera owner. It annotates detector output,
downscales preview frames to at most 960 pixels wide, encodes at JPEG quality 72,
publishes at most five previews per second, and retains only the latest JPEG.
`GET /api/camera/preview.jpg` serves that in-memory frame locally. Stop,
disconnect, and scanner errors remove preview availability.

Camera indices are discovered, not assigned fixed identities. **Refresh
Cameras** now rebuilds the selector from devices that open and return a frame
through AVFoundation. The 2026-10-15 run exposed `MacBook Air Camera` at index
0 and 1920x1080. A real dashboard run loaded its preview at 960x540; no
physical-camera frame was written to evidence storage. No iPhone camera was
available during this run.

Voice is off by default. The browser exposes enable/disable, test, volume,
status, and optional installed-voice selection. Stable event IDs suppress
duplicates; disabling or rerouting cancels pending speech. Unsupported browsers
show `Unavailable` and disable the controls.

Verification:

- 132 backend tests passed.
- 86 dashboard and simulation tests passed.
- Chromium passed at 1366x768, 1920x1080, and 390x844 with five required
  sections, no horizontal overflow, no console errors, and no page errors.
- Manual navigation, guided navigation, and the camera-assisted CP200 entrance
  gate passed browser/API acceptance.
- Voice first-event, duplicate suppression, and disabled-state behavior passed.

Evidence is stored in `component3/evaluation/navigation_simulation/phase7b2_browser_acceptance.json`,
`component3/evaluation/camera_assisted/phase7b2_real_preview_2026-10-15.json`,
and the three `C3-DASH-7B2-*` screenshots. Historical evidence was not overwritten.
