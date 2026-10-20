"""Transparent basket-level recommendation baselines for Phase 8B experiments."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Mapping, Sequence

from .preprocess import Basket


def _basket_sets(baskets: Sequence[Basket]) -> list[set[str]]:
    return [{item.item_key for item in basket.items} for basket in baskets]


def _rank(
    scores: Mapping[str, float], observed: set[str], k: int,
    vocabulary: Sequence[str] | None = None, fallback: Mapping[str, float] | None = None,
) -> list[tuple[str, float]]:
    if k <= 0:
        raise ValueError("k must be positive")
    candidates = vocabulary if vocabulary is not None else tuple(scores)
    fallback = fallback or {}
    ranked = sorted(
        (item for item in candidates if item not in observed),
        key=lambda item: (-float(scores.get(item, 0.0)), -float(fallback.get(item, 0.0)), item),
    )[:k]
    return [(item, float(scores.get(item, 0.0))) for item in ranked]


class GlobalPopularity:
    """Rank items by number of training baskets containing each item."""

    def fit(self, baskets: Sequence[Basket]) -> "GlobalPopularity":
        self.scores = Counter(item for basket in _basket_sets(baskets) for item in basket)
        self.vocabulary = tuple(sorted(self.scores))
        self.model_metadata = {
            "model_type": "global_popularity", "score": "training_basket_prevalence_count",
            "training_baskets": len(baskets), "vocabulary_size": len(self.vocabulary),
        }
        return self

    def recommend(self, observed: Sequence[str], k: int) -> list[tuple[str, float]]:
        return _rank(self.scores, set(observed), k, self.vocabulary)


class CategoryPopularity:
    """Rank popular items in categories represented in the observed basket."""

    def fit(self, baskets: Sequence[Basket]) -> "CategoryPopularity":
        self.item_category = {item.item_key: item.category for basket in baskets for item in basket.items}
        self.scores: dict[str, Counter[str]] = defaultdict(Counter)
        for basket in _basket_sets(baskets):
            for item in basket:
                self.scores[self.item_category[item]][item] += 1
        self.fallback = GlobalPopularity().fit(baskets)
        self.vocabulary = self.fallback.vocabulary
        self.model_metadata = {
            "model_type": "category_popularity", "score": "category_conditioned_basket_prevalence",
            "training_baskets": len(baskets), "vocabulary_size": len(self.vocabulary),
        }
        return self

    def recommend(self, observed: Sequence[str], k: int) -> list[tuple[str, float]]:
        categories = {self.item_category[item] for item in observed if item in self.item_category}
        scores = Counter()
        for category in categories:
            scores.update(self.scores[category])
        return _rank(scores, set(observed), k, self.vocabulary, self.fallback.scores)


class AssociationRules:
    """Pairwise rules using support, confidence and lift with popularity fallback."""

    def fit(self, baskets: Sequence[Basket], min_support_count: int = 2) -> "AssociationRules":
        if min_support_count <= 0:
            raise ValueError("min_support_count must be positive")
        item_counts = Counter()
        pair_counts = Counter()
        for basket in _basket_sets(baskets):
            item_counts.update(basket)
            for source in basket:
                pair_counts.update((source, target) for target in basket if target != source)
        self.rules: dict[str, dict[str, float]] = defaultdict(dict)
        self.rule_metrics: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
        basket_count = len(baskets)
        for (source, target), count in pair_counts.items():
            if count >= min_support_count:
                support = count / basket_count
                confidence = count / item_counts[source]
                lift = confidence / (item_counts[target] / basket_count)
                self.rules[source][target] = confidence * lift
                self.rule_metrics[source][target] = {
                    "support": support, "confidence": confidence, "lift": lift,
                    "support_count": float(count),
                }
        self.fallback = GlobalPopularity().fit(baskets)
        self.vocabulary = self.fallback.vocabulary
        self.min_support_count = min_support_count
        self.model_metadata = {
            "model_type": "association_rules", "score": "max_confidence_times_lift",
            "min_support_count": min_support_count,
            "rule_count": sum(len(values) for values in self.rules.values()),
            "training_baskets": len(baskets), "vocabulary_size": len(self.vocabulary),
        }
        return self

    def recommend(self, observed: Sequence[str], k: int) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for source in set(observed):
            for target, confidence in self.rules.get(source, {}).items():
                scores[target] = max(scores[target], confidence)
        return _rank(scores, set(observed), k, self.vocabulary, self.fallback.scores)


class ItemItemCooccurrence:
    """Cosine-normalized item-item basket co-occurrence baseline."""

    def fit(self, baskets: Sequence[Basket]) -> "ItemItemCooccurrence":
        counts = Counter()
        pairs = Counter()
        for basket in _basket_sets(baskets):
            counts.update(basket)
            for left in basket:
                pairs.update((left, right) for right in basket if right != left)
        self.similarity = {
            pair: count / math.sqrt(counts[pair[0]] * counts[pair[1]])
            for pair, count in pairs.items()
        }
        self.fallback = GlobalPopularity().fit(baskets)
        self.vocabulary = self.fallback.vocabulary
        self.model_metadata = {
            "model_type": "item_item_cosine", "score": "sum_cosine_cooccurrence",
            "pair_count": len(self.similarity), "training_baskets": len(baskets),
            "vocabulary_size": len(self.vocabulary),
        }
        return self

    def recommend(self, observed: Sequence[str], k: int) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for source in set(observed):
            for (left, right), score in self.similarity.items():
                if left == source:
                    scores[right] += score
        return _rank(scores, set(observed), k, self.vocabulary, self.fallback.scores)
