"""Dynamic shopping mutation and anchored reoptimization tests."""

from __future__ import annotations

import unittest

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    DeadReckoner,
    PositionEstimate,
)
from component3.simulations.navigation_dashboard.spatial_simulation import (
    SpatialNavigationSimulation,
)


class DynamicShoppingSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = SpatialNavigationSimulation()
        self.sim.set_products(["SIM-P-001", "SIM-P-002"])

    def test_add_during_mid_edge_navigation_reoptimizes_without_reset(self) -> None:
        self.sim.enter_free_walk()
        target = self.sim.free_walk_options()[0]["node_id"]
        self.sim.choose_free_walk_edge(target)
        self.sim.step(3)
        before = self.sim.snapshot()
        result = self.sim.mutate_shopping_list(
            "add", "SIM-P-003", 1, before["shopping_list_revision"]
        )
        self.assertEqual(result["simulation_time_s"], before["simulation_time_s"])
        self.assertEqual(result["ground_truth"], before["ground_truth"])
        self.assertEqual(result["shopping_list_revision"], 1)
        self.assertEqual(result["route_revision"], before["route_revision"] + 1)
        self.assertEqual(result["route_anchor"]["anchor_type"], "edge")
        self.assertGreater(
            result["adaptive_replan_history"][-1]["partial_edge_distance_m"], 0
        )

    def test_remove_and_quantity_changes_preserve_localization_history(self) -> None:
        before = self.sim.snapshot()
        changed = self.sim.mutate_shopping_list("increase", "SIM-P-001", 2, 0)
        changed = self.sim.mutate_shopping_list("decrease_remaining", "SIM-P-001", 1, 1)
        changed = self.sim.mutate_shopping_list("remove", "SIM-P-002", 1, 2)
        line = next(
            item for item in changed["shopping_session"]["items"]
            if item["product_id"] == "SIM-P-001"
        )
        self.assertEqual((line["requested_quantity"], line["remaining_quantity"]), (2, 2))
        self.assertEqual(changed["detected_checkpoint_ids"], before["detected_checkpoint_ids"])
        self.assertEqual(changed["estimate"], before["estimate"])
        self.assertEqual(changed["shopping_list_revision"], 3)

    def test_stale_or_invalid_mutation_is_atomic(self) -> None:
        before = self.sim.snapshot()
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.sim.mutate_shopping_list("add", "SIM-P-003", 1, 7)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.sim.mutate_shopping_list("add", "NOT-A-PRODUCT", 1, 0)
        after = self.sim.snapshot()
        for field in (
            "shopping_session", "planned_route", "route_revision", "estimate",
            "checkpoint_observation_history",
        ):
            self.assertEqual(after[field], before[field])

    def test_pickup_confirms_one_unit_and_keeps_remaining_shelf_destination(self) -> None:
        self.sim.mutate_shopping_list("increase", "SIM-P-001", 1, 0)
        self.sim.current_node_id = "N1_1"
        node = self.sim.graph.node("N1_1")
        self.sim.true_x_m, self.sim.true_y_m = node.x_m, node.y_m
        self.sim.estimator = DeadReckoner(
            PositionEstimate(node.x_m, node.y_m, 0.0, self.sim.simulation_time_s)
        )
        self.sim.status = "awaiting_product_confirmation"
        self.sim.running = False
        self.sim._arrived_product_id = "SIM-P-001"
        result = self.sim.confirm_product(expected_shopping_revision=1)
        line = next(
            item for item in result["shopping_session"]["items"]
            if item["product_id"] == "SIM-P-001"
        )
        self.assertEqual((line["collected_quantity"], line["remaining_quantity"]), (1, 1))
        self.assertEqual(result["status"], "awaiting_product_confirmation")
        self.assertIn("N1_1", self.sim.route_manager.remaining_destinations)

    def test_accepted_recommendation_uses_normal_mutation_pipeline(self) -> None:
        recommendation = self.sim.snapshot()["recommendations"][0]
        result = self.sim.accept_recommendation(recommendation["recommendation_id"], 0)
        line = next(
            item for item in result["shopping_session"]["items"]
            if item["product_id"] == recommendation["product_id"]
        )
        self.assertEqual(line["source"], "accepted_recommendation")
        event = result["recommendation_events"][-1]
        self.assertEqual(event["event_type"], "accepted")
        self.assertEqual(event["recommendation_id"], recommendation["recommendation_id"])
        self.assertEqual(event["shopping_revision_after"], 1)

    def test_add_after_checkout_reopens_from_checkout_without_erasing_history(self) -> None:
        simulation = SpatialNavigationSimulation(speed_m_s=1.6)
        simulation.set_products([])
        simulation.start()
        for _ in range(500):
            if simulation.status == "complete":
                break
            simulation.step()
        self.assertEqual(simulation.status, "complete")
        checkout_state = simulation.snapshot()
        reopened = simulation.mutate_shopping_list("add", "SIM-P-003", 1, 0)
        self.assertEqual(reopened["status"], "ready")
        self.assertFalse(reopened["running"])
        self.assertEqual(reopened["current_node_id"], simulation.checkout_node_id)
        self.assertEqual(reopened["ground_truth"], checkout_state["ground_truth"])
        self.assertEqual(reopened["planned_route"][0], simulation.checkout_node_id)
        self.assertEqual(reopened["planned_route"][-1], simulation.checkout_node_id)


if __name__ == "__main__":
    unittest.main()
