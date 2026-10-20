"""Fit, select, freeze and evaluate Phase 8B recommendation models."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import time
from typing import Mapping, Sequence

import numpy as np

from .artifacts import save_model
from .baselines import AssociationRules, CategoryPopularity, GlobalPopularity, ItemItemCooccurrence
from .data_loading import EvaluationCase, load_baskets, load_cases, verify_phase8a
from .evaluation import catalog_coverage, category_diversity, evaluate_case, latency_summary
from .linear_model import LinearBasketRanker
from .preprocess import Basket, sha256_file


SEED = 3408
MODEL_VERSION_PREFIX = "comp3-phase8b-20261016"
K_VALUES = (1, 3, 5)
BOOTSTRAP_REPLICATES = 2000
COMPONENT_ROOT = Path(__file__).resolve().parents[3]


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bootstrap_interval(values: Sequence[float], seed_offset: int = 0) -> list[float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(SEED + seed_offset)
    indices = rng.integers(0, len(array), size=(BOOTSTRAP_REPLICATES, len(array)))
    means = array[indices].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def evaluate_model(
    model: object, cases: Sequence[EvaluationCase], vocabulary: Sequence[str],
    categories: Mapping[str, str], *, scope: set[str] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    latency_ms: list[float] = []
    recommendations_by_k: dict[int, list[list[str]]] = {k: [] for k in K_VALUES}
    eligible_targets = 0
    for case in cases:
        started = time.perf_counter_ns()
        full_ranked = model.recommend(case.observed, len(vocabulary))
        elapsed = (time.perf_counter_ns() - started) / 1_000_000.0
        latency_ms.append(elapsed)
        ranked = [(item, score) for item, score in full_ranked if scope is None or item in scope]
        target_eligible = scope is None or case.target in scope
        eligible_targets += int(target_eligible)
        record: dict[str, object] = {
            "basket_id": case.basket_id, "timestamp": case.timestamp,
            "observed": list(case.observed), "hidden_target": case.target,
            "target_eligible_in_scope": target_eligible,
            "recommendations": [{"item_key": item, "score": score} for item, score in ranked[:5]],
            "latency_ms": elapsed,
        }
        for k in K_VALUES:
            recommended = [item for item, _ in ranked[:k]]
            recommendations_by_k[k].append(recommended)
            metrics = evaluate_case(recommended, (case.target,), case.observed, k)
            for metric, value in metrics.items():
                record[f"{metric}_{k}"] = value
        records.append(record)

    summary: dict[str, object] = {
        "basket_count": len(cases), "target_eligible_count": eligible_targets,
        "scope_catalog_size": len(scope) if scope is not None else len(vocabulary),
        "latency": latency_summary(latency_ms),
    }
    for k in K_VALUES:
        suffix = f"at_{k}"
        for metric in ("precision", "recall", "hit_rate", "ndcg"):
            key = f"{metric}_at_k_{k}"
            values = [float(record[f"{metric}_at_k_{k}"]) for record in records]
            summary[f"{metric}@{k}"] = float(np.mean(values))
            if metric in {"hit_rate", "ndcg"}:
                summary[f"{metric}@{k}_bootstrap_95_ci"] = _bootstrap_interval(values, k)
        summary[f"catalog_coverage@{k}"] = catalog_coverage(recommendations_by_k[k], tuple(scope or vocabulary))
        summary[f"category_diversity@{k}"] = float(np.mean([
            category_diversity(values, categories) for values in recommendations_by_k[k]
        ]))
        summary[f"already_observed_violations@{k}"] = int(sum(
            int(record[f"already_observed_count_{k}"]) for record in records
        ))
    cold_target = [record for record in records if record["hidden_target"] not in vocabulary]
    cold_basket = [record for record in records if not set(record["observed"]) & set(vocabulary)]
    summary["cold_start"] = {
        "unseen_target_count": len(cold_target),
        "no_known_observed_item_count": len(cold_basket),
        "metrics": None if not cold_target and not cold_basket else "See per-basket records",
    }
    summary["sessions_with_at_least_one_candidate"] = sum(bool(record["recommendations"]) for record in records)
    return summary, records


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _validation_figure(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    width, height = 900, 420
    margin, chart_height = 70, 280
    values = [float(row["ndcg@5"]) for row in rows]
    maximum = max(values) or 1.0
    bar_width = 110
    gap = (width - 2 * margin - len(rows) * bar_width) / max(1, len(rows) - 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="450" y="32" text-anchor="middle" font-family="sans-serif" font-size="20">Validation NDCG@5 (unknown-provenance dataset)</text>',
        f'<line x1="{margin}" y1="{margin + chart_height}" x2="{width-margin}" y2="{margin + chart_height}" stroke="#333"/>',
    ]
    for index, (row, value) in enumerate(zip(rows, values)):
        x = margin + index * (bar_width + gap)
        bar_height = value / maximum * (chart_height - 20)
        y = margin + chart_height - bar_height
        label = str(row["model"]).replace("&", "and")
        parts.extend([
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" fill="#177a5b"/>',
            f'<text x="{x + bar_width/2:.1f}" y="{y-7:.1f}" text-anchor="middle" font-family="sans-serif" font-size="13">{value:.4f}</text>',
            f'<text x="{x + bar_width/2:.1f}" y="{margin+chart_height+22}" text-anchor="middle" font-family="sans-serif" font-size="11">{label}</text>',
        ])
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def run(component_root: Path = COMPONENT_ROOT) -> dict[str, object]:
    derived = component_root / "data/derived/recommendation_phase8a"
    evidence = component_root / "evaluation/research_archive/02_recommendation_engine"
    model_dir = component_root / "ml/models/comp3/recommendation_phase8b"
    model_dir.mkdir(parents=True, exist_ok=True)
    baskets = load_baskets(derived / "cleaned_baskets.jsonl")
    cases = load_cases(derived / "split_assignments.csv")
    verification = verify_phase8a(baskets, cases, component_root / "data/raw/Retail_pos_basket_data.csv")
    _json(evidence / "phase_8b_dataset_verification.json", verification)

    basket_by_id = {basket.basket_id: basket for basket in baskets}
    train_cases = [case for case in cases if case.split == "train"]
    validation_cases = [case for case in cases if case.split == "validation"]
    test_cases = [case for case in cases if case.split == "test"]
    train_baskets = [basket_by_id[case.basket_id] for case in train_cases]
    vocabulary = tuple(sorted({item.item_key for basket in train_baskets for item in basket.items}))
    categories = {item.item_key: item.category for basket in baskets for item in basket.items}

    models: dict[str, object] = {}
    training_times: dict[str, float] = {}
    constructors = {
        "global_popularity": lambda: GlobalPopularity().fit(train_baskets),
        "category_popularity": lambda: CategoryPopularity().fit(train_baskets),
        "association_rules": lambda: AssociationRules().fit(train_baskets, min_support_count=5),
        "item_item_cosine": lambda: ItemItemCooccurrence().fit(train_baskets),
    }
    for name, constructor in constructors.items():
        started = time.perf_counter()
        models[name] = constructor()
        training_times[name] = (time.perf_counter() - started) * 1000.0

    linear_tuning: list[dict[str, object]] = []
    linear_candidates: dict[float, LinearBasketRanker] = {}
    for l2 in (0.0, 0.0001, 0.001, 0.01, 0.1):
        started = time.perf_counter()
        model = LinearBasketRanker(l2=l2, learning_rate=0.3, epochs=400, seed=SEED).fit(train_cases, vocabulary)
        runtime = (time.perf_counter() - started) * 1000.0
        metrics, _ = evaluate_model(model, validation_cases, vocabulary, categories)
        linear_tuning.append({"l2": l2, "training_runtime_ms": runtime,
                              "ndcg@5": metrics["ndcg@5"], "hit_rate@5": metrics["hit_rate@5"]})
        linear_candidates[l2] = model
    chosen_l2 = max(linear_tuning, key=lambda row: (row["ndcg@5"], row["hit_rate@5"], -row["l2"]))["l2"]
    models["linear_basket_softmax"] = linear_candidates[chosen_l2]
    training_times["linear_basket_softmax"] = next(
        row["training_runtime_ms"] for row in linear_tuning if row["l2"] == chosen_l2
    )

    validation_results: dict[str, dict[str, object]] = {}
    validation_records: list[dict[str, object]] = []
    table_rows: list[dict[str, object]] = []
    for name, model in models.items():
        metrics, records = evaluate_model(model, validation_cases, vocabulary, categories)
        validation_results[name] = metrics
        for record in records:
            validation_records.append({"model": name, **record})
        table_rows.append({
            "model": name, "precision@1": metrics["precision@1"],
            "recall@1": metrics["recall@1"], "hit_rate@1": metrics["hit_rate@1"],
            "ndcg@1": metrics["ndcg@1"], "precision@3": metrics["precision@3"],
            "recall@3": metrics["recall@3"], "hit_rate@3": metrics["hit_rate@3"],
            "ndcg@3": metrics["ndcg@3"], "precision@5": metrics["precision@5"],
            "recall@5": metrics["recall@5"], "hit_rate@5": metrics["hit_rate@5"],
            "ndcg@5": metrics["ndcg@5"], "coverage@5": metrics["catalog_coverage@5"],
            "diversity@5": metrics["category_diversity@5"],
            "observed_violations@5": metrics["already_observed_violations@5"],
            "mean_latency_ms": metrics["latency"]["mean_ms"],
            "median_latency_ms": metrics["latency"]["median_ms"],
            "p95_latency_ms": metrics["latency"]["p95_ms"],
            "training_runtime_ms": training_times[name],
        })

    complexity_order = {
        "global_popularity": 0, "category_popularity": 1, "association_rules": 2,
        "item_item_cosine": 3, "linear_basket_softmax": 4,
    }
    selected_name = max(models, key=lambda name: (
        validation_results[name]["ndcg@5"], validation_results[name]["hit_rate@5"],
        validation_results[name]["catalog_coverage@5"], -complexity_order[name],
    ))
    selected_model = models[selected_name]
    selection = {
        "primary_criterion": "maximum validation NDCG@5",
        "tie_breakers": ["validation HitRate@5", "catalog coverage@5", "lower model complexity"],
        "selected_model": selected_name,
        "selected_validation_ndcg@5": validation_results[selected_name]["ndcg@5"],
        "test_consulted_during_selection": False,
        "frozen": {
            "preprocessing": "phase8a-preparation-v1 normalized-name keys",
            "vocabulary_sha256": hashlib.sha256("\n".join(vocabulary).encode()).hexdigest(),
            "model_family": selected_name, "hyperparameters": selected_model.model_metadata,
            "candidate_filtering": "training vocabulary minus observed items",
            "ranking_logic": "descending model score then deterministic item key",
            "seed": SEED,
        },
    }

    paired: dict[str, object] = {}
    selected_by_id = {record["basket_id"]: record for record in validation_records if record["model"] == selected_name}
    for name in models:
        if name == selected_name:
            continue
        comparison = {record["basket_id"]: record for record in validation_records if record["model"] == name}
        differences = [
            float(selected_by_id[basket_id]["ndcg_at_k_5"]) - float(comparison[basket_id]["ndcg_at_k_5"])
            for basket_id in selected_by_id
        ]
        paired[name] = {"paired_baskets": len(differences), "mean_ndcg@5_difference": float(np.mean(differences)),
                        "bootstrap_95_ci": _bootstrap_interval(differences, complexity_order[name] + 100),
                        "statistical_significance_claimed": False}

    model_paths: dict[str, str] = {}
    for name, model in models.items():
        path = model_dir / f"{name}.json"
        save_model(model, path, f"{MODEL_VERSION_PREFIX}-{name}")
        model_paths[name] = path.as_posix()
    selected_path = model_dir / "selected_model.json"
    save_model(selected_model, selected_path, f"{MODEL_VERSION_PREFIX}-{selected_name}")

    # The test set is evaluated only after selection and artifact freezing above.
    test_metrics, test_records = evaluate_model(selected_model, test_cases, vocabulary, categories)

    with (derived / "catalog_reconciliation.csv").open(newline="", encoding="utf-8") as stream:
        mapping_rows = list(csv.DictReader(stream))
    navigable = {row["source_item_key"] for row in mapping_rows if row["navigation_eligible"].lower() == "true"}
    expected_navigable = {"name:banana", "name:bread", "name:milk", "name:pasta"}
    if navigable != expected_navigable:
        raise ValueError(f"navigation mapping mismatch: {sorted(navigable)}")
    nav_validation, _ = evaluate_model(selected_model, validation_cases, vocabulary, categories, scope=navigable)
    nav_test, nav_test_records = evaluate_model(selected_model, test_cases, vocabulary, categories, scope=navigable)
    nav_validation_eligible, _ = evaluate_model(
        selected_model, [case for case in validation_cases if case.target in navigable],
        vocabulary, categories, scope=navigable,
    )
    nav_test_eligible, _ = evaluate_model(
        selected_model, [case for case in test_cases if case.target in navigable],
        vocabulary, categories, scope=navigable,
    )
    navigation_report = {
        "navigation_eligible_items": sorted(navigable),
        "candidate_fraction_navigable": len(navigable) / len(vocabulary),
        "candidate_mapping_coverage_loss": 1.0 - len(navigable) / len(vocabulary),
        "validation_all_sessions": nav_validation, "test_all_sessions": nav_test,
        "validation_navigation_eligible_target_subset": nav_validation_eligible,
        "test_navigation_eligible_target_subset": nav_test_eligible,
        "validation_session_fraction_with_suggestion": (
            nav_validation["sessions_with_at_least_one_candidate"] / len(validation_cases)
        ),
        "test_session_fraction_with_suggestion": (
            nav_test["sessions_with_at_least_one_candidate"] / len(test_cases)
        ),
        "scope_warning": "Navigable-only results are not full-catalog performance.",
    }

    configuration = {
        "experiment_version": "phase8b-v1", "seed": SEED, "k_values": list(K_VALUES),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "association_min_support_count": 5,
        "linear_search": linear_tuning,
        "data_checksum": verification["raw_sha256"],
        "python_version": platform.python_version(), "numpy_version": np.__version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance_classification": "UNKNOWN PROVENANCE",
    }
    _json(model_dir / "product_vocabulary.json", {"items": list(vocabulary), "categories": categories})
    _json(model_dir / "training_configuration.json", configuration)
    _json(model_dir / "training_metadata.json", {
        "training_baskets": len(train_baskets), "training_examples": len(train_cases),
        "training_runtime_ms": training_times, "artifacts": model_paths,
        "selected_artifact": selected_path.as_posix(), "selection": selection,
    })
    _json(model_dir / "evaluation_configuration.json", {
        "validation_baskets": len(validation_cases), "test_baskets": len(test_cases),
        "hidden_targets_per_basket": 1, "full_catalog_size": len(vocabulary),
        "navigable_catalog_size": len(navigable), "k_values": list(K_VALUES),
    })
    _json(evidence / "phase_8b_validation_results.json", validation_results)
    _json(evidence / "phase_8b_model_selection.json", selection)
    _json(evidence / "phase_8b_frozen_test_results.json", {
        "selected_model": selected_name, "metrics": test_metrics,
        "selection_frozen_before_test": True,
    })
    _json(evidence / "phase_8b_paired_comparisons.json", paired)
    _json(evidence / "phase_8b_navigable_coverage.json", navigation_report)
    _write_csv(evidence / "phase_8b_validation_comparison.csv", table_rows)
    _write_csv(evidence / "phase_8b_linear_tuning.csv", linear_tuning)
    _write_csv(evidence / "phase_8b_test_metrics.csv", [{"selected_model": selected_name, **{
        key: value for key, value in test_metrics.items() if isinstance(value, (int, float))
    }}])
    _validation_figure(evidence / "phase_8b_validation_ndcg5.svg", table_rows)
    with (evidence / "phase_8b_validation_predictions.jsonl").open("w", encoding="utf-8") as stream:
        for record in validation_records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    with (evidence / "phase_8b_test_predictions.jsonl").open("w", encoding="utf-8") as stream:
        for record in test_records:
            stream.write(json.dumps({"model": selected_name, **record}, sort_keys=True) + "\n")
    with (evidence / "phase_8b_navigable_test_predictions.jsonl").open("w", encoding="utf-8") as stream:
        for record in nav_test_records:
            stream.write(json.dumps({"model": selected_name, **record}, sort_keys=True) + "\n")

    manifest_files = list(model_dir.glob("*.json")) + [
        path for path in evidence.glob("phase_8b_*")
        if path.name != "phase_8b_experiment_manifest.json"
    ]
    manifest = {
        "experiment_version": "phase8b-v1", "selected_model": selected_name,
        "raw_sha256": verification["raw_sha256"], "seed": SEED,
        "final_model_trained": True, "dashboard_integration_performed": False,
        "artifacts": {path.as_posix(): sha256_file(path) for path in sorted(manifest_files)},
    }
    _json(evidence / "phase_8b_experiment_manifest.json", manifest)
    return {
        "verification": verification, "validation": validation_results,
        "selection": selection, "test": test_metrics, "navigation": navigation_report,
        "training_configuration": configuration, "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component-root", type=Path, default=COMPONENT_ROOT)
    args = parser.parse_args()
    result = run(args.component_root)
    print(json.dumps({
        "selected_model": result["selection"]["selected_model"],
        "validation_ndcg@5": result["selection"]["selected_validation_ndcg@5"],
        "test_metrics": result["test"],
        "navigation": result["navigation"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
