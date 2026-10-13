"""Tests for offline AprilTag detection and checkpoint localization."""

from __future__ import annotations

import argparse
from datetime import datetime
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from component3.backend.comp3_reco_navigation.navigation.apriltag import (
    EXPECTED_FAMILY,
    AprilTagLayout,
    AprilTagLayoutError,
    ImageReadError,
    detect_apriltags,
    load_apriltag_layout,
    localize_detections,
    localize_marker_ids,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import load_store_graph


try:
    import cv2
    import numpy as np

    ARUCO_AVAILABLE = bool(
        hasattr(cv2, "aruco")
        and hasattr(cv2.aruco, "DICT_APRILTAG_36h11")
        and (hasattr(cv2.aruco, "generateImageMarker") or hasattr(cv2.aruco, "drawMarker"))
        and (hasattr(cv2.aruco, "ArucoDetector") or hasattr(cv2.aruco, "detectMarkers"))
    )
except ModuleNotFoundError:
    cv2 = None
    np = None
    ARUCO_AVAILABLE = False


DETECTION_SKIP_REASON = "cv2 with tag36h11 ArUco generation/detection is not installed"


def _layout_dict() -> dict:
    path = Path(__file__).resolve().parents[3] / "data/store_map/apriltag_layout.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _marker_image(marker_id: int, marker_pixels: int = 240, canvas: int = 400):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    if hasattr(cv2.aruco, "generateImageMarker"):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_pixels)
    else:
        marker = cv2.aruco.drawMarker(dictionary, marker_id, marker_pixels)
    image = np.full((canvas, canvas), 255, dtype=np.uint8)
    offset = (canvas - marker_pixels) // 2
    image[offset : offset + marker_pixels, offset : offset + marker_pixels] = marker
    return image


@unittest.skipUnless(ARUCO_AVAILABLE, DETECTION_SKIP_REASON)
class OpenCVDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory(prefix="comp3-tags-")
        cls.root = Path(cls.temp_directory.name)
        cls.layout = load_apriltag_layout()
        cls.single = cls.root / "single_100.png"
        cv2.imwrite(str(cls.single), _marker_image(100))

        multiple_image = np.full((500, 900), 255, dtype=np.uint8)
        for marker_id, x in ((100, 60), (110, 350), (115, 640)):
            marker = _marker_image(marker_id, 180, 260)[40:220, 40:220]
            multiple_image[150:330, x : x + 180] = marker
        cls.multiple = cls.root / "multiple_100_110_115.png"
        cv2.imwrite(str(cls.multiple), multiple_image)

        cls.unknown = cls.root / "unknown_42.png"
        cv2.imwrite(str(cls.unknown), _marker_image(42))
        cls.blank = cls.root / "blank.png"
        cv2.imwrite(str(cls.blank), np.full((400, 400), 255, dtype=np.uint8))
        cls.rotated = cls.root / "rotated_100.png"
        cv2.imwrite(str(cls.rotated), cv2.rotate(_marker_image(100), cv2.ROTATE_90_CLOCKWISE))

        source = np.float32([[80, 80], [319, 80], [319, 319], [80, 319]])
        destination = np.float32([[95, 65], [325, 92], [300, 330], [70, 300]])
        transform = cv2.getPerspectiveTransform(source, destination)
        cls.perspective = cls.root / "perspective_100.png"
        cv2.imwrite(
            str(cls.perspective),
            cv2.warpPerspective(_marker_image(100), transform, (400, 400), borderValue=255),
        )
        cls.reduced = cls.root / "reduced_100.png"
        cv2.imwrite(str(cls.reduced), _marker_image(100, 80, 180))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_directory.cleanup()

    def test_10_generated_valid_marker(self) -> None:
        self.assertEqual([item.marker_id for item in detect_apriltags(self.single)], [100])

    def test_11_multiple_markers(self) -> None:
        self.assertEqual(
            [item.marker_id for item in detect_apriltags(self.multiple)], [100, 110, 115]
        )

    def test_12_unknown_valid_tag_without_location(self) -> None:
        detections = detect_apriltags(self.unknown)
        self.assertEqual([item.marker_id for item in detections], [42])
        self.assertFalse(localize_detections(detections, self.layout)[0].is_known_checkpoint)

    def test_13_blank_image(self) -> None:
        self.assertEqual(detect_apriltags(self.blank), ())

    def test_14_rotated_marker(self) -> None:
        self.assertEqual([item.marker_id for item in detect_apriltags(self.rotated)], [100])

    def test_15_perspective_distorted_marker(self) -> None:
        self.assertEqual([item.marker_id for item in detect_apriltags(self.perspective)], [100])

    def test_16_reduced_resolution_marker(self) -> None:
        self.assertEqual([item.marker_id for item in detect_apriltags(self.reduced)], [100])

    def test_18_deterministic_repeatability(self) -> None:
        self.assertEqual(detect_apriltags(self.multiple), detect_apriltags(self.multiple))


class CheckpointMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_store_graph()
        cls.layout = load_apriltag_layout(graph=cls.graph)

    def test_01_valid_layout_loading(self) -> None:
        self.assertEqual(self.layout.family, EXPECTED_FAMILY)

    def test_02_eight_unique_checkpoint_ids(self) -> None:
        self.assertEqual(self.layout.tag_ids, (100, 101, 110, 111, 112, 113, 114, 115))

    def test_03_correct_tag_to_node_mapping(self) -> None:
        expected = {
            100: "ENT", 101: "CHK", 110: "B1", 111: "B2",
            112: "B3", 113: "B4", 114: "B5", 115: "B6",
        }
        self.assertEqual(
            {tag_id: item.node_id for tag_id, item in self.layout.checkpoints.items()},
            expected,
        )

    def test_04_correct_xy_coordinate_lookup(self) -> None:
        checkpoint = self.layout.checkpoint_for(114)
        self.assertIsNotNone(checkpoint)
        self.assertEqual((checkpoint.x_m, checkpoint.y_m), (17.4, 3.0))

    def test_05_unknown_marker_id(self) -> None:
        result = localize_marker_ids([42], self.layout)
        self.assertEqual(result[0].marker_id, 42)
        self.assertIsNone(result[0].checkpoint)

    def test_06_no_detection_handling(self) -> None:
        self.assertEqual(localize_marker_ids([], self.layout), ())

    def test_07_duplicate_detection_handling(self) -> None:
        result = localize_marker_ids([100, 100, 999, 999], self.layout)
        self.assertEqual([item.marker_id for item in result], [100, 999])
        self.assertTrue(result[0].is_known_checkpoint)
        self.assertFalse(result[1].is_known_checkpoint)

    def test_08_invalid_layout_references(self) -> None:
        data = _layout_dict()
        data["tags"][0]["node_id"] = "UNKNOWN"
        with self.assertRaisesRegex(AprilTagLayoutError, "unknown graph node"):
            AprilTagLayout.from_dict(data, self.graph)

    def test_09_wrong_apriltag_family(self) -> None:
        data = _layout_dict()
        data["family"] = "tag25h9"
        with self.assertRaisesRegex(AprilTagLayoutError, "tag36h11"):
            AprilTagLayout.from_dict(data, self.graph)

    def test_17_missing_image(self) -> None:
        with self.assertRaisesRegex(ImageReadError, "does not exist"):
            detect_apriltags("definitely-missing-apriltag-image.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    body = stream.getvalue()
    passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
    report = (
        "Component 3 Offline AprilTag Test Execution\n"
        "============================================\n"
        f"Executed: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"Python: {sys.version.split()[0]}\n"
        f"OpenCV available: {ARUCO_AVAILABLE}\n"
        "Required detector: cv2.aruco.DICT_APRILTAG_36h11\n"
        f"Command: {sys.executable} -B -m "
        "component3.backend.comp3_reco_navigation.tests.test_apriltag "
        "--output component3/evaluation/test_results/apriltag_tests.txt\n"
        "Framework: Python standard-library unittest\n\n"
        f"{body}\n"
        f"Tests executed: {result.testsRun}\n"
        f"Passed: {passed}\n"
        f"Skipped: {len(result.skipped)}\n"
        f"Failed: {len(result.failures)}\n"
        f"Errors: {len(result.errors)}\n"
        f"Overall runnable-test result: {'PASS' if result.wasSuccessful() else 'FAIL'}\n"
        f"Detection evaluation status: {'READY' if ARUCO_AVAILABLE else 'BLOCKED'}\n"
    )
    print(report, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
