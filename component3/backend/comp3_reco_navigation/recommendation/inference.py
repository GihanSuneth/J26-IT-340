"""Deterministic offline inference interface for Phase 8B artifacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .artifacts import load_model


class RecommendationInference:
    def __init__(self, model_path: Path, mapping_path: Path) -> None:
        self.model = load_model(model_path)
        with mapping_path.open(newline="", encoding="utf-8") as stream:
            self.mappings = {row["source_item_key"]: row for row in csv.DictReader(stream)}

    def recommend(self, observed: Sequence[str], k: int = 5) -> list[dict[str, object]]:
        ranked = self.model.recommend(observed, k)
        output: list[dict[str, object]] = []
        for source_item_key, score in ranked:
            mapping = self.mappings[source_item_key]
            output.append({
                "product_id": source_item_key,
                "normalized_product_name": source_item_key.removeprefix("name:").replace("-", " "),
                "mapped_demo_product_id": mapping["demo_product_id"] or None,
                "score": score,
                "model_version": self.model.model_version,
                "candidate_source": self.model.model_metadata["model_type"],
                "mapping_status": mapping["mapping_status"],
                "navigation_eligible": mapping["navigation_eligible"].lower() == "true",
                "shelf_id": mapping["shelf_id"] or None,
                "pickup_node_id": mapping["pickup_node_id"] or None,
                "explanation": self._explanation(source_item_key, observed),
            })
        return output

    def _explanation(self, candidate: str, observed: Sequence[str]) -> str | None:
        model_type = self.model.model_metadata["model_type"]
        if model_type == "global_popularity":
            return "Frequently present in the training baskets."
        if model_type == "association_rules":
            supported = [
                (source, self.model.rule_metrics.get(source, {}).get(candidate))
                for source in observed
            ]
            supported = [(source, metrics) for source, metrics in supported if metrics]
            if supported:
                source, metrics = max(supported, key=lambda pair: pair[1]["confidence"] * pair[1]["lift"])
                return (
                    f"Associated with {source.removeprefix('name:').replace('-', ' ')} "
                    f"in training baskets (confidence {metrics['confidence']:.3f}, lift {metrics['lift']:.3f})."
                )
        return None
