"""Headless local OpenCV camera acquisition for AprilTag observations.

This module deliberately does not know about routes or mutate navigation state.
It emits a stable marker ID to a caller-supplied observation callback and never
opens a native GUI window.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib
import json
import logging
import math
import platform
import subprocess
import threading
import time
from typing import Any, Callable, Sequence

from .apriltag import OpenCVUnavailableError, _load_aruco, detect_apriltags_frame


LOGGER = logging.getLogger("component3.camera_scanner")
ObservationCallback = Callable[[int, float], dict[str, Any] | None]
DEFAULT_MAX_CAMERA_INDEX = 5
REJECTION_MESSAGES = {
    "unknown_tag": "Unknown checkpoint",
    "unexpected_checkpoint": "Out-of-order checkpoint",
    "duplicate_observation": "Duplicate checkpoint observation",
    "checkpoint_gate_not_active": "Checkpoint gate not active",
    "camera_mode_requires_camera_source": "Camera source required",
    "confidence_below_threshold": "Detection confidence below threshold",
    "correction_exceeds_limit": "Position correction exceeds safety limit",
    "observed_pose_inconsistent": "Observed position is inconsistent",
    "out_of_order_observation": "Observation timestamp is out of order",
    "wrong_map_version": "Wrong map version",
}


@dataclass(slots=True)
class CameraState:
    connection: str = "stopped"
    camera_index: int | None = None
    scanning: bool = False
    detected_tag_id: int | None = None
    visible_tag_ids: tuple[int, ...] = ()
    consistent_frames: int = 0
    required_consistent_frames: int = 3
    armed: bool = True
    consecutive_read_failures: int = 0
    frame_read_recoveries: int = 0
    last_result: str | None = None
    rejection_reason: str | None = None
    frames_processed: int = 0
    error: str | None = None
    frame_read: bool = False
    resolution: tuple[int, int] | None = None
    capture_backend: str | None = None
    device_name: str | None = None
    preview_available: bool = False
    preview_sequence: int = 0
    scan_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["visible_tag_ids"] = list(self.visible_tag_ids)
        payload["resolution"] = list(self.resolution) if self.resolution else None
        return payload


class DetectionConsensus:
    """Confirm one ID over consecutive frames and suppress held-marker repeats."""

    def __init__(self, required_frames: int = 3, release_frames: int = 2) -> None:
        if required_frames < 1 or release_frames < 1:
            raise ValueError("frame thresholds must be positive integers")
        self.required_frames = required_frames
        self.release_frames = release_frames
        self.reset()

    def reset(self) -> None:
        self.candidate: int | None = None
        self.count = 0
        self.absent_count = 0
        self.armed = True

    def reset_partial(self) -> None:
        """Discard an incomplete candidate without rearming a submitted marker."""
        self.candidate = None
        self.count = 0
        self.absent_count = 0

    def update(self, marker_ids: Sequence[int]) -> int | None:
        unique_ids = tuple(dict.fromkeys(marker_ids))
        if len(unique_ids) != 1:
            self.candidate = None
            self.count = 0
            if not unique_ids:
                self.absent_count += 1
                if self.absent_count >= self.release_frames:
                    self.armed = True
            else:
                self.absent_count = 0
            return None
        marker_id = unique_ids[0]
        self.absent_count = 0
        if marker_id != self.candidate:
            self.candidate = marker_id
            self.count = 1
        else:
            self.count += 1
        if self.armed and self.count >= self.required_frames:
            self.armed = False
            return marker_id
        return None


def _camera_backend(cv2: Any) -> int | None:
    """Prefer AVFoundation on macOS and otherwise let OpenCV choose."""
    if platform.system() == "Darwin":
        return getattr(cv2, "CAP_AVFOUNDATION", None)
    return getattr(cv2, "CAP_ANY", None)


def _open_camera(cv2: Any, index: int) -> Any:
    """Open one index with the platform backend, retaining test-double support."""
    backend = _camera_backend(cv2)
    if backend is None:
        return cv2.VideoCapture(index)
    try:
        return cv2.VideoCapture(index, backend)
    except TypeError:
        return cv2.VideoCapture(index)


def _system_profiler_camera_names() -> tuple[str, ...]:
    """Read macOS camera names when system_profiler exposes them."""
    if platform.system() != "Darwin":
        return ()
    try:
        completed = subprocess.run(
            ["/usr/sbin/system_profiler", "SPCameraDataType", "-json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        )
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return ()
    names: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            name = value.get("_name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    collect(payload.get("SPCameraDataType", []))
    return tuple(dict.fromkeys(names))


def probe_camera_devices(
    indices: Sequence[int] = tuple(range(DEFAULT_MAX_CAMERA_INDEX + 1)),
    *,
    device_names: Sequence[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Probe camera indices without a GUI; release each before continuing."""
    for index in indices:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("camera indices must be nonnegative integers")
    try:
        cv2 = importlib.import_module("cv2")
    except ModuleNotFoundError as exc:
        raise OpenCVUnavailableError(
            "OpenCV is unavailable; install the Component 3 camera requirements"
        ) from exc
    results: list[dict[str, Any]] = []
    for index in indices:
        capture: Any = None
        result: dict[str, Any] = {
            "camera_index": index,
            "opened": False,
            "frame_read": False,
            "frame_dimensions": None,
            "backend": None,
            "device_name": None,
            "error": None,
        }
        try:
            capture = _open_camera(cv2, index)
            result["opened"] = bool(capture.isOpened())
            if not result["opened"]:
                result["error"] = "Camera could not be opened."
            else:
                try:
                    result["backend"] = capture.getBackendName()
                except Exception as exc:
                    result["error"] = f"Could not identify capture backend: {exc}"
                ok, frame = capture.read()
                result["frame_read"] = bool(ok and frame is not None)
                if result["frame_read"]:
                    result["frame_dimensions"] = [
                        int(frame.shape[1]),
                        int(frame.shape[0]),
                    ]
                    if device_names is not None and index < len(device_names):
                        result["device_name"] = device_names[index]
                elif result["error"] is None:
                    result["error"] = "Camera opened but no frame could be read."
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception as exc:
                    release_error = f"Could not release camera: {exc}"
                    result["error"] = (
                        f"{result['error']} {release_error}"
                        if result["error"]
                        else release_error
                    )
        results.append(result)
    return tuple(results)


def enumerate_camera_devices(
    max_camera_index: int = DEFAULT_MAX_CAMERA_INDEX,
) -> dict[str, Any]:
    """Return only frame-verified cameras plus complete diagnostic attempts."""
    if (
        isinstance(max_camera_index, bool)
        or not isinstance(max_camera_index, int)
        or not 0 <= max_camera_index <= 32
    ):
        raise ValueError("max_camera_index must be an integer between 0 and 32")
    names = _system_profiler_camera_names()
    attempts = probe_camera_devices(
        tuple(range(max_camera_index + 1)), device_names=names
    )
    devices = tuple(
        {
            **attempt,
            "label": attempt["device_name"] or f"Camera index {attempt['camera_index']}",
        }
        for attempt in attempts
        if attempt["opened"] and attempt["frame_read"]
    )
    return {
        "devices": devices,
        "attempts": attempts,
        "device_names_exposed": bool(names),
        "capture_backend": "AVFOUNDATION" if platform.system() == "Darwin" else "AUTO",
    }


class CameraScanner:
    """Own one camera lifecycle and submit only stable visual detections."""

    DEFAULT_MAX_CONSECUTIVE_READ_FAILURES = 5
    DEFAULT_READ_RECOVERY_TIMEOUT_S = 2.0
    DEFAULT_MAX_FPS = 15.0
    MAX_ALLOWED_FPS = 60.0
    READ_RETRY_INTERVAL_S = 0.05

    def __init__(
        self,
        callback: ObservationCallback | None = None,
        *,
        required_frames: int = 3,
        release_frames: int = 2,
        max_consecutive_read_failures: int = DEFAULT_MAX_CONSECUTIVE_READ_FAILURES,
        read_recovery_timeout_s: float = DEFAULT_READ_RECOVERY_TIMEOUT_S,
        max_fps: float = DEFAULT_MAX_FPS,
        disconnect_callback: Callable[[], Any] | None = None,
    ) -> None:
        if (
            isinstance(max_consecutive_read_failures, bool)
            or not isinstance(max_consecutive_read_failures, int)
            or max_consecutive_read_failures < 1
        ):
            raise ValueError("max_consecutive_read_failures must be a positive integer")
        if (
            isinstance(read_recovery_timeout_s, bool)
            or not isinstance(read_recovery_timeout_s, (int, float))
            or not math.isfinite(read_recovery_timeout_s)
            or read_recovery_timeout_s <= 0
        ):
            raise ValueError("read_recovery_timeout_s must be a finite positive number")
        if (
            isinstance(max_fps, bool)
            or not isinstance(max_fps, (int, float))
            or not math.isfinite(max_fps)
            or not 0 < max_fps <= self.MAX_ALLOWED_FPS
        ):
            raise ValueError(f"max_fps must be greater than 0 and at most {self.MAX_ALLOWED_FPS}")
        self.callback = callback
        self.disconnect_callback = disconnect_callback
        self.consensus = DetectionConsensus(required_frames, release_frames)
        self.max_consecutive_read_failures = max_consecutive_read_failures
        self.read_recovery_timeout_s = float(read_recovery_timeout_s)
        self.max_fps = float(max_fps)
        self._state = CameraState(required_consistent_frames=required_frames)
        self._lock = threading.RLock()
        self._capture_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: Any = None
        self._cv2: Any = None
        self._preview_jpeg: bytes | None = None
        self._last_preview_s = 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def preview(self) -> tuple[bytes | None, int]:
        """Return the latest bounded JPEG and its sequence without copying frames."""
        with self._lock:
            return self._preview_jpeg, self._state.preview_sequence

    def start(self, camera_index: int = 0, device_name: str | None = None) -> dict[str, Any]:
        if isinstance(camera_index, bool) or not isinstance(camera_index, int) or camera_index < 0:
            raise ValueError("camera_index must be a nonnegative integer")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValueError("Camera is already running")
            cv2, _ = _load_aruco()
            capture = _open_camera(cv2, camera_index)
            if not capture.isOpened():
                capture.release()
                self._state = CameraState(
                    connection="unavailable",
                    camera_index=camera_index,
                    required_consistent_frames=self.consensus.required_frames,
                    error=(
                        f"Camera index {camera_index} could not be opened with the macOS "
                        "AVFoundation backend. Stop other apps using the camera, unlock "
                        "and select the iPhone in its Continuity Camera prompt, check "
                        "System Settings > Privacy & Security > Camera permission for "
                        "Terminal/Python, then Refresh Cameras."
                    ),
                )
                return self._state.to_dict()
            try:
                backend = capture.getBackendName()
            except Exception:
                backend = None
            self.consensus.reset()
            with self._capture_lock:
                self._capture = capture
            self._cv2 = cv2
            self._stop_event.clear()
            self._state = CameraState(
                connection="connected",
                camera_index=camera_index,
                scanning=True,
                required_consistent_frames=self.consensus.required_frames,
                capture_backend=backend,
                device_name=device_name,
            )
            self._preview_jpeg = None
            self._last_preview_s = 0.0
            self._thread = threading.Thread(
                target=self._run, name="component3-camera-scanner", daemon=True
            )
            self._thread.start()
            return self._state.to_dict()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5.0)
            if thread.is_alive():
                with self._lock:
                    self._state.connection = "stopping"
                    self._state.error = (
                        "Camera worker has not exited yet; retry Stop Camera after "
                        "the current frame read completes."
                    )
                    return self._state.to_dict()
        with self._lock:
            if self._state.connection not in ("error", "disconnected"):
                self._state.connection = "stopped"
                self._state.error = None
            self._state.scanning = False
            self._state.visible_tag_ids = ()
            self._state.detected_tag_id = None
            self._state.preview_available = False
            self._preview_jpeg = None
            return self._state.to_dict()

    def switch(self, camera_index: int, device_name: str | None = None) -> dict[str, Any]:
        """Fully release the current capture before opening a different device."""
        current = self.snapshot()
        if current["scanning"] and current["camera_index"] == camera_index:
            return current
        stopped = self.stop()
        if stopped["scanning"]:
            raise ValueError(
                "The previous camera is still stopping and has not been released."
            )
        return self.start(camera_index, device_name)

    def _release_capture(self) -> None:
        with self._capture_lock:
            capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()

    def _run(self) -> None:
        print("[CAMERA] Scanning...", flush=True)
        failure_started_s: float | None = None
        consecutive_failures = 0
        try:
            while not self._stop_event.is_set():
                if (
                    failure_started_s is not None
                    and time.monotonic() - failure_started_s
                    >= self.read_recovery_timeout_s
                ):
                    raise CameraDisconnectedError(
                        consecutive_failures,
                        time.monotonic() - failure_started_s,
                    )
                capture = self._capture
                if capture is None:
                    break
                frame_started_s = time.monotonic()
                ok, frame = capture.read()
                if self._stop_event.is_set():
                    break
                if not ok or frame is None:
                    now_s = time.monotonic()
                    if failure_started_s is None:
                        failure_started_s = now_s
                        LOGGER.warning("Camera frame read failed; waiting for recovery")
                    consecutive_failures += 1
                    self.consensus.reset_partial()
                    with self._lock:
                        self._state.consecutive_read_failures = consecutive_failures
                        self._state.consistent_frames = 0
                        self._state.armed = self.consensus.armed
                        self._state.detected_tag_id = None
                        self._state.visible_tag_ids = ()
                    failure_duration_s = now_s - failure_started_s
                    if (
                        consecutive_failures >= self.max_consecutive_read_failures
                        or failure_duration_s >= self.read_recovery_timeout_s
                    ):
                        raise CameraDisconnectedError(
                            consecutive_failures, failure_duration_s
                        )
                    self._stop_event.wait(
                        min(
                            self.READ_RETRY_INTERVAL_S,
                            self.read_recovery_timeout_s - failure_duration_s,
                        )
                    )
                    continue
                if self._stop_event.is_set():
                    break
                if failure_started_s is not None:
                    recovery_duration_s = time.monotonic() - failure_started_s
                    if recovery_duration_s >= self.read_recovery_timeout_s:
                        raise CameraDisconnectedError(
                            consecutive_failures, recovery_duration_s
                        )
                    LOGGER.info(
                        "Camera frame reads recovered after %d consecutive failures (%.3f s)",
                        consecutive_failures,
                        recovery_duration_s,
                    )
                    with self._lock:
                        self._state.frame_read_recoveries += 1
                        self._state.scan_events.append(
                            {
                                "event": "frame_read_recovered",
                                "consecutive_failures": consecutive_failures,
                                "recovery_timestamp_s": time.monotonic(),
                            }
                        )
                        del self._state.scan_events[:-100]
                    failure_started_s = None
                    consecutive_failures = 0
                    self.consensus.reset_partial()
                with self._lock:
                    self._state.consecutive_read_failures = 0
                detections = detect_apriltags_frame(frame)
                if self._stop_event.is_set():
                    break
                ids = tuple(item.marker_id for item in detections)
                stable_id = self.consensus.update(ids)
                frame_shape = getattr(frame, "shape", None)
                with self._lock:
                    self._state.frames_processed += 1
                    self._state.frame_read = True
                    if frame_shape is not None and len(frame_shape) >= 2:
                        self._state.resolution = (int(frame_shape[1]), int(frame_shape[0]))
                    self._state.visible_tag_ids = ids
                    self._state.consistent_frames = self.consensus.count
                    self._state.armed = self.consensus.armed
                    self._state.detected_tag_id = ids[0] if len(ids) == 1 else None
                    if len(ids) > 1:
                        if self._state.rejection_reason != "multiple_visible_tags":
                            self._state.scan_events.append(
                                {
                                    "detected_tag_ids": list(ids),
                                    "detection_timestamp_s": time.monotonic(),
                                    "accepted": False,
                                    "reason": "multiple_visible_tags",
                                }
                            )
                        self._state.last_result = "rejected"
                        self._state.rejection_reason = "multiple_visible_tags"
                if frame_shape is not None and len(frame_shape) >= 2:
                    self._update_preview(self._cv2, frame, detections)
                if stable_id is not None:
                    self._submit(stable_id)
                elapsed_s = time.monotonic() - frame_started_s
                self._stop_event.wait(max(0.0, (1.0 / self.max_fps) - elapsed_s))
        except CameraDisconnectedError as exc:
            LOGGER.error("Camera disconnected: %s", exc)
            self.consensus.reset_partial()
            with self._lock:
                self._state.connection = "disconnected"
                self._state.scanning = False
                self._state.error = str(exc)
                self._state.consistent_frames = 0
                self._state.armed = self.consensus.armed
                self._state.detected_tag_id = None
                self._state.visible_tag_ids = ()
                self._state.preview_available = False
                self._preview_jpeg = None
            if self.disconnect_callback is not None:
                self.disconnect_callback()
        except Exception as exc:
            LOGGER.exception("Camera scanner stopped after an error")
            with self._lock:
                self._state.connection = "error"
                self._state.scanning = False
                self._state.error = str(exc)
                self._state.preview_available = False
                self._preview_jpeg = None
            if self.disconnect_callback is not None:
                self.disconnect_callback()
        finally:
            try:
                self._release_capture()
            except Exception as exc:
                LOGGER.exception("Camera capture could not be released")
                with self._lock:
                    self._state.connection = "error"
                    self._state.error = f"Camera capture could not be released: {exc}"
            with self._lock:
                self._state.scanning = False
                if self._state.connection == "stopping":
                    self._state.connection = "stopped"
                    self._state.error = None

    def _update_preview(self, cv2: Any, frame: Any, detections: Sequence[Any]) -> None:
        """Encode at most five annotated preview frames per second into one slot."""
        now_s = time.monotonic()
        if now_s - self._last_preview_s < 0.2:
            return
        self._last_preview_s = now_s
        preview = frame.copy()
        for detection in detections:
            points = [(int(round(x)), int(round(y))) for x, y in detection.corners_px]
            for start, end in zip(points, points[1:] + points[:1]):
                cv2.line(preview, start, end, (36, 214, 120), 3)
            if points:
                label_at = (points[0][0], max(24, points[0][1] - 8))
                cv2.putText(
                    preview,
                    f"AprilTag {detection.marker_id}",
                    label_at,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (36, 214, 120),
                    2,
                    cv2.LINE_AA,
                )
        height, width = preview.shape[:2]
        if width > 960:
            scale = 960.0 / width
            preview = cv2.resize(preview, (960, max(1, int(height * scale))))
        ok, encoded = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 72])
        if not ok:
            return
        jpeg = encoded.tobytes()
        with self._lock:
            self._preview_jpeg = jpeg
            self._state.preview_available = True
            self._state.preview_sequence += 1

    def _submit(self, marker_id: int) -> None:
        timestamp_s = time.monotonic()
        validation_started = time.perf_counter()
        print(f"[DETECTED] Tag ID: {marker_id}", flush=True)
        if self.callback is None:
            return
        print("[VALIDATION] Checking checkpoint...", flush=True)
        result = self.callback(marker_id, timestamp_s) or {}
        validation_latency_ms = (time.perf_counter() - validation_started) * 1000.0
        observed = result.get("observed_checkpoint") or {}
        accepted = bool(observed.get("accepted"))
        reason = observed.get("reason") or "validation_result_unavailable"
        with self._lock:
            self._state.last_result = "accepted" if accepted else "rejected"
            self._state.rejection_reason = None if accepted else reason
            self._state.scan_events.append(
                {
                    "detected_tag_id": marker_id,
                    "detection_timestamp_s": timestamp_s,
                    "accepted": accepted,
                    "reason": reason,
                    "expected_checkpoint_id": observed.get("expected_checkpoint_id"),
                    "validation_latency_ms": validation_latency_ms,
                    "position_before": observed.get("position_before"),
                    "position_after": observed.get("position_after"),
                    "guidance_type": (result.get("guidance") or {}).get("instruction_type"),
                }
            )
            del self._state.scan_events[:-100]
        if accepted:
            print(f"[ACCEPTED] CP{marker_id} confirmed", flush=True)
            print("[LOCALIZATION] Position corrected", flush=True)
            print("[NAVIGATION] Continue toward next destination", flush=True)
        else:
            print(f"[REJECTED] {REJECTION_MESSAGES.get(reason, reason)}", flush=True)
            print("[LOCALIZATION] Position unchanged", flush=True)


class CameraDisconnectedError(RuntimeError):
    """Raised after frame reads exceed the configured recovery bounds."""

    def __init__(self, consecutive_failures: int, failure_duration_s: float) -> None:
        """Describe the bounded read failure that ended the camera session."""
        self.consecutive_failures = consecutive_failures
        self.failure_duration_s = failure_duration_s
        super().__init__(
            "Camera frame reads did not recover after "
            f"{consecutive_failures} consecutive failures over {failure_duration_s:.2f} seconds"
        )
