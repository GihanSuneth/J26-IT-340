"""Offline top-K metric definitions kept separate from route-cost evaluation."""

from __future__ import annotations

import math
from statistics import mean
from statistics import median
from typing import Mapping, Sequence


def evaluate_case(
    recommendations: Sequence[str], targets: Sequence[str], observed: Sequence[str], k: int,
) -> dict[str, float | int]:
    if k <= 0 or not targets:
        raise ValueError("k must be positive and targets must not be empty")
    ranked = list(recommendations[:k])
    target_set = set(targets)
    hits = [index for index, item in enumerate(ranked) if item in target_set]
    dcg = sum(1.0 / math.log2(index + 2) for index in hits)
    ideal = sum(1.0 / math.log2(index + 2) for index in range(min(len(target_set), k)))
    return {
        "precision_at_k": len(hits) / k,
        "recall_at_k": len(set(ranked) & target_set) / len(target_set),
        "hit_rate_at_k": int(bool(hits)),
        "ndcg_at_k": dcg / ideal if ideal else 0.0,
        "already_observed_count": sum(item in set(observed) for item in ranked),
    }


def aggregate_cases(cases: Sequence[Mapping[str, float | int]]) -> dict[str, float]:
    if not cases:
        raise ValueError("at least one evaluated case is required")
    return {key: mean(float(case[key]) for case in cases) for key in cases[0]}


def catalog_coverage(recommendation_lists: Sequence[Sequence[str]], eligible_catalog: Sequence[str]) -> float:
    catalog = set(eligible_catalog)
    if not catalog:
        raise ValueError("eligible catalog must not be empty")
    recommended = {item for values in recommendation_lists for item in values}
    return len(recommended & catalog) / len(catalog)


def category_diversity(recommendations: Sequence[str], categories: Mapping[str, str]) -> float:
    """Fraction of unordered recommendation pairs in different categories."""
    if len(recommendations) < 2:
        return 0.0
    pairs = 0
    different = 0
    for index, left in enumerate(recommendations):
        for right in recommendations[index + 1:]:
            pairs += 1
            different += categories.get(left) != categories.get(right)
    return different / pairs


def latency_summary(milliseconds: Sequence[float]) -> dict[str, float]:
    if not milliseconds or any(value < 0 or not math.isfinite(value) for value in milliseconds):
        raise ValueError("latencies must be finite nonnegative values")
    ordered = sorted(milliseconds)
    percentile = lambda q: ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]
    return {
        "count": float(len(ordered)), "mean_ms": mean(ordered),
        "median_ms": median(ordered), "p50_ms": percentile(0.50), "p95_ms": percentile(0.95),
    }
