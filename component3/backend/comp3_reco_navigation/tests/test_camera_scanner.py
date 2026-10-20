"""Tests for stable camera detections without opening physical hardware."""

from __future__ import annotations

import threading
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from component3.backend.comp3_reco_navigation.navigation.camera_scanner import (
    CameraScanner,
    DetectionConsensus,
    enumerate_camera_devices,
    probe_camera_devices,
)
from component3.backend.comp3_reco_navigation.navigation.apriltag import AprilTagDetection
from component3.backend.comp3_reco_navigation.navigation import apriltag_camera_smoke_test


class DetectionConsensusTests(unittest.TestCase):
    def test_requires_three_consistent_frames(self) -> None:
        consensus = DetectionConsensus(required_frames=3, release_frames=2)
        self.assertIsNone(consensus.update([201]))
        self.assertIsNone(consensus.update([201]))
        self.assertEqual(consensus.update([201]), 201)

    def test_continuously_visible_tag_is_submitted_only_once(self) -> None:
        consensus = DetectionConsensus(required_frames=2, release_frames=2)
        results = [consensus.update([200]) for _ in range(6)]
        self.assertEqual(results.count(200), 1)

    def test_tag_must_disappear_before_rearm(self) -> None:
        consensus = DetectionConsensus(required_frames=2, release_frames=2)
        self.assertEqual([consensus.update([202]), consensus.update([202])][-1], 202)
        self.assertIsNone(consensus.update([]))
        self.assertFalse(consensus.armed)
        self.assertIsNone(consensus.update([]))
        self.assertTrue(consensus.armed)
        self.assertIsNone(consensus.update([202]))
        self.assertEqual(consensus.update([202]), 202)


class _FakeCapture:
    def __init__(self, opened: bool = True) -> None:
        self.opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        return True, object()

    def release(self) -> None:
        self.released = True


class _SequencedCapture(_FakeCapture):
    """Yield a predetermined sequence of successful and failed reads."""

    def __init__(self, outcomes: list[bool]) -> None:
        """Initialize the ordered read outcomes."""
        super().__init__()
        self.outcomes = list(outcomes)

    def read(self) -> tuple[bool, object | None]:
        """Return the next test read result, then successful frames."""
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            return (True, object()) if outcome else (False, None)
        return True, object()


class CameraScannerTests(unittest.TestCase):
    def test_enumeration_returns_only_frame_verified_devices_with_real_names(self) -> None:
        attempts = (
            {"camera_index": 0, "opened": True, "frame_read": True, "frame_dimensions": [640, 480], "backend": "AVFOUNDATION", "device_name": "FaceTime HD Camera", "error": None},
            {"camera_index": 1, "opened": True, "frame_read": False, "frame_dimensions": None, "backend": "AVFOUNDATION", "device_name": "iPhone Camera", "error": "no frame"},
            {"camera_index": 2, "opened": True, "frame_read": True, "frame_dimensions": [1920, 1080], "backend": "AVFOUNDATION", "device_name": None, "error": None},
        )
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._system_profiler_camera_names",
            return_value=("FaceTime HD Camera", "iPhone Camera"),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.probe_camera_devices",
            return_value=attempts,
        ):
            result = enumerate_camera_devices(2)
        self.assertEqual([item["camera_index"] for item in result["devices"]], [0, 2])
        self.assertEqual(result["devices"][0]["label"], "FaceTime HD Camera")
        self.assertEqual(result["devices"][1]["label"], "Camera index 2")
        self.assertEqual(len(result["attempts"]), 3)

    def test_macos_probe_requests_avfoundation_backend(self) -> None:
        calls = []

        class Capture(_FakeCapture):
            def read(self):
                return True, SimpleNamespace(shape=(720, 1280, 3))

            def getBackendName(self):
                return "AVFOUNDATION"

        class FakeCV2:
            CAP_AVFOUNDATION = 1200

            @staticmethod
            def VideoCapture(index, backend):
                calls.append((index, backend))
                return Capture()

        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.platform.system",
            return_value="Darwin",
        ):
            with patch(
                "component3.backend.comp3_reco_navigation.navigation.camera_scanner.importlib.import_module",
                return_value=FakeCV2,
            ):
                result = probe_camera_devices((3,))
        self.assertEqual(calls, [(3, 1200)])
        self.assertTrue(result[0]["frame_read"])

    def test_camera_index_validation_rejects_boolean_and_negative_values(self) -> None:
        scanner = CameraScanner()
        for invalid in (True, -1, 1.5, "0"):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "nonnegative integer"
            ):
                scanner.start(invalid)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "nonnegative integers"):
            probe_camera_devices((0, -1))

    def test_preview_slot_is_bounded_and_stop_clears_it(self) -> None:
        """Preview transport keeps only the latest JPEG and releases it on stop."""
        class Frame:
            shape = (480, 1280, 3)

            def copy(self):
                return self

        class Encoded:
            def tobytes(self):
                return b"latest-local-jpeg"

        class PreviewCV2:
            FONT_HERSHEY_SIMPLEX = 0
            LINE_AA = 0
            IMWRITE_JPEG_QUALITY = 1

            @staticmethod
            def line(*_args):
                return None

            @staticmethod
            def putText(*_args):
                return None

            @staticmethod
            def resize(frame, _size):
                return frame

            @staticmethod
            def imencode(extension, _frame, options):
                self.assertEqual(extension, ".jpg")
                self.assertEqual(options, [1, 72])
                return True, Encoded()

        scanner = CameraScanner()
        scanner._update_preview(
            PreviewCV2,
            Frame(),
            (AprilTagDetection(201, ((1.0, 2.0), (3.0, 2.0), (3.0, 4.0), (1.0, 4.0))),),
        )
        frame, sequence = scanner.preview()
        self.assertEqual(frame, b"latest-local-jpeg")
        self.assertEqual(sequence, 1)
        self.assertTrue(scanner.snapshot()["preview_available"])
        stopped = scanner.stop()
        self.assertFalse(stopped["preview_available"])
        self.assertEqual(scanner.preview()[0], None)

    def test_smoke_test_keyboard_interrupt_stops_without_traceback(self) -> None:
        """Ctrl+C runs scanner shutdown and returns normally from the CLI."""
        class FakeScanner:
            def __init__(self, **kwargs) -> None:
                self.stopped = False

            def start(self, camera_index: int) -> dict:
                return {"connection": "connected"}

            def snapshot(self) -> dict:
                return {"scanning": True}

            def stop(self) -> dict:
                self.stopped = True
                return {
                    "connection": "stopped",
                    "scanning": False,
                    "frames_processed": 0,
                }

        class FakeScannerFactory:
            DEFAULT_MAX_CONSECUTIVE_READ_FAILURES = 5
            DEFAULT_READ_RECOVERY_TIMEOUT_S = 2.0
            DEFAULT_MAX_FPS = 15.0
            MAX_ALLOWED_FPS = 60.0

            def __init__(self, scanner: FakeScanner) -> None:
                self.scanner = scanner

            def __call__(self, **kwargs) -> FakeScanner:
                return self.scanner

        fake_scanner = FakeScanner()
        scanner_factory = FakeScannerFactory(fake_scanner)
        output = StringIO()
        with (
            patch.object(
                apriltag_camera_smoke_test,
                "CameraScanner",
                scanner_factory,
            ),
            patch(
                "sys.argv",
                [
                    "apriltag_camera_smoke_test",
                    "--camera-index",
                    "0",
                    "--no-preview",
                ],
            ),
            patch.object(
                apriltag_camera_smoke_test.time,
                "sleep",
                side_effect=KeyboardInterrupt,
            ),
            redirect_stdout(output),
        ):
            result = apriltag_camera_smoke_test.main()
        self.assertEqual(result, 0)
        self.assertTrue(fake_scanner.stopped)
        self.assertNotIn("Traceback", output.getvalue())

    def test_mocked_camera_submits_one_stable_detection_and_releases(self) -> None:
        capture = _FakeCapture()
        submitted = threading.Event()
        calls: list[int] = []

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                self.assertEqual(index, 2)
                return capture

        def callback(tag_id: int, timestamp_s: float):
            calls.append(tag_id)
            submitted.set()
            return {
                "observed_checkpoint": {
                    "accepted": True,
                    "reason": "accepted",
                    "expected_checkpoint_id": 201,
                },
                "guidance": {"instruction_type": "CHECKPOINT_CONFIRMED"},
            }

        detection = AprilTagDetection(201, ((0.0, 0.0),) * 4)
        scanner = CameraScanner(callback=callback, required_frames=3)
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(detection,),
        ):
            self.assertEqual(scanner.start(2)["connection"], "connected")
            self.assertTrue(submitted.wait(1.0))
            stopped = scanner.stop()
        self.assertEqual(calls, [201])
        self.assertTrue(capture.released)
        self.assertEqual(stopped["scan_events"][0]["detected_tag_id"], 201)
        self.assertTrue(stopped["scan_events"][0]["accepted"])

    def test_unavailable_mocked_camera_reports_error_without_callback(self) -> None:
        capture = _FakeCapture(opened=False)

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        scanner = CameraScanner(callback=lambda *_: self.fail("callback must not run"))
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ):
            state = scanner.start(0)
        self.assertEqual(state["connection"], "unavailable")
        self.assertIn("permission", state["error"])
        self.assertIn("Refresh Cameras", state["error"])
        self.assertTrue(capture.released)

    def test_switch_releases_previous_capture_before_opening_next(self) -> None:
        captures: list[tuple[int, _FakeCapture]] = []

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                if captures:
                    self.assertTrue(captures[-1][1].released)
                capture = _FakeCapture()
                captures.append((index, capture))
                return capture

        scanner = CameraScanner(max_fps=60)
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(),
        ):
            self.assertEqual(scanner.start(0, "MacBook Camera")["camera_index"], 0)
            switched = scanner.switch(2, "iPhone Camera")
            self.assertEqual(switched["camera_index"], 2)
            self.assertEqual(switched["device_name"], "iPhone Camera")
            scanner.stop()
        self.assertEqual([index for index, _ in captures], [0, 2])
        self.assertTrue(all(capture.released for _, capture in captures))

    def test_multiple_tags_never_form_a_candidate(self) -> None:
        consensus = DetectionConsensus(required_frames=2)
        for _ in range(5):
            self.assertIsNone(consensus.update([200, 201]))
        self.assertEqual(consensus.count, 0)

    def test_blurred_or_empty_frames_rearm_but_never_submit(self) -> None:
        consensus = DetectionConsensus(required_frames=2, release_frames=2)
        self.assertIsNone(consensus.update([]))
        self.assertIsNone(consensus.update([]))
        self.assertIsNone(consensus.update([]))

    def test_single_frame_read_failure_recovers_without_submitting_gap(self) -> None:
        """A transient failure waits, resets consensus, then needs three frames."""
        capture = _SequencedCapture([True, True, False, True, True, True])
        detected_frames = []
        submissions = []
        submitted = threading.Event()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        def detect(frame):
            detected_frames.append(frame)
            return (AprilTagDetection(200, ((0.0, 0.0),) * 4),)

        def callback(tag_id, timestamp_s):
            submissions.append(tag_id)
            submitted.set()
            return {"observed_checkpoint": {"accepted": False, "reason": "unknown_tag"}}

        scanner = CameraScanner(
            callback=callback,
            max_consecutive_read_failures=3,
            read_recovery_timeout_s=1.0,
            max_fps=60,
        )
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            side_effect=detect,
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            self.assertTrue(submitted.wait(2.0))
            state = scanner.stop()
        self.assertEqual(state["connection"], "stopped")
        self.assertEqual(submissions, [200])
        self.assertEqual(state["frame_read_recoveries"], 1)
        self.assertEqual(state["consecutive_read_failures"], 0)
        self.assertEqual(state["frames_processed"], 5)
        self.assertEqual(len(detected_frames), 5)
        self.assertEqual(state["scan_events"][0]["event"], "frame_read_recovered")
        self.assertTrue(capture.released)

    def test_several_frame_failures_recover_with_one_bounded_warning(self) -> None:
        """Multiple short read failures recover without terminating scanning."""
        capture = _SequencedCapture([False, False, True, True, True])
        submissions = []
        submitted = threading.Event()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        detection = AprilTagDetection(201, ((0.0, 0.0),) * 4)

        def callback(tag_id, timestamp_s):
            submissions.append(tag_id)
            submitted.set()
            return None

        scanner = CameraScanner(
            callback=callback,
            max_consecutive_read_failures=4,
            read_recovery_timeout_s=1.0,
            max_fps=60,
        )
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(detection,),
        ), self.assertLogs("component3.camera_scanner", level="WARNING") as logs:
            self.assertEqual(scanner.start(0)["connection"], "connected")
            self.assertTrue(submitted.wait(2.0))
            state = scanner.stop()
        self.assertEqual(state["connection"], "stopped")
        self.assertEqual(state["frame_read_recoveries"], 1)
        self.assertEqual(state["frames_processed"], 3)
        self.assertEqual(submissions, [201])
        self.assertEqual(len(logs.records), 1)
        self.assertIn("waiting for recovery", logs.records[0].getMessage())
        self.assertTrue(capture.released)

    def test_sustained_frame_loss_disconnects_and_notifies_navigation(self) -> None:
        """Sustained failures disconnect once, release capture, and notify caller."""
        capture = _SequencedCapture([False] * 5)
        detector_calls = []
        submissions = []
        disconnected = threading.Event()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        def disconnect():
            disconnected.set()

        scanner = CameraScanner(
            callback=lambda *args: submissions.append(args),
            max_consecutive_read_failures=3,
            read_recovery_timeout_s=10.0,
            disconnect_callback=disconnect,
        )
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            side_effect=lambda frame: detector_calls.append(frame),
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            self.assertTrue(disconnected.wait(2.0))
            state = scanner.stop()
        self.assertEqual(state["connection"], "disconnected")
        self.assertFalse(state["preview_available"])
        self.assertIsNone(scanner.preview()[0])
        self.assertFalse(state["scanning"])
        self.assertIn("did not recover", state["error"])
        self.assertEqual(state["frames_processed"], 0)
        self.assertEqual(state["frame_read_recoveries"], 0)
        self.assertEqual(detector_calls, [])
        self.assertEqual(submissions, [])
        self.assertTrue(capture.released)

    def test_failure_after_submitted_tag_preserves_duplicate_suppression(self) -> None:
        """A camera gap clears partial consensus but does not rearm seen tags."""
        capture = _SequencedCapture([True, True, True, False, True, True, True])
        submissions = []
        submitted_twice = threading.Event()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        detection = AprilTagDetection(202, ((0.0, 0.0),) * 4)

        def callback(tag_id, timestamp_s):
            submissions.append(tag_id)
            submitted_twice.set() if len(submissions) > 1 else None
            return None

        scanner = CameraScanner(
            callback=callback,
            max_consecutive_read_failures=3,
            read_recovery_timeout_s=1.0,
            max_fps=60,
        )
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(detection,),
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            deadline = time.monotonic() + 1.0
            while scanner.snapshot()["frames_processed"] < 6 and time.monotonic() < deadline:
                time.sleep(0.01)
            state = scanner.stop()
        self.assertFalse(submitted_twice.is_set())
        self.assertEqual(submissions, [202])
        self.assertFalse(state["armed"])
        self.assertTrue(capture.released)

    def test_detection_error_is_reported_without_success_shaped_fallback(self) -> None:
        """Detector failures are surfaced instead of looking like an empty scan."""
        capture = _FakeCapture()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        scanner = CameraScanner(callback=lambda *_: self.fail("callback must not run"))
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            side_effect=RuntimeError("detector failed"),
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            deadline = time.monotonic() + 1.0
            while scanner.snapshot()["connection"] != "error" and time.monotonic() < deadline:
                time.sleep(0.01)
            state = scanner.stop()
        self.assertEqual(state["connection"], "error")
        self.assertEqual(state["error"], "detector failed")
        self.assertTrue(capture.released)

    def test_read_recovery_timeout_disconnects_before_failure_count_limit(self) -> None:
        """The elapsed recovery bound independently terminates a dead camera."""
        class SlowFailedCapture(_FakeCapture):
            def read(self) -> tuple[bool, None]:
                time.sleep(0.07)
                return False, None

        capture = SlowFailedCapture()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        scanner = CameraScanner(
            max_consecutive_read_failures=10,
            read_recovery_timeout_s=0.12,
        )
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            deadline = time.monotonic() + 2.0
            while scanner.snapshot()["connection"] != "disconnected" and time.monotonic() < deadline:
                time.sleep(0.01)
            state = scanner.stop()
        self.assertEqual(state["connection"], "disconnected")
        self.assertIn("Camera frame reads did not recover", state["error"])
        self.assertTrue(capture.released)

    def test_frame_processing_rate_respects_configured_limit(self) -> None:
        """The scanner throttles valid frame processing to its configured FPS."""
        capture = _FakeCapture()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        scanner = CameraScanner(max_fps=10)
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(),
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            time.sleep(0.36)
            state = scanner.stop()
        self.assertGreaterEqual(state["frames_processed"], 2)
        self.assertLessEqual(state["frames_processed"], 5)
        self.assertTrue(capture.released)

    def test_shutdown_releases_capture_only_after_worker_finishes_reading(self) -> None:
        """The capture owner releases only after its in-flight read returns."""
        read_started = threading.Event()
        finish_read = threading.Event()

        class BlockingCapture(_FakeCapture):
            def read(self):
                read_started.set()
                finish_read.wait(1.0)
                return True, object()

        capture = BlockingCapture()

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                return capture

        scanner = CameraScanner()
        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner._load_aruco",
            return_value=(FakeCV2, object()),
        ), patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(),
        ):
            self.assertEqual(scanner.start(0)["connection"], "connected")
            self.assertTrue(read_started.wait(1.0))
            result: list[dict] = []
            stopper = threading.Thread(target=lambda: result.append(scanner.stop()))
            stopper.start()
            time.sleep(0.05)
            self.assertFalse(capture.released)
            finish_read.set()
            stopper.join(1.0)
        self.assertFalse(stopper.is_alive())
        self.assertTrue(capture.released)
        self.assertEqual(result[0]["connection"], "stopped")

    def test_camera_probe_reports_frame_metadata_and_releases_before_next_index(self) -> None:
        """The device probe reports metadata and releases each index in order."""
        captures: list[_FakeCapture] = []

        class ProbeCapture(_FakeCapture):
            def read(self):
                return True, SimpleNamespace(shape=(480, 640, 3))

            def getBackendName(self):
                return "AVFOUNDATION"

        class FakeCV2:
            @staticmethod
            def VideoCapture(index):
                if captures:
                    self.assertTrue(captures[-1].released)
                capture = ProbeCapture()
                captures.append(capture)
                return capture

        with patch(
            "component3.backend.comp3_reco_navigation.navigation.camera_scanner.importlib.import_module",
            return_value=FakeCV2,
        ):
            results = probe_camera_devices((0, 1))
        self.assertEqual(len(captures), 2)
        self.assertTrue(all(capture.released for capture in captures))
        self.assertEqual(results[0]["camera_index"], 0)
        self.assertTrue(results[0]["opened"])
        self.assertTrue(results[0]["frame_read"])
        self.assertEqual(results[0]["frame_dimensions"], [640, 480])
        self.assertEqual(results[0]["backend"], "AVFOUNDATION")


if __name__ == "__main__":
    unittest.main()
