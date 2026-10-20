"""Live frozen-model recommendation and adaptive-route integration tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from component3.backend.comp3_reco_navigation.recommendation.live_service import (
    EXPECTED_SELECTED_SHA256,
    LiveRecommendationService,
    get_live_recommendation_service,
)
from component3.simulations.navigation_dashboard.shared_session import SharedNavigationSession
from component3.simulations.navigation_dashboard.spatial_simulation import SpatialNavigationSimulation


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
        static = Path(__file__).resolve().parents[1] / "static"
        customer_html = (static / "customer.html").read_text(encoding="utf-8")
        customer_js = (static / "customer.js").read_text(encoding="utf-8")
        operator_html = (static / "spatial.html").read_text(encoding="utf-8")
        operator_js = (static / "spatial.js").read_text(encoding="utf-8")
        self.assertIn("Experimental recommendation", customer_html)
        self.assertIn("route_detour_cost_m", customer_js)
        self.assertIn("expected_shopping_revision", customer_js)
        self.assertNotIn("purchase probability", customer_js.lower())
        self.assertIn("recommendation-diagnostics-heading", operator_html)
        self.assertIn("candidate_ranking", operator_js)
        self.assertIn("filter_reasons", operator_js)


if __name__ == "__main__":
    unittest.main()
