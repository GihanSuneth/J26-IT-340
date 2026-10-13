"""Validate the Component 3 evidence structure and CSV file references."""

from __future__ import annotations

import csv
from pathlib import Path


HEADERS = [
    "evidence_id",
    "date",
    "phase",
    "title",
    "description",
    "file_path",
    "related_code",
    "test_result",
    "capture_method",
    "status",
]
PHASES = [
    "01_architecture",
    "02_store_map",
    "03_apriltag_detection",
    "04_navigation_algorithms",
    "05_position_tracking",
    "06_recommendation_engine",
    "07_cnn_training",
    "08_integration_testing",
    "09_final_evaluation",
]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = EVIDENCE_ROOT / "evidence_index.csv"


def main() -> int:
    errors: list[str] = []
    required_files = [
        EVIDENCE_ROOT / "README.md",
        EVIDENCE_ROOT / "progress_log.md",
        INDEX_PATH,
    ]
    required_directories = [
        REPOSITORY_ROOT / "component3/evaluation/test_results",
        REPOSITORY_ROOT / "component3/evaluation/metrics",
        REPOSITORY_ROOT / "component3/evaluation/logs",
    ]

    for phase in PHASES:
        required_files.append(EVIDENCE_ROOT / phase / "notes.md")
        required_directories.append(EVIDENCE_ROOT / phase / "screenshots")

    for path in required_files:
        if not path.is_file():
            errors.append(f"Missing file: {path.relative_to(REPOSITORY_ROOT)}")
    for path in required_directories:
        if not path.is_dir():
            errors.append(f"Missing directory: {path.relative_to(REPOSITORY_ROOT)}")

    seen_ids: set[str] = set()
    if INDEX_PATH.is_file():
        with INDEX_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADERS:
                errors.append("Evidence index headers do not match the required schema")
            else:
                for line_number, row in enumerate(reader, start=2):
                    evidence_id = row["evidence_id"].strip()
                    if not evidence_id:
                        errors.append(f"Line {line_number}: empty evidence ID")
                    elif evidence_id in seen_ids:
                        errors.append(f"Line {line_number}: duplicate ID {evidence_id}")
                    seen_ids.add(evidence_id)

                    evidence_path = (REPOSITORY_ROOT / row["file_path"]).resolve()
                    if not evidence_path.is_file():
                        errors.append(
                            f"Line {line_number}: missing evidence file {row['file_path']}"
                        )

    if errors:
        print("Component 3 evidence validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Component 3 evidence structure is valid; {len(seen_ids)} indexed artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
