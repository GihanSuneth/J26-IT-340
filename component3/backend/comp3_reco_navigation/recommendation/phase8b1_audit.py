"""Phase 8B.1 post-hoc generalization and navigable-catalog audit.

This module never fits a model or changes the frozen Phase 8B selection.  Test-label
use is limited to retrospective diagnosis after the original result was recorded.
"""

from __future__ import annotations

import csv
from collections import Counter
from itertools import combinations
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Mapping, Sequence

import numpy as np

from component3.simulations.navigation_dashboard.demo_store import load_demo_store

from .artifacts import load_model
from .data_loading import EvaluationCase, load_baskets, load_cases, verify_phase8a
from .phase8b_experiment import evaluate_model
from .preprocess import Basket, basket_completion_case, sha256_file


SEED = 3408
COMPONENT_ROOT = Path(__file__).resolve().parents[3]
MODEL_NAMES = (
    "association_rules",
    "item_item_cosine",
    "global_popularity",
    "category_popularity",
    "linear_basket_softmax",
)


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _percentiles(values: Sequence[int]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values), "minimum": int(array.min()),
        "p25": float(np.percentile(array, 25)), "median": float(np.median(array)),
        "mean": float(array.mean()), "p75": float(np.percentile(array, 75)),
        "maximum": int(array.max()),
    }


def _distribution(counter: Counter[str], vocabulary: Sequence[str]) -> np.ndarray:
    values = np.asarray([counter[item] for item in vocabulary], dtype=np.float64)
    return values / values.sum()


def _js_divergence(left: np.ndarray, right: np.ndarray) -> float:
    midpoint = (left + right) / 2.0

    def divergence(source: np.ndarray) -> float:
        present = source > 0
        return float(np.sum(source[present] * np.log2(source[present] / midpoint[present])))

    return (divergence(left) + divergence(right)) / 2.0


def _drift(left: Counter[str], right: Counter[str], vocabulary: Sequence[str]) -> dict[str, object]:
    left_distribution = _distribution(left, vocabulary)
    right_distribution = _distribution(right, vocabulary)
    correlation = float(np.corrcoef(left_distribution, right_distribution)[0, 1])
    changes = sorted(
        (
            {
                "item_key": item,
                "left_share": float(left_distribution[index]),
                "right_share": float(right_distribution[index]),
                "absolute_share_change": float(abs(right_distribution[index] - left_distribution[index])),
            }
            for index, item in enumerate(vocabulary)
        ),
        key=lambda row: (-row["absolute_share_change"], row["item_key"]),
    )
    return {
        "total_variation_distance": float(np.abs(left_distribution - right_distribution).sum() / 2.0),
        "jensen_shannon_divergence_bits": _js_divergence(left_distribution, right_distribution),
        "pearson_correlation": correlation,
        "largest_absolute_share_changes": changes[:10],
    }


def _pair_diagnostics(train_baskets: Sequence[Basket], cases: Sequence[EvaluationCase]) -> dict[str, object]:
    train_pairs = {
        pair for basket in train_baskets for pair in combinations(sorted(basket.signature), 2)
    }
    complete_pairs: list[tuple[str, str]] = []
    target_pairs: list[tuple[str, str]] = []
    for case in cases:
        complete_pairs.extend(combinations(sorted((*case.observed, case.target)), 2))
        target_pairs.extend(tuple(sorted((observed, case.target))) for observed in case.observed)
    unseen_complete = [pair for pair in complete_pairs if pair not in train_pairs]
    unseen_target = [pair for pair in target_pairs if pair not in train_pairs]
    return {
        "training_unique_pair_count": len(train_pairs),
        "evaluation_pair_occurrences": len(complete_pairs),
        "unseen_evaluation_pair_occurrences": len(unseen_complete),
        "unseen_evaluation_pair_rate": len(unseen_complete) / len(complete_pairs),
        "observed_to_target_pair_occurrences": len(target_pairs),
        "unseen_observed_to_target_pair_occurrences": len(unseen_target),
        "unseen_observed_to_target_pair_rate": len(unseen_target) / len(target_pairs),
        "unique_unseen_observed_to_target_pairs": len(set(unseen_target)),
    }


def _association_diagnostics(model: object, cases: Sequence[EvaluationCase]) -> dict[str, object]:
    fallback_only = 0
    rule_candidate_counts: list[int] = []
    target_supported = 0
    hit_targets: Counter[str] = Counter()
    miss_targets: Counter[str] = Counter()
    for case in cases:
        candidates = {
            candidate
            for source in case.observed
            for candidate in model.rules.get(source, {})
            if candidate not in case.observed
        }
        rule_candidate_counts.append(len(candidates))
        fallback_only += int(not candidates)
        target_supported += int(case.target in candidates)
        recommendations = [item for item, _ in model.recommend(case.observed, 5)]
        (hit_targets if case.target in recommendations else miss_targets)[case.target] += 1
    return {
        "basket_count": len(cases),
        "sessions_with_rule_candidates": len(cases) - fallback_only,
        "rule_candidate_coverage_rate": (len(cases) - fallback_only) / len(cases),
        "fallback_only_sessions": fallback_only,
        "fallback_only_frequency": fallback_only / len(cases),
        "mean_rule_candidate_count": mean(rule_candidate_counts),
        "median_rule_candidate_count": median(rule_candidate_counts),
        "hidden_target_supported_by_rule_count": target_supported,
        "hidden_target_supported_by_rule_rate": target_supported / len(cases),
        "top_hit_targets": hit_targets.most_common(10),
        "top_missed_targets": miss_targets.most_common(10),
    }


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _prediction_reproduction(
    models: Mapping[str, object], cases: Sequence[EvaluationCase], evidence: Path,
) -> dict[str, object]:
    by_split = {
        "validation": evidence / "phase_8b_validation_predictions.jsonl",
        "test": evidence / "phase_8b_test_predictions.jsonl",
    }
    results: dict[str, object] = {}
    cases_by_id = {case.basket_id: case for case in cases}
    for split, path in by_split.items():
        stored = _load_jsonl(path)
        checked = mismatches = 0
        for record in stored:
            model_name = str(record["model"])
            if model_name not in models:
                continue
            case = cases_by_id[str(record["basket_id"])]
            actual = models[model_name].recommend(case.observed, 5)
            expected = [(row["item_key"], float(row["score"])) for row in record["recommendations"]]
            checked += 1
            if len(actual) != len(expected) or any(
                item != expected_item or not math.isclose(score, expected_score, rel_tol=1e-12, abs_tol=1e-12)
                for (item, score), (expected_item, expected_score) in zip(actual, expected)
            ):
                mismatches += 1
        results[split] = {
            "stored_records_checked": checked,
            "prediction_mismatch_count": mismatches,
            "reproduced": mismatches == 0,
        }
    return results


def _manual_category_diversity(items: Sequence[str], categories: Mapping[str, str]) -> float:
    """Independent implementation used to audit the published diversity aggregate."""
    if len(items) < 2:
        return 0.0
    pairs = list(combinations(items, 2))
    return sum(categories[left] != categories[right] for left, right in pairs) / len(pairs)


def _catalog_audit(component_root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    crosswalk_path = component_root / "data/derived/recommendation_phase8a/catalog_reconciliation.csv"
    with crosswalk_path.open(newline="", encoding="utf-8") as stream:
        source_rows = list(csv.DictReader(stream))
    store = load_demo_store(component_root / "data/demo_store/v1/demo_store.json")
    products = {row["demo_product_id"]: row for row in store.data["products"]}
    shelves = {row["shelf_id"]: row for row in store.data["shelves"]}
    graph_nodes = set(store.graph.node_ids)
    rows: list[dict[str, object]] = []
    before_eligible = sum(row["navigation_eligible"] == "True" for row in source_rows)
    for source in source_rows:
        product = products.get(source["demo_product_id"])
        shelf = shelves.get(source["shelf_id"])
        eligible = bool(
            source["navigation_eligible"] == "True"
            and product
            and shelf
            and product["display_name"] == source["demo_product_name"]
            and product["shelf_id"] == source["shelf_id"]
            and product["pickup_node_id"] == source["pickup_node_id"]
            and shelf["pickup_node_id"] == source["pickup_node_id"]
            and source["pickup_node_id"] in graph_nodes
        )
        status = "verified_existing_mapping" if eligible else (
            "section_only_not_eligible" if source["mapping_status"] == "category_level_mapping"
            else "unmapped_not_eligible"
        )
        confidence = "high" if eligible else ("section-only" if source["shelf_section"] else "none")
        evidence = (
            f"Active demo catalog {product['demo_product_id']} matches product name, "
            f"shelf {product['shelf_id']} and graph pickup {product['pickup_node_id']}."
            if eligible else source["rationale"]
        )
        proposal = "" if eligible else (
            "Separate synthetic extension required: create a reviewed demo product and allocate a validated shelf, bay, level and pickup node; no location is asserted here."
        )
        rows.append({
            "source_item_key": source["source_item_key"],
            "source_product_name": source["source_product_name"],
            "source_category": source["source_category"],
            "proposed_catalog_product": product["display_name"] if eligible else "",
            "mapping_status": status,
            "mapping_confidence": confidence,
            "mapping_evidence": evidence,
            "existing_demo_product_id": product["demo_product_id"] if eligible else "",
            "existing_shelf_id": source["shelf_id"] if eligible else "",
            "existing_pickup_node": source["pickup_node_id"] if eligible else "",
            "navigation_eligible": eligible,
            "reference_validation": "passed_active_demo_graph" if eligible else "not_applicable",
            "synthetic_extension_proposal": proposal,
        })
    after_eligible = sum(bool(row["navigation_eligible"]) for row in rows)
    summary = {
        "source_product_count": len(rows),
        "active_demo_catalog_product_count": len(products),
        "coverage_before_verified_reconciliation": {
            "count": before_eligible, "denominator": len(rows), "rate": before_eligible / len(rows),
        },
        "coverage_after_verified_reconciliation": {
            "count": after_eligible, "denominator": len(rows), "rate": after_eligible / len(rows),
        },
        "verified_reference_count": after_eligible,
        "invalid_reference_count": sum(
            row["navigation_eligible"] and row["reference_validation"] != "passed_active_demo_graph"
            for row in rows
        ),
        "new_mapping_approvals": 0,
        "validated_map_modified": False,
        "decision": "No additional mapping had product-specific catalog and map evidence.",
    }
    return rows, summary


def run(component_root: Path = COMPONENT_ROOT) -> dict[str, object]:
    derived = component_root / "data/derived/recommendation_phase8a"
    evidence = component_root / "evaluation/research_archive/02_recommendation_engine"
    model_dir = component_root / "ml/models/comp3/recommendation_phase8b"
    baskets = load_baskets(derived / "cleaned_baskets.jsonl")
    cases = load_cases(derived / "split_assignments.csv")
    verification = verify_phase8a(baskets, cases, component_root / "data/raw/Retail_pos_basket_data.csv")
    basket_by_id = {basket.basket_id: basket for basket in baskets}
    split_cases = {split: [case for case in cases if case.split == split] for split in ("train", "validation", "test")}
    split_baskets = {
        split: [basket_by_id[case.basket_id] for case in split_cases[split]] for split in split_cases
    }
    vocabulary = tuple(sorted({item.item_key for basket in split_baskets["train"] for item in basket.items}))
    categories = {item.item_key: item.category for basket in baskets for item in basket.items}
    names = {item.item_key: item.product_name for basket in baskets for item in basket.items}
    models = {name: load_model(model_dir / f"{name}.json") for name in MODEL_NAMES}

    occurrence = {
        split: Counter(item for basket in split_baskets[split] for item in basket.signature)
        for split in split_cases
    }
    targets = {split: Counter(case.target for case in split_cases[split]) for split in split_cases}
    frequency_rows: list[dict[str, object]] = []
    for item in vocabulary:
        row: dict[str, object] = {
            "item_key": item, "product_name": names[item], "category": categories[item],
        }
        for split in split_cases:
            row[f"{split}_basket_count"] = occurrence[split][item]
            row[f"{split}_basket_prevalence"] = occurrence[split][item] / len(split_baskets[split])
            row[f"{split}_hidden_target_count"] = targets[split][item]
            row[f"{split}_hidden_target_share"] = targets[split][item] / len(split_cases[split])
        frequency_rows.append(row)
    _csv(evidence / "phase_8b1_distribution_comparison.csv", frequency_rows)

    distribution = {
        "basket_size_by_split": {
            split: _percentiles([len(basket.signature) for basket in split_baskets[split]])
            for split in split_cases
        },
        "item_presence": {
            split: {
                "present_count": sum(occurrence[split][item] > 0 for item in vocabulary),
                "absent_items": [item for item in vocabulary if not occurrence[split][item]],
            }
            for split in split_cases
        },
        "new_and_disappearing_items": {
            "validation_not_train": sorted(set(targets["validation"]) - set(occurrence["train"])),
            "test_not_train": sorted(set(targets["test"]) - set(occurrence["train"])),
            "test_not_validation": sorted(set(occurrence["test"]) - set(occurrence["validation"])),
            "validation_not_test": sorted(set(occurrence["validation"]) - set(occurrence["test"])),
        },
        "basket_item_frequency_drift": {
            "train_to_validation": _drift(occurrence["train"], occurrence["validation"], vocabulary),
            "train_to_test": _drift(occurrence["train"], occurrence["test"], vocabulary),
            "validation_to_test": _drift(occurrence["validation"], occurrence["test"], vocabulary),
        },
        "hidden_target_distribution_drift": {
            "validation_to_test": _drift(targets["validation"], targets["test"], vocabulary),
        },
        "unseen_pairs": {
            split: _pair_diagnostics(split_baskets["train"], split_cases[split])
            for split in ("validation", "test")
        },
        "candidate_availability": {
            split: _percentiles([len(vocabulary) - len(set(case.observed) & set(vocabulary)) for case in split_cases[split]])
            for split in ("validation", "test")
        },
        "association_rule_coverage": {
            split: _association_diagnostics(models["association_rules"], split_cases[split])
            for split in ("validation", "test")
        },
    }
    _json(evidence / "phase_8b1_generalization_diagnostics.json", distribution)

    validation_rows: dict[str, dict[str, str]] = {}
    with (evidence / "phase_8b_validation_comparison.csv").open(newline="", encoding="utf-8") as stream:
        validation_rows = {row["model"]: row for row in csv.DictReader(stream)}
    comparison_rows: list[dict[str, object]] = []
    test_results: dict[str, object] = {}
    for name in MODEL_NAMES:
        metrics, records = evaluate_model(models[name], split_cases["test"], vocabulary, categories)
        stable_metrics = {key: value for key, value in metrics.items() if key != "latency"}
        test_results[name] = {
            "metrics": stable_metrics,
            "top5_hit_count": sum(bool(row["hit_rate_at_k_5"]) for row in records),
            "top5_miss_count": sum(not bool(row["hit_rate_at_k_5"]) for row in records),
        }
        validation_ndcg = float(validation_rows[name]["ndcg@5"])
        test_ndcg = float(metrics["ndcg@5"])
        comparison_rows.append({
            "model": name,
            "validation_ndcg@5": validation_ndcg,
            "posthoc_test_ndcg@5": test_ndcg,
            "absolute_ndcg@5_change": test_ndcg - validation_ndcg,
            "relative_ndcg@5_change": (test_ndcg - validation_ndcg) / validation_ndcg,
            "validation_hit_rate@5": float(validation_rows[name]["hit_rate@5"]),
            "posthoc_test_hit_rate@5": float(metrics["hit_rate@5"]),
            "posthoc_diagnostic_only": True,
            "eligible_for_model_selection": False,
        })
    _csv(evidence / "phase_8b1_baseline_posthoc_test_comparison.csv", comparison_rows)
    _json(evidence / "phase_8b1_baseline_posthoc_test_results.json", {
        "warning": "Retrospective frozen-test diagnosis only; not model selection or tuning evidence.",
        "original_primary_finding_preserved": {
            "model": "association_rules", "validation_ndcg@5": 0.058074855380056536,
            "frozen_test_ndcg@5": 0.02320118339585382,
        },
        "selection_changed": False, "models_refit": False, "results": test_results,
    })

    manifest = json.loads((evidence / "phase_8b_experiment_manifest.json").read_text(encoding="utf-8"))
    expected_hashes = {
        Path(path).name: checksum for path, checksum in manifest["artifacts"].items()
        if str(path).startswith(str(model_dir))
    }
    current_hashes = {path.name: sha256_file(path) for path in model_dir.glob("*.json")}
    hidden_target_mismatches = 0
    for case in cases:
        if case.split == "purged_duplicate":
            continue
        observed, target = basket_completion_case(basket_by_id[case.basket_id], SEED)
        hidden_target_mismatches += int(observed != case.observed or target != case.target)
    reproduction = _prediction_reproduction(models, cases, evidence)
    stored_validation_metrics = json.loads(
        (evidence / "phase_8b_validation_results.json").read_text(encoding="utf-8")
    )
    stored_test_metrics = json.loads(
        (evidence / "phase_8b_frozen_test_results.json").read_text(encoding="utf-8")
    )["metrics"]
    validation_prediction_rows = _load_jsonl(evidence / "phase_8b_validation_predictions.jsonl")
    original_test_prediction_rows = _load_jsonl(evidence / "phase_8b_test_predictions.jsonl")
    diversity_recheck: dict[str, object] = {}
    for name in MODEL_NAMES:
        values = [
            _manual_category_diversity(
                [entry["item_key"] for entry in row["recommendations"]], categories
            )
            for row in validation_prediction_rows if row["model"] == name
        ]
        recalculated = mean(values)
        published = float(stored_validation_metrics[name]["category_diversity@5"])
        diversity_recheck[f"validation_{name}"] = {
            "recalculated": recalculated, "published": published,
            "matches": math.isclose(recalculated, published, rel_tol=1e-12, abs_tol=1e-12),
        }
    test_recalculated = mean([
        _manual_category_diversity(
            [entry["item_key"] for entry in row["recommendations"]], categories
        )
        for row in original_test_prediction_rows
    ])
    diversity_recheck["test_association_rules"] = {
        "recalculated": test_recalculated,
        "published": float(stored_test_metrics["category_diversity@5"]),
        "matches": math.isclose(
            test_recalculated, float(stored_test_metrics["category_diversity@5"]),
            rel_tol=1e-12, abs_tol=1e-12,
        ),
    }
    integrity = {
        "chronological_and_split_verification": verification,
        "chronological_order_strict": all(
            earlier.timestamp <= later.timestamp for earlier, later in zip(cases, cases[1:])
        ),
        "transaction_assignment_unique": len(cases) == len({case.basket_id for case in cases}),
        "hidden_target_reconstruction_mismatch_count": hidden_target_mismatches,
        "observed_target_overlap_count": sum(case.target in case.observed for case in cases),
        "training_vocabulary_size": len(vocabulary),
        "unseen_validation_targets": sorted(set(targets["validation"]) - set(vocabulary)),
        "unseen_test_targets": sorted(set(targets["test"]) - set(vocabulary)),
        "metric_denominators": {"validation": len(split_cases["validation"]), "test": len(split_cases["test"]), "hidden_targets_per_case": 1},
        "precision_hit_rate_identity_at_5_holds": all(
            math.isclose(float(row["posthoc_test_hit_rate@5"]) / 5.0,
                         float(test_results[str(row["model"])]["metrics"]["precision@5"]), rel_tol=1e-12)
            for row in comparison_rows
        ),
        "category_diversity_definition": "mean fraction of unordered recommendation pairs belonging to different categories; lists shorter than two return 0",
        "category_diversity_independent_recheck": diversity_recheck,
        "category_diversity_recalculated_during_frozen_artifact_evaluation": {
            name: test_results[name]["metrics"]["category_diversity@5"] for name in MODEL_NAMES
        },
        "model_artifact_hashes_match_phase8b_manifest": expected_hashes == {
            name: current_hashes.get(name) for name in expected_hashes
        },
        "expected_model_artifact_sha256": expected_hashes,
        "prediction_reproduction": reproduction,
        "purged_repeated_purchase_implication": (
            "The two records have distinct transaction IDs and timestamps and are likely legitimate repeated purchases. "
            "Their exclusion reduces the sample by two and slightly changes temporal prevalence, while enforcing the conservative no-shared-signature policy. "
            "They remain excluded to preserve the original split and report; no claim of source duplication is made."
        ),
    }
    _json(evidence / "phase_8b1_evaluation_integrity.json", integrity)

    mapping_rows, mapping_summary = _catalog_audit(component_root)
    _csv(evidence / "phase_8b1_catalog_mapping_audit.csv", mapping_rows)
    _json(evidence / "phase_8b1_catalog_mapping_summary.json", mapping_summary)

    outputs = [
        "phase_8b1_distribution_comparison.csv", "phase_8b1_generalization_diagnostics.json",
        "phase_8b1_baseline_posthoc_test_comparison.csv", "phase_8b1_baseline_posthoc_test_results.json",
        "phase_8b1_evaluation_integrity.json", "phase_8b1_catalog_mapping_audit.csv",
        "phase_8b1_catalog_mapping_summary.json",
    ]
    audit_manifest = {
        "phase": "8B.1", "seed": SEED,
        "audit_is_posthoc": True, "models_refit": False, "selection_changed": False,
        "test_labels_used_for_tuning": False, "dashboard_integration_performed": False,
        "validated_research_maps_modified": False,
        "phase8b_model_artifact_hashes_unchanged": integrity["model_artifact_hashes_match_phase8b_manifest"],
        "outputs": {name: sha256_file(evidence / name) for name in outputs},
    }
    _json(evidence / "phase_8b1_manifest.json", audit_manifest)
    return {
        "distribution": distribution,
        "comparison": comparison_rows,
        "integrity": integrity,
        "mapping": mapping_summary,
        "manifest": audit_manifest,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
