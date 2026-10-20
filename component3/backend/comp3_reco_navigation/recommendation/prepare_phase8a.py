"""Generate reproducible Phase 8A derived data and machine-readable evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform

from .catalog_mapping import reconcile_catalog
from .preprocess import (
    audit_dataset, basket_completion_case, chronological_split,
    read_transactions, reconstruct_baskets, sha256_file,
)


SEED = 3408
PIPELINE_VERSION = "phase8a-preparation-v1"
COMPONENT_ROOT = Path(__file__).resolve().parents[3]


def _json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare(raw_path: Path, catalog_path: Path, output_dir: Path, evidence_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    before_hash = sha256_file(raw_path)
    audit = audit_dataset(raw_path)
    lines, row_rejects = read_transactions(raw_path)
    baskets, basket_exclusions = reconstruct_baskets(lines)
    split = chronological_split(baskets)
    mappings = reconcile_catalog(baskets, catalog_path)

    cleaned_path = output_dir / "cleaned_baskets.jsonl"
    with cleaned_path.open("w", encoding="utf-8") as stream:
        for basket in baskets:
            stream.write(json.dumps(basket.to_dict(), sort_keys=True) + "\n")

    mapping_path = output_dir / "catalog_reconciliation.csv"
    mapping_rows = [mapping.to_dict() for mapping in mappings]
    with mapping_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mapping_rows[0]))
        writer.writeheader()
        writer.writerows(mapping_rows)

    assignments_path = output_dir / "split_assignments.csv"
    purged = set(split.purged_duplicate_basket_ids)
    split_by_id = {
        basket.basket_id: label
        for label, values in (("train", split.train), ("validation", split.validation), ("test", split.test))
        for basket in values
    }
    with assignments_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "basket_id", "timestamp", "split", "observed_item_keys", "hidden_target_item_key", "seed",
        ))
        writer.writeheader()
        for basket in baskets:
            observed, target = basket_completion_case(basket, SEED)
            writer.writerow({
                "basket_id": basket.basket_id, "timestamp": basket.timestamp.isoformat(),
                "split": "purged_duplicate" if basket.basket_id in purged else split_by_id[basket.basket_id],
                "observed_item_keys": "|".join(observed), "hidden_target_item_key": target, "seed": SEED,
            })

    basket_sizes = [len(basket.items) for basket in baskets]
    basket_report = {
        "input_valid_lines": len(lines), "reconstructed_baskets": len(baskets),
        "excluded_baskets": len(basket_exclusions), "row_rejects": len(row_rejects),
        "distinct_model_items": len({item.item_key for basket in baskets for item in basket.items}),
        "basket_distinct_items": {
            "minimum": min(basket_sizes), "maximum": max(basket_sizes),
            "mean": sum(basket_sizes) / len(basket_sizes),
        },
        "source_lines_aggregated": len(lines) - sum(basket_sizes),
        "transformations": [
            "Strict schema and value parsing; invalid rows are rejected with a reason.",
            "Orders must have one source user ID and one timestamp.",
            "Normalized product name is the model item key because source product_id is unstable.",
            "Repeated order/name lines are quantity-summed; source IDs and line counts remain traceable.",
            "Raw source user IDs are not copied into the derived JSONL.",
            "No category is excluded and no refund/cancellation inference is made.",
        ],
        "basket_exclusions": basket_exclusions,
    }
    split_report = {
        "method": "chronological_70_15_15_then_purge_later_duplicate_signatures",
        "seed_for_hidden_target": SEED,
        "raw_basket_count": len(baskets),
        "counts": {"train": len(split.train), "validation": len(split.validation), "test": len(split.test),
                   "purged_duplicate": len(split.purged_duplicate_basket_ids)},
        "train_end_inclusive": split.train_end,
        "validation_end_inclusive": split.validation_end,
        "test_end_inclusive": baskets[-1].timestamp.isoformat(),
        "hidden_target": "One item per basket selected by SHA-256(seed:basket_id) modulo distinct item count.",
        "leakage_controls": [
            "Targets are removed from observed inputs.",
            "Model and item statistics must fit train only.",
            "Validation selects hyperparameters; test remains untouched until final evaluation.",
            "A basket signature appearing in an earlier partition is purged from each later partition.",
        ],
    }
    mapping_counts = Counter(mapping.mapping_status for mapping in mappings)
    mapping_report = {
        "source_item_count": len(mappings), "status_counts": dict(mapping_counts),
        "navigation_eligible_source_items": sum(mapping.navigation_eligible for mapping in mappings),
        "exact_verified_mapping_count": mapping_counts["exact_verified_mapping"],
        "demo_catalog_product_count": 6,
        "policy": "Only exact-verified or normalized-name product mappings with shelf and pickup node may be navigable.",
    }
    inventory = {
        "discovery_scope": "component3 data directories",
        "candidate_dataset_count": 1,
        "datasets": [audit],
        "requested_filename_search": {
            "Retail_pos_basket_data.csv.csv": "not found",
            "srilanka_supermarket_raw_pos.csv": "not found",
            "Retail_pos_basket_data.csv": raw_path.as_posix(),
        },
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "pipeline_version": PIPELINE_VERSION, "generated_at_utc": generated_at,
        "python_version": platform.python_version(), "seed": SEED,
        "commands": [
            "component3/.venv/bin/python -m component3.backend.comp3_reco_navigation.recommendation.prepare_phase8a",
        ],
        "inputs": {
            "raw_path": raw_path.as_posix(), "raw_sha256": before_hash,
            "catalog_path": catalog_path.as_posix(), "catalog_sha256": sha256_file(catalog_path),
        },
        "outputs": {},
        "raw_unchanged": before_hash == sha256_file(raw_path),
        "final_model_trained": False,
    }
    for name, payload in (
        ("dataset_inventory.json", inventory), ("data_quality.json", audit),
        ("basket_reconstruction.json", basket_report), ("split_protocol.json", split_report),
        ("catalog_reconciliation_summary.json", mapping_report),
    ):
        _json(evidence_dir / name, payload)
    for output in (cleaned_path, mapping_path, assignments_path):
        manifest["outputs"][output.as_posix()] = sha256_file(output)
    _json(evidence_dir / "preparation_manifest.json", manifest)
    return {"inventory": inventory, "basket": basket_report, "split": split_report,
            "mapping": mapping_report, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=COMPONENT_ROOT / "data/raw/Retail_pos_basket_data.csv")
    parser.add_argument("--catalog", type=Path, default=COMPONENT_ROOT / "data/demo_store/v1/demo_store.json")
    parser.add_argument("--output", type=Path, default=COMPONENT_ROOT / "data/derived/recommendation_phase8a")
    parser.add_argument("--evidence", type=Path, default=COMPONENT_ROOT / "evaluation/research_archive/02_recommendation_engine")
    args = parser.parse_args()
    print(json.dumps(prepare(args.raw, args.catalog, args.output, args.evidence), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
