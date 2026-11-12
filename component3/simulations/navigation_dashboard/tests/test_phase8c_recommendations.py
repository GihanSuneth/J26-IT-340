"""Live frozen-model recommendation and adaptive-route integration tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from component3.backend.recommendation.live_service import (
    EXPECTED_SELECTED_SHA256,
    LiveRecommendationService,
    get_live_recommendation_service,
)
from component3.simulations.navigation_dashboard.shared_session import SharedNavigationSession
from component3.simulations.navigation_dashboard.reco_policy import RecommendationPolicyConfig
from component3.simulations.navigation_dashboard.spatial_simulation import SpatialNavigationSimulation
from component3.simulations.navigation_dashboard.config import (
    NAVIGATION_FRONTEND_ROOT,
    RECOMMENDATION_FRONTEND_ROOT,
)


class Phase8CLiveRecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = SpatialNavigationSimulation()
        self.sim.set_products(("SIM-P-001", "SIM-P-002"))

    def test_frozen_artifact_is_cached_verified_and_never_reads_labels(self) -> None:
        service = get_live_recommendation_service()
        self.assertIs(service, get_live_recommendation_service())
        self.assertTrue(service.ready)
        self.assertEqual(service.artifact_sha256, EXPECTED_SELECTED_SHA256)
        self.assertEqual(service.model_name, "association_rules")
        self.assertFalse(service.status()["test_labels_loaded"])

    def test_current_basket_produces_verified_rank_preserving_action(self) -> None:
        state = self.sim.snapshot()
        recommendation = state["recommendations"][0]
        diagnostics = state["recommendation_diagnostics"]
        self.assertEqual(diagnostics["normalized_basket_input"], ["name:banana", "name:bread"])
        self.assertEqual(recommendation["product_id"], "SIM-P-004")
        self.assertEqual(recommendation["shelf_id"], "DEMO-SHELF-04")
        self.assertEqual(recommendation["pickup_node_id"], "N2_1")
        self.assertTrue(recommendation["navigation_eligible"])
        self.assertGreaterEqual(recommendation["route_detour_cost_m"], 0)
        self.assertEqual(state["route_revision"], 0)

    def test_accept_is_atomic_revision_bound_and_route_audited(self) -> None:
        before = self.sim.snapshot()
        recommendation = before["recommendations"][0]
        after = self.sim.accept_recommendation(recommendation["recommendation_id"], 0)
        self.assertEqual(after["shopping_list_revision"], 1)
        self.assertEqual(after["route_revision"], before["route_revision"] + 1)
        event = after["recommendation_events"][-1]
        self.assertEqual(event["previous_route_revision"], before["route_revision"])
        self.assertEqual(event["new_route_revision"], after["route_revision"])
        self.assertEqual(event["model_artifact_sha256"], EXPECTED_SELECTED_SHA256)

    def test_stale_accept_and_dismiss_do_not_mutate(self) -> None:
        before = self.sim.snapshot()
        recommendation = before["recommendations"][0]
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.sim.accept_recommendation(recommendation["recommendation_id"], 7)
        unchanged = self.sim.snapshot()
        self.assertEqual(unchanged["shopping_session"], before["shopping_session"])
        dismissed = self.sim.reject_recommendation(recommendation["recommendation_id"], 0)
        self.assertEqual(dismissed["shopping_list_revision"], 0)
        self.assertNotEqual(
            dismissed["recommendations"][0]["product_id"] if dismissed["recommendations"] else None,
            recommendation["product_id"],
        )

    def test_shared_command_id_makes_duplicate_acceptance_idempotent(self) -> None:
        shared = SharedNavigationSession(self.sim)
        recommendation = self.sim.snapshot()["recommendations"][0]
        payload = {
            "action": "accept_recommendation", "client_id": "test-client",
            "command_id": "accept-once", "recommendation_id": recommendation["recommendation_id"],
            "expected_shopping_revision": 0,
        }
        dispatcher = lambda action, body: self.sim.accept_recommendation(
            body["recommendation_id"], body["expected_shopping_revision"]
        )
        first = shared.apply(payload, dispatcher)
        second = shared.apply(payload, dispatcher)
        self.assertEqual(first, second)
        self.assertEqual(self.sim.shopping_session.revision, 1)

    def test_mid_edge_accept_replans_from_edge_anchor(self) -> None:
        self.sim.enter_free_walk()
        self.sim.choose_free_walk_edge(self.sim.free_walk_options()[0]["node_id"])
        self.sim.step(2)
        recommendation = self.sim.snapshot()["recommendations"][0]
        result = self.sim.accept_recommendation(recommendation["recommendation_id"], 0)
        self.assertEqual(result["route_anchor"]["anchor_type"], "edge")
        self.assertGreater(result["adaptive_replan_history"][-1]["partial_edge_distance_m"], 0)

    def test_no_eligible_and_unavailable_model_are_safe(self) -> None:
        self.sim.set_products(tuple(self.sim.products_by_id))
        no_candidate = self.sim.snapshot()
        self.assertEqual(no_candidate["recommendations"], [])
        self.assertEqual(no_candidate["recommendation_diagnostics"]["fallback_state"], "no_eligible_candidate")
        with tempfile.TemporaryDirectory() as directory:
            unavailable = LiveRecommendationService(Path(directory) / "missing.json")
            simulation = SpatialNavigationSimulation(recommendation_service=unavailable)
        state = simulation.snapshot()
        self.assertFalse(state["recommendation_diagnostics"]["inference_ready"])
        self.assertEqual(state["recommendations"], [])
        self.assertTrue(state["planned_route"])

    def test_camera_state_and_multi_view_reads_do_not_change_recommendation(self) -> None:
        before = self.sim.snapshot()
        shared = SharedNavigationSession(self.sim)
        first_view = shared.snapshot()
        second_view = shared.snapshot()
        self.assertEqual(first_view["recommendations"], second_view["recommendations"])
        self.sim.camera_stopped()
        after = self.sim.snapshot()
        self.assertEqual(before["recommendations"], after["recommendations"])

    def test_customer_and_operator_assets_expose_guarded_contract(self) -> None:
        customer_html = (NAVIGATION_FRONTEND_ROOT / "customer.html").read_text(encoding="utf-8")
        customer_js = (NAVIGATION_FRONTEND_ROOT / "customer.js").read_text(encoding="utf-8")
        operator_html = (NAVIGATION_FRONTEND_ROOT / "spatial.html").read_text(encoding="utf-8")
        operator_js = (NAVIGATION_FRONTEND_ROOT / "spatial.js").read_text(encoding="utf-8")
        recommendation_html = (RECOMMENDATION_FRONTEND_ROOT / "recommendations.html").read_text(encoding="utf-8")
        recommendation_js = (RECOMMENDATION_FRONTEND_ROOT / "recommendations.js").read_text(encoding="utf-8")
        self.assertNotIn("Experimental recommendation", customer_html)
        self.assertIn("Passive suggestion", recommendation_html)
        self.assertIn("standalone_accept_recommendation", recommendation_js)
        self.assertIn("expected_shopping_revision", recommendation_js)
        self.assertNotIn("purchase probability", customer_js.lower())
        self.assertIn("recommendation-diagnostics-heading", operator_html)
        self.assertIn("candidate_ranking", operator_js)
        self.assertIn("filter_reasons", operator_js)

    def test_three_item_demo_gate_offers_milk(self) -> None:
        simulation = SpatialNavigationSimulation(
            recommendation_policy=RecommendationPolicyConfig(min_distinct_items=3)
        )
        state = simulation.set_products(("SIM-P-001", "SIM-P-002", "SIM-P-004"))
        self.assertEqual(state["recommendations"][0]["product_id"], "SIM-P-003")
        self.assertEqual(state["recommendation_diagnostics"]["distinct_cart_item_count"], 3)

    def test_unmapped_items_count_for_five_item_gate_but_not_model_input(self) -> None:
        simulation = SpatialNavigationSimulation(
            recommendation_policy=RecommendationPolicyConfig(min_distinct_items=5)
        )
        state = simulation.set_products(
            ("SIM-P-001", "SIM-P-002", "SIM-P-004", "SIM-P-005", "SIM-P-006")
        )
        diagnostics = state["recommendation_diagnostics"]
        self.assertEqual(state["recommendations"][0]["product_id"], "SIM-P-003")
        self.assertEqual(diagnostics["distinct_cart_item_count"], 5)
        self.assertEqual(diagnostics["mapped_model_input_count"], 3)
        self.assertEqual(diagnostics["unmapped_demo_product_ids"], ["SIM-P-005", "SIM-P-006"])

    def test_below_gate_has_no_customer_card_and_keeps_analysis(self) -> None:
        simulation = SpatialNavigationSimulation(
            recommendation_policy=RecommendationPolicyConfig(min_distinct_items=3)
        )
        state = simulation.set_products(("SIM-P-001", "SIM-P-002"))
        self.assertEqual(state["recommendations"], [])
        self.assertEqual(
            state["recommendation_diagnostics"]["policy"]["reasons"],
            ["below_minimum_distinct_items"],
        )
        self.assertGreater(len(state["recommendation_diagnostics"]["candidate_ranking"]), 0)

    def test_two_suggestion_trip_limit_and_dismissal_memory(self) -> None:
        first = self.sim.snapshot()["recommendations"][0]
        second_state = self.sim.reject_recommendation(first["recommendation_id"], 0)
        second = second_state["recommendations"][0]
        self.assertNotEqual(second["product_id"], first["product_id"])
        stable = self.sim.snapshot()
        self.assertEqual(stable["recommendations"][0]["product_id"], second["product_id"])
        final = self.sim.reject_recommendation(second["recommendation_id"], 0)
        self.assertEqual(final["recommendations"], [])
        self.assertIn(
            "max_suggestions_per_trip_reached",
            final["recommendation_diagnostics"]["policy"]["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
