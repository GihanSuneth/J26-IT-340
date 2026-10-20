"""Phase 8B model, artifact, evaluation and inference contract tests."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from component3.backend.comp3_reco_navigation.recommendation.artifacts import load_model, save_model
from component3.backend.comp3_reco_navigation.recommendation.baselines import (
    AssociationRules, CategoryPopularity, GlobalPopularity, ItemItemCooccurrence,
)
from component3.backend.comp3_reco_navigation.recommendation.data_loading import (
    EvaluationCase, load_baskets, load_cases, verify_phase8a,
)
from component3.backend.comp3_reco_navigation.recommendation.evaluation import evaluate_case
from component3.backend.comp3_reco_navigation.recommendation.inference import RecommendationInference
from component3.backend.comp3_reco_navigation.recommendation.linear_model import LinearBasketRanker
from component3.backend.comp3_reco_navigation.recommendation.preprocess import Basket, BasketItem


ROOT = Path(__file__).resolve().parents[4]
COMPONENT = ROOT / "component3"
DERIVED = COMPONENT / "data/derived/recommendation_phase8a"
MODEL_DIR = COMPONENT / "ml/models/comp3/recommendation_phase8b"


def item(key: str, category: str = "Test") -> BasketItem:
    return BasketItem(key, key.removeprefix("name:"), category, 1, ("source",), 1)


def basket(identifier: str, keys: tuple[str, ...]) -> Basket:
    return Basket(identifier, datetime(2024, 1, 1), "user", tuple(item(key) for key in keys), len(keys))


class Phase8BDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baskets = load_baskets(DERIVED / "cleaned_baskets.jsonl")
        cls.cases = load_cases(DERIVED / "split_assignments.csv")

    def test_phase8a_artifacts_verify_exactly(self) -> None:
        report = verify_phase8a(self.baskets, self.cases, COMPONENT / "data/raw/Retail_pos_basket_data.csv")
        self.assertTrue(report["verified"])
        self.assertEqual((report["basket_count"], report["vocabulary_size"]), (1991, 68))
        self.assertEqual(report["target_leak_count"], 0)

    def test_split_transactions_and_signatures_are_isolated(self) -> None:
        by_id = {value.basket_id: value for value in self.baskets}
        parts = {
            split: {by_id[case.basket_id].signature for case in self.cases if case.split == split}
            for split in ("train", "validation", "test")
        }
        self.assertTrue(parts["train"].isdisjoint(parts["validation"]))
        self.assertTrue(parts["train"].isdisjoint(parts["test"]))
        self.assertEqual(len({case.basket_id for case in self.cases}), 1991)


class BaselineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baskets = [
            basket("1", ("name:a", "name:b")),
            basket("2", ("name:a", "name:c")),
            basket("3", ("name:a", "name:b")),
        ]

    def test_all_baselines_fit_and_rank_deterministically(self) -> None:
        models = (
            GlobalPopularity().fit(self.baskets), CategoryPopularity().fit(self.baskets),
            AssociationRules().fit(self.baskets, 1), ItemItemCooccurrence().fit(self.baskets),
        )
        for model in models:
            first = model.recommend(("name:a",), 2)
            self.assertEqual(first, model.recommend(("name:a",), 2))
            self.assertLessEqual(len(first), 2)
            self.assertNotIn("name:a", [key for key, _ in first])

    def test_empty_and_unseen_baskets_are_supported(self) -> None:
        for model in (
            GlobalPopularity().fit(self.baskets), CategoryPopularity().fit(self.baskets),
            AssociationRules().fit(self.baskets, 1), ItemItemCooccurrence().fit(self.baskets),
        ):
            self.assertEqual(len(model.recommend((), 2)), 2)
            self.assertEqual(len(model.recommend(("name:unseen",), 2)), 2)

    def test_association_rules_record_support_confidence_and_lift(self) -> None:
        model = AssociationRules().fit(self.baskets, 1)
        metrics = model.rule_metrics["name:a"]["name:b"]
        self.assertEqual(set(metrics), {"support", "confidence", "lift", "support_count"})
        self.assertGreater(metrics["lift"], 0)


class LinearModelTests(unittest.TestCase):
    def test_fit_rank_and_reload_are_deterministic(self) -> None:
        cases = [
            EvaluationCase("1", "2024-01-01", "train", ("name:a",), "name:b"),
            EvaluationCase("2", "2024-01-02", "train", ("name:a",), "name:b"),
            EvaluationCase("3", "2024-01-03", "train", ("name:b",), "name:c"),
        ]
        model = LinearBasketRanker(l2=0.01, epochs=30, seed=3408).fit(cases, ("name:a", "name:b", "name:c"))
        expected = model.recommend(("name:a",), 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            save_model(model, path, "test-v1")
            loaded = load_model(path)
        self.assertEqual(expected, loaded.recommend(("name:a",), 2))
        self.assertNotIn("name:a", [key for key, _ in expected])
        self.assertEqual(len(loaded.recommend((), 2)), 2)
        self.assertEqual(len(loaded.recommend(("name:unseen",), 2)), 2)


class EvaluationAndInferenceTests(unittest.TestCase):
    def test_metric_values_with_one_hidden_target(self) -> None:
        result = evaluate_case(("target", "x", "y"), ("target",), (), 3)
        self.assertAlmostEqual(result["precision_at_k"], 1 / 3)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["hit_rate_at_k"], 1)
        self.assertEqual(result["ndcg_at_k"], 1.0)

    def test_selected_artifact_inference_schema_and_navigation_filter(self) -> None:
        inference = RecommendationInference(
            MODEL_DIR / "selected_model.json", DERIVED / "catalog_reconciliation.csv"
        )
        output = inference.recommend(("name:rice",), 68)
        self.assertNotIn("name:rice", [value["product_id"] for value in output])
        expected_fields = set(json.loads(
            (COMPONENT / "contracts/recommendation_inference.schema.json").read_text()
        )["required"])
        self.assertTrue(output)
        self.assertEqual(set(output[0]), expected_fields)
        navigable = [value for value in output if value["navigation_eligible"]]
        self.assertEqual(
            {value["product_id"] for value in navigable},
            {"name:banana", "name:bread", "name:milk", "name:pasta"},
        )
        self.assertTrue(all(value["shelf_id"] and value["pickup_node_id"] for value in navigable))

    def test_inference_top_k_and_unseen_input(self) -> None:
        inference = RecommendationInference(
            MODEL_DIR / "selected_model.json", DERIVED / "catalog_reconciliation.csv"
        )
        first = inference.recommend(("name:not-in-training",), 3)
        self.assertEqual(len(first), 3)
        self.assertEqual(first, inference.recommend(("name:not-in-training",), 3))


if __name__ == "__main__":
    unittest.main()
