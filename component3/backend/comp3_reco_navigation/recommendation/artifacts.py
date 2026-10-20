"""Safe JSON serialization for fitted recommendation models."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from .baselines import AssociationRules, CategoryPopularity, GlobalPopularity, ItemItemCooccurrence
from .linear_model import LinearBasketRanker


ARTIFACT_SCHEMA = "comp3-recommendation-model-v1"


def model_to_dict(model: object, model_version: str) -> dict[str, object]:
    common = {
        "artifact_schema": ARTIFACT_SCHEMA, "model_version": model_version,
        "metadata": dict(model.model_metadata), "vocabulary": list(model.vocabulary),
    }
    if isinstance(model, LinearBasketRanker):
        return common | {"state": model.state_dict()}
    if isinstance(model, GlobalPopularity):
        state = {"scores": dict(model.scores)}
    elif isinstance(model, CategoryPopularity):
        state = {
            "item_category": model.item_category,
            "category_scores": {category: dict(scores) for category, scores in model.scores.items()},
            "fallback_scores": dict(model.fallback.scores),
        }
    elif isinstance(model, AssociationRules):
        state = {
            "rules": {source: dict(values) for source, values in model.rules.items()},
            "rule_metrics": {source: dict(values) for source, values in model.rule_metrics.items()},
            "fallback_scores": dict(model.fallback.scores),
            "min_support_count": model.min_support_count,
        }
    elif isinstance(model, ItemItemCooccurrence):
        state = {
            "similarity": [{"left": pair[0], "right": pair[1], "score": score}
                           for pair, score in sorted(model.similarity.items())],
            "fallback_scores": dict(model.fallback.scores),
        }
    else:
        raise TypeError(f"unsupported model type: {type(model).__name__}")
    return common | {"state": state}


def save_model(model: object, path: Path, model_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model_to_dict(model, model_version), indent=2, sort_keys=True) + "\n")


def _fallback(scores: dict[str, int | float], vocabulary: tuple[str, ...]) -> GlobalPopularity:
    model = GlobalPopularity()
    model.scores = Counter(scores)
    model.vocabulary = vocabulary
    model.model_metadata = {"model_type": "global_popularity_reloaded"}
    return model


def model_from_dict(artifact: dict[str, Any]) -> object:
    if artifact.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError("unsupported model artifact schema")
    state = artifact["state"]
    model_type = artifact["metadata"]["model_type"]
    vocabulary = tuple(artifact["vocabulary"])
    if model_type == "linear_basket_softmax":
        model = LinearBasketRanker.from_state_dict(state)
    elif model_type == "global_popularity":
        model = GlobalPopularity()
        model.scores = Counter(state["scores"])
        model.vocabulary = vocabulary
    elif model_type == "category_popularity":
        model = CategoryPopularity()
        model.item_category = dict(state["item_category"])
        model.scores = defaultdict(Counter, {
            category: Counter(scores) for category, scores in state["category_scores"].items()
        })
        model.fallback = _fallback(state["fallback_scores"], vocabulary)
        model.vocabulary = vocabulary
    elif model_type == "association_rules":
        model = AssociationRules()
        model.rules = defaultdict(dict, {source: dict(values) for source, values in state["rules"].items()})
        model.rule_metrics = defaultdict(dict, {
            source: dict(values) for source, values in state["rule_metrics"].items()
        })
        model.fallback = _fallback(state["fallback_scores"], vocabulary)
        model.vocabulary = vocabulary
        model.min_support_count = int(state["min_support_count"])
    elif model_type == "item_item_cosine":
        model = ItemItemCooccurrence()
        model.similarity = {
            (entry["left"], entry["right"]): float(entry["score"])
            for entry in state["similarity"]
        }
        model.fallback = _fallback(state["fallback_scores"], vocabulary)
        model.vocabulary = vocabulary
    else:
        raise ValueError(f"unknown model type: {model_type}")
    model.model_metadata = dict(artifact["metadata"])
    model.model_version = artifact["model_version"]
    return model


def load_model(path: Path) -> object:
    return model_from_dict(json.loads(path.read_text(encoding="utf-8")))
