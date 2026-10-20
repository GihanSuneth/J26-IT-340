# macOS Continuity Camera acceptance

Date: 2026-10-15  
Branch: `Comp3_Arun`

## Implementation

Camera discovery now explicitly requests OpenCV's AVFoundation backend on
macOS. **Refresh Cameras** probes indices 0 through 5 sequentially and retains
only devices that both open and return a frame. Every probe capture is released
before the next is opened. The selector therefore contains verified devices,
not assumed MacBook/iPhone mappings.

Names are read from macOS `system_profiler SPCameraDataType -json` when that API
exposes them. Otherwise the UI uses `Camera index N`. Selection is passed to the
Python scanner unchanged. Switching stops and joins the current scanner,
releases its capture, then opens the selected device. The browser never opens a
camera session.

## Manual MacBook/iPhone steps

1. Start the dashboard from the repository root with
   `component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.dashboard`.
2. Grant the launching Terminal/Python process access under **System Settings >
   Privacy & Security > Camera** and restart it if permission changed.
3. Open the dashboard and click **Refresh Cameras**. Confirm the MacBook camera
   appears with a readable-frame resolution.
4. Start the MacBook camera and confirm the embedded preview updates and the
   status reports `AVFOUNDATION`.
5. Stop the camera. Lock the iPhone, enable Wi-Fi and Bluetooth on both devices,
   place the iPhone nearby, and select/approve its Continuity Camera prompt.
6. Click **Refresh Cameras** again. Confirm a second frame-verified device
   appears. It may have an actual macOS name or a verified index label.
7. Select that device and click **Start Camera**. Confirm the embedded view is
   the iPhone feed.
8. While it is running, choose the MacBook camera and click **Select Camera**.
   Confirm the preview switches without a second capture session or an in-use
   error. Repeat in the other direction.
9. Start Camera Evaluation and present CP200, CP201, and CP202 in route order.
   Confirm bounding boxes/IDs appear and accepted observations release only the
   expected gates.
10. Disconnect the iPhone and confirm the dashboard reports disconnection;
    reconnect it, click **Refresh Cameras**, and select it again.

## Current hardware status

The MacBook camera was physically verified as `MacBook Air Camera`, index 0,
1920×1080 through AVFoundation; the embedded preview loaded at 960×540 and no
frame was saved. An iPhone Continuity Camera was not physically available in
this run, so iPhone discovery, switching, and live AprilTag acceptance remain
pending manual execution of the steps above.
