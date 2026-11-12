"""Task IJ contracts for the two independent research demonstrations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from component3.simulations.navigation_dashboard.dashboard import make_handler
from component3.simulations.navigation_dashboard.config import (
    COMPONENT_ROOT,
    NAVIGATION_FRONTEND_ROOT,
    RECOMMENDATION_FRONTEND_ROOT,
)


STATIC = NAVIGATION_FRONTEND_ROOT


class StandaloneDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handlers = []

    def tearDown(self) -> None:
        for handler in self.handlers:
            handler.camera_scanner.stop()
            handler.stop_background()

    def handler(self, mode: str):
        handler = make_handler(mode=mode)
        self.handlers.append(handler)
        return handler

    def test_wishlist_does_not_plan_or_infer(self) -> None:
        handler = self.handler("navigation")
        workflow = handler.standalone_workflow
        workflow.navigation_action("wishlist_add", {"product_id": "SIM-P-001"})
        state = workflow.enrich(handler.shared_session.snapshot())
        self.assertEqual([row["product_id"] for row in state["wishlist_items"]], ["SIM-P-001"])
        self.assertEqual(state["selected_product_ids"], [])
        self.assertEqual(state["planned_route"], [])
        self.assertEqual(state["recommendation_diagnostics"]["reason"], "standalone_navigation_mode")

    def test_wishlist_remove_also_removes_navigation_selection(self) -> None:
        handler = self.handler("navigation")
        workflow = handler.standalone_workflow
        workflow.navigation_action("wishlist_add", {"product_id": "SIM-P-001"})
        workflow.navigation_action("navigation_basket_add", {"product_id": "SIM-P-001"})
        workflow.navigation_action("wishlist_remove", {"product_id": "SIM-P-001"})
        state = workflow.enrich(handler.shared_session.snapshot())
        self.assertEqual(state["wishlist_items"], [])
        self.assertEqual(state["navigation_basket_items"], [])

    def test_navigation_basket_requires_wishlist_and_plan_is_explicit(self) -> None:
        handler = self.handler("navigation")
        workflow = handler.standalone_workflow
        with self.assertRaisesRegex(ValueError, "wishlist"):
            workflow.navigation_action("navigation_basket_add", {"product_id": "SIM-P-002"})
        workflow.navigation_action("wishlist_add", {"product_id": "SIM-P-002"})
        workflow.navigation_action("navigation_basket_add", {"product_id": "SIM-P-002"})
        before = workflow.enrich(handler.shared_session.snapshot())
        self.assertEqual(before["planned_route"], [])
        workflow.navigation_action("plan_navigation_route", {})
        after = workflow.enrich(handler.shared_session.snapshot())
        self.assertEqual(after["selected_product_ids"], ["SIM-P-002"])
        self.assertTrue(after["planned_route"])

    def test_shared_pickup_checkpoint_is_deduplicated(self) -> None:
        handler = self.handler("navigation")
        workflow = handler.standalone_workflow
        second = dict(workflow.simulation.products_by_id["SIM-P-002"])
        original = workflow.simulation.products_by_id["SIM-P-002"]
        second["pickup_node_id"] = workflow.simulation.products_by_id["SIM-P-001"]["pickup_node_id"]
        second["shelf_id"] = workflow.simulation.products_by_id["SIM-P-001"]["shelf_id"]
        workflow.simulation.products_by_id["SIM-P-002"] = second
        try:
            for product in ("SIM-P-001", "SIM-P-002"):
                workflow.navigation_action("wishlist_add", {"product_id": product})
                workflow.navigation_action("navigation_basket_add", {"product_id": product})
            state = workflow.enrich(handler.shared_session.snapshot())
            self.assertEqual(len(state["navigation_destinations"]), 1)
            self.assertEqual(set(state["navigation_destinations"][0]["product_ids"]), {"SIM-P-001", "SIM-P-002"})
        finally:
            workflow.simulation.products_by_id["SIM-P-002"] = original

    def test_unverified_location_is_reported_and_not_routed(self) -> None:
        handler = self.handler("navigation")
        workflow = handler.standalone_workflow
        original = workflow.simulation.products_by_id["SIM-P-001"]
        broken = dict(original); broken["pickup_node_id"] = "NOT-IN-GRAPH"
        workflow.simulation.products_by_id["SIM-P-001"] = broken
        try:
            workflow.navigation_action("wishlist_add", {"product_id": "SIM-P-001"})
            workflow.navigation_action("navigation_basket_add", {"product_id": "SIM-P-001"})
            with self.assertRaisesRegex(ValueError, "verified store location"):
                workflow.navigation_action("plan_navigation_route", {})
            state = workflow.enrich(handler.shared_session.snapshot())
            self.assertEqual(state["unresolved_products"][0]["reason"], "pickup_node_not_in_active_graph")
            self.assertEqual(state["planned_route"], [])
        finally:
            workflow.simulation.products_by_id["SIM-P-001"] = original

    def test_navigation_and_recommendation_sessions_are_independent(self) -> None:
        navigation = self.handler("navigation")
        recommendation = self.handler("recommendation")
        navigation.standalone_workflow.navigation_action("wishlist_add", {"product_id": "SIM-P-001"})
        recommendation.standalone_workflow.recommendation_action("confirmed_cart_add", {"product_id": "SIM-P-002"})
        recommendation_before = recommendation.standalone_workflow.enrich(recommendation.shared_session.snapshot())
        navigation.standalone_workflow.reset()
        recommendation_after = recommendation.standalone_workflow.enrich(recommendation.shared_session.snapshot())
        self.assertEqual(recommendation_before["confirmed_cart_items"], recommendation_after["confirmed_cart_items"])
        self.assertNotEqual(navigation.shared_session.session_id, recommendation.shared_session.session_id)

    def test_three_confirmed_items_offer_actual_milk_result(self) -> None:
        with patch.dict(os.environ, {"COMP3_RECO_MIN_ITEMS": "3"}):
            handler = self.handler("recommendation")
        workflow = handler.standalone_workflow
        for product in ("SIM-P-001", "SIM-P-002", "SIM-P-004"):
            workflow.recommendation_action("confirmed_cart_add", {"product_id": product})
        state = workflow.enrich(handler.shared_session.snapshot())
        self.assertEqual(state["recommendations"][0]["product_id"], "SIM-P-003")
        self.assertEqual(state["recommendations"][0]["product_name"], "Milk carton")

    def test_acceptance_does_not_confirm_physical_collection(self) -> None:
        handler = self.handler("recommendation")
        workflow = handler.standalone_workflow
        for product in ("SIM-P-001", "SIM-P-002", "SIM-P-004"):
            workflow.recommendation_action("confirmed_cart_add", {"product_id": product})
        before = workflow.enrich(handler.shared_session.snapshot())
        suggestion = before["recommendations"][0]
        workflow.recommendation_action("standalone_accept_recommendation", {
            "recommendation_id": suggestion["recommendation_id"],
            "expected_shopping_revision": before["shopping_list_revision"],
        })
        after = workflow.enrich(handler.shared_session.snapshot())
        self.assertEqual(before["confirmed_cart_items"], after["confirmed_cart_items"])
        self.assertIn(suggestion["product_id"], [row["product_id"] for row in after["accepted_suggestion_items"]])

    def test_recommendation_reset_clears_trip_state_only(self) -> None:
        navigation = self.handler("navigation")
        recommendation = self.handler("recommendation")
        navigation.standalone_workflow.navigation_action("wishlist_add", {"product_id": "SIM-P-006"})
        recommendation.standalone_workflow.recommendation_action("confirmed_cart_add", {"product_id": "SIM-P-001"})
        recommendation.standalone_workflow.reset()
        reco = recommendation.standalone_workflow.enrich(recommendation.shared_session.snapshot())
        nav = navigation.standalone_workflow.enrich(navigation.shared_session.snapshot())
        self.assertEqual(reco["confirmed_cart_items"], [])
        self.assertEqual(reco["recommendation_wishlist_items"], [])
        self.assertEqual(nav["wishlist_items"][0]["product_id"], "SIM-P-006")

    def test_frozen_artifact_checksum_matches_loaded_bytes(self) -> None:
        handler = self.handler("recommendation")
        service = handler.shared_session.simulation._recommendation_service
        artifact = service.model_path
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), service.artifact_sha256)

    def test_customer_is_simplified_and_operator_retains_full_map(self) -> None:
        customer = (STATIC / "customer.js").read_text(encoding="utf-8")
        operator = (STATIC / "spatial.js").read_text(encoding="utf-8")
        self.assertIn("visibleSegment", customer)
        self.assertNotIn("map.shelves || []", customer)
        self.assertIn("map.shelves", operator)

    def test_archived_evidence_wording_remains_present(self) -> None:
        evidence = json.loads(
            (RECOMMENDATION_FRONTEND_ROOT / "reco_evidence.json").read_text(encoding="utf-8")
        )
        self.assertIn("HitRate@5 4.7%", evidence["wording"])
        self.assertIn("validation 9.4%", evidence["wording"])

    def test_shared_voice_preference_is_session_state(self) -> None:
        handler = self.handler("navigation")
        handler.shared_session.set_voice_preference(True, "Example en-US", 0.7)
        preference = handler.shared_session.snapshot()["voice_preference"]
        self.assertEqual(preference, {"enabled": True, "voice_name": "Example en-US", "volume": 0.7})
        customer = (STATIC / "customer.js").read_text(encoding="utf-8")
        operator = (STATIC / "spatial.js").read_text(encoding="utf-8")
        self.assertIn("voice_preference", customer)
        self.assertIn("VOICE_PREFERENCE_KEY", operator)
        self.assertIn("/^en-US/i", operator)

    def test_launchers_are_local_only_and_open_the_expected_modes(self) -> None:
        run = COMPONENT_ROOT / "run"
        navigation = (run / "start_navigation_demo.sh").read_text(encoding="utf-8")
        recommendation = (run / "start_recommendation_demo.sh").read_text(encoding="utf-8")
        self.assertIn("--mode navigation --host 127.0.0.1", navigation)
        self.assertIn('URL="http://127.0.0.1:${PORT}/"', navigation)
        self.assertIn("--mode recommendation --host 127.0.0.1", recommendation)
        self.assertIn('URL="http://127.0.0.1:${PORT}/recommendations"', recommendation)


if __name__ == "__main__":
    unittest.main()
