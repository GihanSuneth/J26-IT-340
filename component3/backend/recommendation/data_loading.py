"""Load and verify frozen Phase 8A recommendation artifacts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Sequence

from .preprocess import Basket, BasketItem, sha256_file


EXPECTED_RAW_SHA256 = "0cd3a4d7d66dec3e7ce6fb1031b095740fb180b9e5fa46ce8bbb9f26f763ae57"
EXPECTED_COUNTS = {"train": 1393, "validation": 297, "test": 299, "purged_duplicate": 2}


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    basket_id: str
    timestamp: str
    split: str
    observed: tuple[str, ...]
    target: str


def load_baskets(path: Path) -> list[Basket]:
    baskets: list[Basket] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = json.loads(line)
        items = tuple(BasketItem(
            item_key=item["item_key"], product_name=item["product_name"], category=item["category"],
            quantity=int(item["quantity"]), source_product_ids=tuple(item["source_product_ids"]),
            line_count=int(item["line_count"]),
        ) for item in value["items"])
        if not items:
            raise ValueError(f"empty basket at line {line_number}")
        baskets.append(Basket(
            basket_id=value["basket_id"], timestamp=datetime.fromisoformat(value["timestamp"]),
            source_user_id="not_exported", items=items, source_line_count=int(value["source_line_count"]),
        ))
    return baskets


def load_cases(path: Path) -> list[EvaluationCase]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    return [EvaluationCase(
        basket_id=row["basket_id"], timestamp=row["timestamp"], split=row["split"],
        observed=tuple(filter(None, row["observed_item_keys"].split("|"))),
        target=row["hidden_target_item_key"],
    ) for row in rows]


def verify_phase8a(
    baskets: Sequence[Basket], cases: Sequence[EvaluationCase], raw_path: Path,
) -> dict[str, object]:
    counts = {label: sum(case.split == label for case in cases) for label in EXPECTED_COUNTS}
    vocabulary = {item.item_key for basket in baskets for item in basket.items}
    basket_by_id = {basket.basket_id: basket for basket in baskets}
    errors: list[str] = []
    if len(baskets) != 1991:
        errors.append(f"expected 1991 baskets, found {len(baskets)}")
    if len(vocabulary) != 68:
        errors.append(f"expected 68 products, found {len(vocabulary)}")
    if counts != EXPECTED_COUNTS:
        errors.append(f"unexpected split counts: {counts}")
    if sha256_file(raw_path) != EXPECTED_RAW_SHA256:
        errors.append("raw checksum mismatch")
    if len({case.basket_id for case in cases}) != len(cases):
        errors.append("duplicate transaction assignment")
    target_leaks = [case.basket_id for case in cases if case.target in case.observed]
    if target_leaks:
        errors.append(f"hidden target included in observed input: {target_leaks[:5]}")
    for case in cases:
        expected_items = basket_by_id[case.basket_id].signature
        if tuple(sorted((*case.observed, case.target))) != expected_items:
            errors.append(f"assignment does not reconstruct basket {case.basket_id}")
            break
    signatures: dict[str, set[tuple[str, ...]]] = {}
    for split in ("train", "validation", "test"):
        signatures[split] = {
            basket_by_id[case.basket_id].signature for case in cases if case.split == split
        }
    cross_split_overlap = {
        "train_validation": len(signatures["train"] & signatures["validation"]),
        "train_test": len(signatures["train"] & signatures["test"]),
        "validation_test": len(signatures["validation"] & signatures["test"]),
    }
    if any(cross_split_overlap.values()):
        errors.append(f"cross-split basket-signature overlap: {cross_split_overlap}")
    purged_audit = []
    for case in (entry for entry in cases if entry.split == "purged_duplicate"):
        signature = basket_by_id[case.basket_id].signature
        earlier = [
            other for other in cases
            if other.split in {"train", "validation"}
            and basket_by_id[other.basket_id].signature == signature
            and other.timestamp < case.timestamp
        ]
        purged_audit.append({
            "basket_id": case.basket_id, "timestamp": case.timestamp,
            "signature": list(signature),
            "earlier_matching_transactions": [
                {"basket_id": other.basket_id, "timestamp": other.timestamp} for other in earlier
            ],
            "confirmed_duplicate_record": False,
            "assessment": "Distinct transaction ID and timestamp; likely legitimate repeated item set, conservatively purged to enforce signature isolation.",
        })
    result = {
        "verified": not errors, "errors": errors, "basket_count": len(baskets),
        "vocabulary_size": len(vocabulary), "split_counts": counts,
        "raw_sha256": sha256_file(raw_path), "target_leak_count": len(target_leaks),
        "cross_split_signature_overlap": cross_split_overlap,
        "train_start": min(case.timestamp for case in cases if case.split == "train"),
        "train_end": max(case.timestamp for case in cases if case.split == "train"),
        "validation_start": min(case.timestamp for case in cases if case.split == "validation"),
        "validation_end": max(case.timestamp for case in cases if case.split == "validation"),
        "test_start": min(case.timestamp for case in cases if case.split == "test"),
        "test_end": max(case.timestamp for case in cases if case.split == "test"),
        "purged_transaction_audit": purged_audit,
        "provenance_classification": "UNKNOWN PROVENANCE",
    }
    if errors:
        raise ValueError("Phase 8A verification failed: " + "; ".join(errors))
    return result
