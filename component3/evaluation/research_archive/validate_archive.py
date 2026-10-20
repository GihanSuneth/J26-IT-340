"""Validate research-archive index uniqueness and referenced local artifacts."""

from __future__ import annotations

import csv
from pathlib import Path


HEADERS = ("evidence_id", "date", "area", "title", "path", "status", "claim_boundary")
ARCHIVE = Path(__file__).resolve().parent
REPOSITORY = ARCHIVE.parents[2]


def main() -> int:
    errors: list[str] = []
    with (ARCHIVE / "evidence_index.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != HEADERS:
            errors.append("unexpected evidence-index headers")
        rows = list(reader)
    identifiers = [row["evidence_id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        errors.append("duplicate evidence ID")
    for row in rows:
        if not (REPOSITORY / row["path"]).is_file():
            errors.append(f"missing artifact: {row['path']}")
        if not row["claim_boundary"].strip():
            errors.append(f"empty claim boundary: {row['evidence_id']}")
    if errors:
        print("Research archive validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Research archive is valid; {len(rows)} indexed artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
