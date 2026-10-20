"""Phase 8A parsing, baskets, leakage, mapping, baselines and API contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from component3.backend.comp3_reco_navigation.api.recommend import validate_recommendation_output
from component3.backend.comp3_reco_navigation.recommendation.baselines import (
    AssociationRules, CategoryPopularity, GlobalPopularity, ItemItemCooccurrence,
)
from component3.backend.comp3_reco_navigation.recommendation.catalog_mapping import reconcile_catalog
from component3.backend.comp3_reco_navigation.recommendation.evaluation import evaluate_case
from component3.backend.comp3_reco_navigation.recommendation.preprocess import (
    Basket, BasketItem, basket_completion_case, chronological_split,
    read_transactions, reconstruct_baskets,
)


ROOT = Path(__file__).resolve().parents[4]
CATALOG = ROOT / "component3/data/demo_store/v1/demo_store.json"


def item(name: str, category: str = "Pantry", quantity: int = 1) -> BasketItem:
    key = f"name:{name.lower().replace(' ', '-')}"
    return BasketItem(key, name, category, quantity, ("source-id",), 1)


def basket(number: int, items: tuple[BasketItem, ...]) -> Basket:
    return Basket(str(number), datetime(2024, 1, 1) + timedelta(days=number), "user", items, len(items))


class DatasetParsingTests(unittest.TestCase):
    def test_single_digit_hour_and_repeated_lines_parse_and_aggregate(self) -> None:
        content = (
            "order_id,user_id,order_date,time,order_hour_of_day,product_name,quantity,price,category,product_id\n"
            "1,u1,2024-01-02,8:05:00,8,Pasta,1,10.00,Pantry,100\n"
            "1,u1,2024-01-02,8:05:00,8,Pasta,2,10.00,Pantry,200\n"
            "1,u1,2024-01-02,8:05:00,8,Bread,1,20.00,Bakery,300\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.csv"
            path.write_text(content, encoding="utf-8")
            lines, rejects = read_transactions(path)
        self.assertEqual(rejects, [])
        baskets, excluded = reconstruct_baskets(lines)
        self.assertEqual(excluded, [])
        self.assertEqual(len(baskets), 1)
        pasta = next(value for value in baskets[0].items if value.product_name == "Pasta")
        self.assertEqual((pasta.quantity, pasta.line_count), (3, 2))
        self.assertEqual(pasta.source_product_ids, ("100", "200"))


class LeakageTests(unittest.TestCase):
    def test_chronological_partitions_have_disjoint_signatures(self) -> None:
        values = [
            basket(1, (item("A"), item("B"))),
            basket(2, (item("A"), item("C"))),
            basket(3, (item("A"), item("D"))),
            basket(4, (item("B"), item("C"))),
            basket(5, (item("C"), item("D"))),
            basket(6, (item("A"), item("B"))),
        ]
        split = chronological_split(values)
        signatures = [{entry.signature for entry in part} for part in (split.train, split.validation, split.test)]
        self.assertTrue(signatures[0].isdisjoint(signatures[1]))
        self.assertTrue(signatures[0].isdisjoint(signatures[2]))
        self.assertIn("6", split.purged_duplicate_basket_ids)

    def test_hidden_target_is_deterministic_and_absent_from_input(self) -> None:
        value = basket(10, (item("A"), item("B"), item("C")))
        first = basket_completion_case(value, 3408)
        self.assertEqual(first, basket_completion_case(value, 3408))
        self.assertNotIn(first[1], first[0])


class CatalogMappingTests(unittest.TestCase):
    def test_only_product_level_mapping_with_route_is_navigable(self) -> None:
        values = [basket(1, (
            item("Pasta", "Grains & Staples"),
            item("Rice", "Grains & Staples"),
            item("Marker", "Stationery"),
        ))]
        mappings = {mapping.source_product_name: mapping for mapping in reconcile_catalog(values, CATALOG)}
        self.assertEqual(mappings["Pasta"].mapping_status, "normalized_name_mapping")
        self.assertTrue(mappings["Pasta"].navigation_eligible)
        self.assertEqual(mappings["Rice"].mapping_status, "category_level_mapping")
        self.assertFalse(mappings["Rice"].navigation_eligible)
        self.assertEqual(mappings["Marker"].mapping_status, "unmapped_product")


class BaselineAndMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baskets = [
            basket(1, (item("A"), item("B", "Bakery"))),
            basket(2, (item("A"), item("C", "Bakery"))),
            basket(3, (item("A"), item("B", "Bakery"))),
        ]

    def test_baselines_never_return_observed_item(self) -> None:
        for model in (
            GlobalPopularity().fit(self.baskets), CategoryPopularity().fit(self.baskets),
            AssociationRules().fit(self.baskets, min_support_count=1),
            ItemItemCooccurrence().fit(self.baskets),
        ):
            output = model.recommend(("name:a",), 2)
            self.assertNotIn("name:a", [key for key, _ in output])

    def test_top_k_metrics_and_observed_tracking(self) -> None:
        result = evaluate_case(("B", "A", "C"), ("B",), ("A",), 2)
        self.assertEqual(result["precision_at_k"], 0.5)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["already_observed_count"], 1)


class RecommendationContractTests(unittest.TestCase):
    def test_schema_declares_phase8a_fields(self) -> None:
        schema = json.loads((ROOT / "component3/contracts/recommendation_output.schema.json").read_text())
        self.assertTrue({"mapping_status", "shelf_availability", "navigation_eligible"} <= set(schema["required"]))

    def test_navigable_candidate_requires_route_destination(self) -> None:
        payload = {
            "recommendation_id": "R-1", "product_id": "SIM-P-004",
            "recommendation_source": "item_item_cooccurrence", "model_version": "candidate-v1",
            "score": 0.8, "display_explanation": "Often selected with your basket.",
            "mapping_status": "normalized_name_mapping", "shelf_availability": "available",
            "shelf_id": "DEMO-SHELF-04", "pickup_node_id": "N2_1",
            "navigation_eligible": True, "route_detour_cost_m": 2.5,
            "acceptance_status": "pending",
        }
        self.assertEqual(validate_recommendation_output(payload)["product_id"], "SIM-P-004")
        payload["pickup_node_id"] = None
        with self.assertRaisesRegex(ValueError, "shelf and pickup node"):
            validate_recommendation_output(payload)


if __name__ == "__main__":
    unittest.main()
