"""Register an existing Component 3 evidence artifact in the CSV index."""

from __future__ import annotations

import argparse
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
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
INDEX_PATH = Path(__file__).resolve().parents[1] / "evidence_index.csv"


def repository_path(value: str) -> Path:
    """Resolve a repository-relative path and reject paths outside the repo."""
    candidate = (REPOSITORY_ROOT / value).resolve()
    if candidate != REPOSITORY_ROOT and REPOSITORY_ROOT not in candidate.parents:
        raise ValueError(f"Path is outside the repository: {value}")
    return candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add an existing evidence artifact to the Component 3 index."
    )
    for option in HEADERS:
        parser.add_argument(f"--{option.replace('_', '-')}", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    row = {header: getattr(args, header) for header in HEADERS}

    evidence_file = repository_path(row["file_path"])
    if not evidence_file.is_file():
        raise SystemExit(f"Evidence file does not exist: {row['file_path']}")

    for optional_reference in ("related_code", "test_result"):
        value = row[optional_reference].strip()
        if value and value.lower() not in {"n/a", "not applicable"}:
            if not repository_path(value).exists():
                raise SystemExit(f"Referenced path does not exist: {value}")

    with INDEX_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADERS:
            raise SystemExit("Evidence index headers do not match the required schema")
        existing_ids = {existing["evidence_id"] for existing in reader}

    if row["evidence_id"] in existing_ids:
        raise SystemExit(f"Duplicate evidence ID: {row['evidence_id']}")

    with INDEX_PATH.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(
            handle,
            fieldnames=HEADERS,
            lineterminator="\n",
        ).writerow(row)

    print(f"Registered {row['evidence_id']}: {row['file_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
