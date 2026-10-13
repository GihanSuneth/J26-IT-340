"""Evaluate offline AprilTag detection on deterministic synthetic fixtures."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from .apriltag import (
    AprilTagDetection,
    CheckpointLocalization,
    detect_apriltags,
    load_apriltag_layout,
    localize_detections,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "component3/data/apriltag_test_images/manifest.json"
DEFAULT_LOG = REPOSITORY_ROOT / "component3/evaluation/logs/apriltag_offline_demo.txt"
DEFAULT_METRICS = REPOSITORY_ROOT / "component3/evaluation/metrics/apriltag_offline_evaluation.csv"
DEFAULT_SCREENSHOTS = REPOSITORY_ROOT / "component3/docs/research_evidence/03_apriltag_detection/screenshots"


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    image_path: Path
    category: str
    expected_ids: tuple[int, ...]
    detections: tuple[AprilTagDetection, ...]
    localizations: tuple[CheckpointLocalization, ...]

    @property
    def detected_ids(self) -> tuple[int, ...]:
        return tuple(item.marker_id for item in self.detections)

    @property
    def correctly_detected_ids(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.expected_ids) & set(self.detected_ids)))

    @property
    def missed_ids(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.expected_ids) - set(self.detected_ids)))

    @property
    def unexpected_ids(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.detected_ids) - set(self.expected_ids)))

    @property
    def succeeded(self) -> bool:
        return not self.missed_ids and not self.unexpected_ids


def evaluate(manifest_path: Path) -> tuple[dict, tuple[EvaluationResult, ...]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layout = load_apriltag_layout()
    results: list[EvaluationResult] = []
    for case in manifest["cases"]:
        path = REPOSITORY_ROOT / case["image"]
        detections = detect_apriltags(path)
        results.append(
            EvaluationResult(
                path,
                case["category"],
                tuple(case["expected_ids"]),
                detections,
                localize_detections(detections, layout),
            )
        )
    return manifest, tuple(results)


def _ids(values: tuple[int, ...]) -> str:
    return "|".join(str(value) for value in values)


def _mappings(result: EvaluationResult) -> str:
    values = []
    for item in result.localizations:
        if item.checkpoint is None:
            values.append(f"{item.marker_id}:UNKNOWN")
        else:
            checkpoint = item.checkpoint
            values.append(
                f"{item.marker_id}:{checkpoint.node_id}@({checkpoint.x_m:.2f},{checkpoint.y_m:.2f})"
            )
    return "|".join(values)


def write_metrics(path: Path, results: tuple[EvaluationResult, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "test_image", "expected_marker_ids", "detected_marker_ids",
        "correctly_detected_ids", "missed_ids", "unexpected_ids",
        "checkpoint_mapping", "detection_success", "transformation_category",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "test_image": str(result.image_path.relative_to(REPOSITORY_ROOT)),
                    "expected_marker_ids": _ids(result.expected_ids),
                    "detected_marker_ids": _ids(result.detected_ids),
                    "correctly_detected_ids": _ids(result.correctly_detected_ids),
                    "missed_ids": _ids(result.missed_ids),
                    "unexpected_ids": _ids(result.unexpected_ids),
                    "checkpoint_mapping": _mappings(result),
                    "detection_success": str(result.succeeded).lower(),
                    "transformation_category": result.category,
                }
            )


def format_report(manifest: dict, results: tuple[EvaluationResult, ...]) -> str:
    expected_count = sum(len(item.expected_ids) for item in results)
    correct_count = sum(len(item.correctly_detected_ids) for item in results)
    successful_cases = sum(item.succeeded for item in results)
    lines = [
        "Component 3 Offline AprilTag Evaluation",
        "========================================",
        f"Executed: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Python: {sys.version.split()[0]}",
        f"OpenCV: {cv2.__version__}",
        f"Dictionary: {manifest['dictionary']}",
        "Detector API: cv2.aruco.ArucoDetector.detectMarkers",
        f"Synthetic cases: {len(results)}",
        "Notice: controlled synthetic fixtures; not physical-camera accuracy.",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"[{result.image_path.name} — {result.category}]",
                f"Expected IDs: {_ids(result.expected_ids) or 'none'}",
                f"Detected IDs: {_ids(result.detected_ids) or 'none'}",
                f"Correct IDs: {_ids(result.correctly_detected_ids) or 'none'}",
                f"Missed IDs: {_ids(result.missed_ids) or 'none'}",
                f"Unexpected IDs: {_ids(result.unexpected_ids) or 'none'}",
                f"Checkpoint mapping: {_mappings(result) or 'none'}",
                f"Exact case success: {result.succeeded}",
                "",
            ]
        )
    recall = correct_count / expected_count * 100 if expected_count else 0.0
    case_rate = successful_cases / len(results) * 100 if results else 0.0
    lines.extend(
        [
            "Summary",
            f"Successful cases: {successful_cases}/{len(results)} ({case_rate:.2f}%)",
            f"Expected marker detections: {expected_count}",
            f"Correct marker detections: {correct_count}",
            f"Synthetic marker recall: {recall:.2f}%",
            f"Total missed IDs: {sum(len(item.missed_ids) for item in results)}",
            f"Total unexpected IDs: {sum(len(item.unexpected_ids) for item in results)}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_overlay(result: EvaluationResult, output: Path, title: str) -> None:
    source = cv2.imread(str(result.image_path), cv2.IMREAD_COLOR)
    if source is None:
        raise RuntimeError(f"Unable to render unreadable image: {result.image_path}")
    canvas = np.full((900, 1600, 3), 255, dtype=np.uint8)
    cv2.putText(canvas, title, (55, 62), cv2.FONT_HERSHEY_SIMPLEX, 1.25, (31, 41, 55), 3, cv2.LINE_AA)
    cv2.putText(
        canvas,
        "ACTUAL OFFLINE DETECTOR OUTPUT - SYNTHETIC FIXTURE, NOT A CAMERA CAPTURE",
        (55, 104),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 102, 180),
        2,
        cv2.LINE_AA,
    )
    max_width, max_height = 920, 690
    scale = min(max_width / source.shape[1], max_height / source.shape[0])
    resized = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    x0, y0 = 55, 145
    canvas[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized
    for detection in result.detections:
        points = np.array(
            [[int(x0 + x * scale), int(y0 + y * scale)] for x, y in detection.corners_px],
            dtype=np.int32,
        )
        cv2.polylines(canvas, [points], True, (30, 170, 50), 6, cv2.LINE_AA)
        label = (int(points[0][0]), max(135, int(points[0][1]) - 14))
        cv2.putText(canvas, f"ID {detection.marker_id}", label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 110, 25), 2, cv2.LINE_AA)

    panel_x = 1030
    cv2.putText(canvas, "Detection result", (panel_x, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (31, 41, 55), 2, cv2.LINE_AA)
    rows = [
        f"Category: {result.category}",
        f"Expected: {_ids(result.expected_ids) or 'none'}",
        f"Detected: {_ids(result.detected_ids) or 'none'}",
        f"Missed: {_ids(result.missed_ids) or 'none'}",
        f"Unexpected: {_ids(result.unexpected_ids) or 'none'}",
        f"Exact success: {result.succeeded}",
        "",
        "Checkpoint mapping",
    ]
    for index, row in enumerate(rows):
        cv2.putText(canvas, row, (panel_x, 220 + index * 42), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (45, 55, 72), 2, cv2.LINE_AA)
    y = 220 + len(rows) * 42
    for mapping in _mappings(result).split("|") if _mappings(result) else ["none"]:
        cv2.putText(canvas, mapping, (panel_x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.57, (90, 55, 170), 2, cv2.LINE_AA)
        y += 38
    cv2.putText(canvas, "Dictionary: tag36h11", (panel_x, 790), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (75, 85, 100), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"OpenCV {cv2.__version__}", (panel_x, 827), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (75, 85, 100), 2, cv2.LINE_AA)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), canvas):
        raise RuntimeError(f"OpenCV could not write evidence image: {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--screenshots", type=Path, default=DEFAULT_SCREENSHOTS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest, results = evaluate(args.manifest)
    report = format_report(manifest, results)
    print(report, end="")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(report, encoding="utf-8")
    write_metrics(args.metrics, results)

    by_name = {item.image_path.name: item for item in results}
    render_overlay(
        by_name["tag_100.png"],
        args.screenshots / "C3-TAG-001_single_marker.png",
        "Component 3 - Single AprilTag Detection",
    )
    render_overlay(
        by_name["multiple_100_110_115.png"],
        args.screenshots / "C3-TAG-002_multiple_markers.png",
        "Component 3 - Multiple AprilTag Detection",
    )
    render_overlay(
        by_name["multiple_100_110_115.png"],
        args.screenshots / "C3-TAG-003_checkpoint_mapping.png",
        "Component 3 - Detected IDs to Store Checkpoints",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
