"""Standalone Mac-camera smoke test; it never submits navigation observations."""

from __future__ import annotations

import argparse
import json
import time

from .camera_scanner import CameraScanner, probe_camera_devices


def main() -> int:
    """Run a local headless scan or camera-device diagnostic."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument(
        "--max-consecutive-read-failures",
        type=int,
        default=CameraScanner.DEFAULT_MAX_CONSECUTIVE_READ_FAILURES,
        help="Disconnect after this many consecutive unreadable frames",
    )
    parser.add_argument(
        "--read-recovery-timeout",
        type=float,
        default=CameraScanner.DEFAULT_READ_RECOVERY_TIMEOUT_S,
        metavar="SECONDS",
        help="Disconnect if unreadable frames persist this long",
    )
    parser.add_argument(
        "--max-fps",
        type=float,
        default=CameraScanner.DEFAULT_MAX_FPS,
        help=f"Maximum frame-processing rate, greater than 0 and at most {CameraScanner.MAX_ALLOWED_FPS:g}",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Run headlessly without OpenCV native GUI (the default and recommended mode)",
    )
    parser.add_argument(
        "--probe-cameras",
        action="store_true",
        help="Probe camera devices without opening GUI windows",
    )
    parser.add_argument(
        "--camera-indices",
        type=int,
        nargs="+",
        default=(0, 1, 2),
        metavar="INDEX",
        help="Indices to probe with --probe-cameras (default: 0 1 2)",
    )
    args = parser.parse_args()

    if args.probe_cameras:
        for result in probe_camera_devices(args.camera_indices):
            print(json.dumps(result, sort_keys=True), flush=True)
        return 0

    scanner = CameraScanner(
        max_consecutive_read_failures=args.max_consecutive_read_failures,
        read_recovery_timeout_s=args.read_recovery_timeout,
        max_fps=args.max_fps,
    )
    state = scanner.start(args.camera_index)
    if state["connection"] != "connected":
        print(f"[CAMERA] Unavailable: {state['error']}")
        return 2
    preview_status = (
        "Native preview disabled by --no-preview."
        if args.no_preview
        else "Native OpenCV preview is not used; scanning headlessly."
    )
    print(
        f"[CAMERA] {preview_status} Present a printed/displayed tag; "
        "press Ctrl+C to stop.",
        flush=True,
    )
    exit_code = 0
    try:
        while scanner.snapshot()["scanning"]:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[CAMERA] Stopping scan...", flush=True)
    finally:
        state = scanner.stop()
    print(f"[CAMERA] Frames processed: {state['frames_processed']}", flush=True)
    if state["connection"] == "error":
        print(f"[CAMERA] Scan failed: {state['error']}", flush=True)
        exit_code = 1
    elif state["connection"] == "disconnected":
        print(f"[CAMERA] Disconnected: {state['error']}", flush=True)
        exit_code = 1
    elif state["connection"] == "stopping" or state["scanning"]:
        print(f"[CAMERA] Shutdown is still pending: {state['error']}", flush=True)
        exit_code = 1
    else:
        print("[CAMERA] Camera released.", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
