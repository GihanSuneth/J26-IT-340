"""Generate deterministic synthetic tag36h11 fixtures for offline evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "component3/data/apriltag_test_images"
CHECKPOINT_IDS = (100, 101, 110, 111, 112, 113, 114, 115)
DICTIONARY_NAME = "DICT_APRILTAG_36h11"
MARKER_PIXELS = 320
CANVAS_PIXELS = 512
WHITE_MARGIN_PIXELS = (CANVAS_PIXELS - MARKER_PIXELS) // 2


def marker_image(marker_id: int, marker_pixels: int, canvas_pixels: int) -> np.ndarray:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_pixels)
    canvas = np.full((canvas_pixels, canvas_pixels), 255, dtype=np.uint8)
    offset = (canvas_pixels - marker_pixels) // 2
    canvas[offset : offset + marker_pixels, offset : offset + marker_pixels] = marker
    return canvas


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"OpenCV could not write image: {path}")


def generate(output: Path) -> dict:
    clean = output / "clean"
    transformed = output / "transformed"
    cases: list[dict[str, object]] = []

    for marker_id in CHECKPOINT_IDS:
        path = clean / f"tag_{marker_id}.png"
        write_image(path, marker_image(marker_id, MARKER_PIXELS, CANVAS_PIXELS))
        cases.append(
            {
                "image": str(path.relative_to(REPOSITORY_ROOT)),
                "expected_ids": [marker_id],
                "category": "clean",
            }
        )

    multi = np.full((600, 1200), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    for marker_id, x in ((100, 100), (110, 480), (115, 860)):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 240)
        multi[180:420, x : x + 240] = marker
    multi_path = transformed / "multiple_100_110_115.png"
    write_image(multi_path, multi)
    cases.append(
        {
            "image": str(multi_path.relative_to(REPOSITORY_ROOT)),
            "expected_ids": [100, 110, 115],
            "category": "multiple",
        }
    )

    unknown_path = transformed / "unknown_tag_42.png"
    write_image(unknown_path, marker_image(42, MARKER_PIXELS, CANVAS_PIXELS))
    cases.append(
        {
            "image": str(unknown_path.relative_to(REPOSITORY_ROOT)),
            "expected_ids": [42],
            "category": "unknown_valid_id",
        }
    )

    blank_path = transformed / "blank.png"
    write_image(blank_path, np.full((CANVAS_PIXELS, CANVAS_PIXELS), 255, dtype=np.uint8))
    cases.append(
        {
            "image": str(blank_path.relative_to(REPOSITORY_ROOT)),
            "expected_ids": [],
            "category": "no_marker",
        }
    )

    base = marker_image(100, MARKER_PIXELS, CANVAS_PIXELS)
    rotated_path = transformed / "rotated_90_tag_100.png"
    write_image(rotated_path, cv2.rotate(base, cv2.ROTATE_90_CLOCKWISE))
    cases.append(
        {
            "image": str(rotated_path.relative_to(REPOSITORY_ROOT)),
            "expected_ids": [100],
            "category": "rotated_90_degrees",
        }
    )

    source = np.float32([[96, 96], [415, 96], [415, 415], [96, 415]])
    destination = np.float32([[120, 70], [425, 115], [380, 440], [70, 390]])
    transform = cv2.getPerspectiveTransform(source, destination)
    perspective_path = transformed / "perspective_tag_100.png"
    perspective = cv2.warpPerspective(base, transform, (512, 512), borderValue=255)
    write_image(perspective_path, perspective)
    cases.append(
        {
            "image": str(perspective_path.relative_to(REPOSITORY_ROOT)),
            "expected_ids": [100],
            "category": "fixed_perspective_transform",
        }
    )

    reduced_path = transformed / "reduced_resolution_tag_100.png"
    write_image(reduced_path, marker_image(100, 80, 180))
    cases.append(
        {
            "image": str(reduced_path.relative_to(REPOSITORY_ROOT)),
            "expected_ids": [100],
            "category": "reduced_resolution",
        }
    )

    manifest = {
        "schema_version": "1.0",
        "synthetic_fixture_notice": "Generated markers are controlled test fixtures, not physical camera captures.",
        "opencv_version": cv2.__version__,
        "dictionary": DICTIONARY_NAME,
        "checkpoint_ids": list(CHECKPOINT_IDS),
        "clean_marker_pixels": MARKER_PIXELS,
        "clean_canvas_pixels": CANVAS_PIXELS,
        "clean_white_margin_pixels": WHITE_MARGIN_PIXELS,
        "random_seed": None,
        "randomness_used": False,
        "cases": cases,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = generate(args.output_dir)
    print(f"OpenCV: {cv2.__version__}")
    print(f"Dictionary: {manifest['dictionary']}")
    print(f"Generated cases: {len(manifest['cases'])}")
    print(f"Output: {args.output_dir.relative_to(REPOSITORY_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
