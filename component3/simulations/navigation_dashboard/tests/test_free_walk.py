"""Free-walk, adaptive checkpoint, and anchored replanning tests."""

from __future__ import annotations

import unittest

from component3.backend.comp3_reco_navigation.navigation.dijkstra import dijkstra_shortest_path
from component3.backend.comp3_reco_navigation.navigation.held_karp import held_karp_route
from component3.simulations.navigation_dashboard.spatial_simulation import (
    SpatialNavigationSimulation,
)


def walk_edge(simulation: SpatialNavigationSimulation, target: str) -> None:
    simulation.choose_free_walk_edge(target)
    for _ in range(100):
        state = simulation.step()
        if state["status"] == "free_walk_stopped":
            return
    raise AssertionError(f"Free walk did not reach {target}")


class FreeWalkTests(unittest.TestCase):
    def test_free_walk_rejects_non_adjacent_edge_and_moves_only_on_graph(self) -> None:
        simulation = SpatialNavigationSimulation(speed_m_s=1.6)
        entered = simulation.enter_free_walk()
        self.assertEqual(entered["status"], "free_walk_stopped")
        self.assertEqual(
            {item["node_id"] for item in entered["free_walk"]["available_edges"]},
            {"N0_1", "N1_0"},
        )
        with self.assertRaisesRegex(ValueError, "not adjacent"):
            simulation.choose_free_walk_edge("N4_5")
        before = simulation.snapshot()["ground_truth"]
        simulation.choose_free_walk_edge("N0_1")
        moved = simulation.step(2)
        self.assertEqual(moved["simulation_time_s"], 0.5)
        self.assertNotEqual(moved["ground_truth"], before)
        self.assertAlmostEqual(moved["ground_truth"]["y_m"], 1.0)
        stopped = simulation.stop_free_walk()
        self.assertEqual(stopped["status"], "free_walk_stopped")
        self.assertFalse(stopped["running"])
        self.assertEqual(simulation.resume_free_walk()["status"], "free_walking")

    def test_mid_edge_navigation_includes_exact_partial_edge_cost(self) -> None:
        simulation = SpatialNavigationSimulation(speed_m_s=0.8)
        simulation.enter_free_walk()
        simulation.choose_free_walk_edge("N0_1")
        simulation.step(5)  # 1.0 m on the 4.0 m edge.
        simulation.stop_free_walk()
        truth_before = dict(simulation.snapshot()["ground_truth"])
        replanned = simulation.request_navigation_from_current_location()
        anchor = replanned["route_anchor"]
        record = replanned["adaptive_replan_history"][-1]
        endpoint = record["chosen_endpoint_node_id"]
        expected_graph = held_karp_route(
            simulation.graph,
            endpoint,
            simulation.route_manager.remaining_destinations,
            simulation.checkout_node_id,
        ).total_distance_m
        self.assertEqual(anchor["anchor_type"], "edge")
        self.assertGreater(record["partial_edge_distance_m"], 0.0)
        self.assertAlmostEqual(
            record["new_route_cost_m"],
            record["partial_edge_distance_m"] + expected_graph,
        )
        self.assertIn(endpoint, {"N0_0", "N0_1"})
        self.assertEqual(replanned["ground_truth"], truth_before)
        self.assertEqual(replanned["status"], "navigating")

    def test_unexpected_plausible_checkpoint_corrects_and_replans_without_truth_teleport(self) -> None:
        simulation = SpatialNavigationSimulation(speed_m_s=1.6)
        simulation.enter_free_walk()
        path = dijkstra_shortest_path(simulation.graph, "N0_0", "N4_5").node_ids
        self.assertNotIn("N2_3", path)
        for target in path[1:]:
            walk_edge(simulation, target)
        before = simulation.snapshot()
        self.assertEqual(before["current_node_id"], "N4_5")
        self.assertEqual(before["next_checkpoint"]["checkpoint_id"], 201)
        observed = simulation.observe_checkpoint(
            {
                "tag_id": 202,
                "timestamp_s": before["simulation_time_s"],
                "detection_source": "adaptive_evaluation",
            }
        )
        self.assertTrue(observed["observed_checkpoint"]["accepted"])
        self.assertEqual(
            observed["observed_checkpoint"]["classification"],
            "unexpected_but_plausible_mapped_checkpoint",
        )
        self.assertEqual(observed["ground_truth"], before["ground_truth"])
        self.assertEqual(observed["last_replanning_reason"], "accepted_unexpected_mapped_checkpoint")
        self.assertEqual(observed["route_revision"], 1)
        self.assertEqual(observed["collected_product_ids"], before["collected_product_ids"])
        self.assertEqual(observed["selected_product_ids"], before["selected_product_ids"])

    def test_rejected_observations_preserve_pose_checkpoint_and_route(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.enter_free_walk()
        before = simulation.snapshot()
        rejected = simulation.observe_checkpoint(
            {
                "tag_id": 202,
                "timestamp_s": 0.25,
                "detection_source": "adaptive_evaluation",
            }
        )
        self.assertEqual(rejected["observed_checkpoint"]["reason"], "spatially_implausible_observation")
        self.assertEqual(rejected["estimate"], before["estimate"])
        self.assertEqual(rejected["last_confirmed_checkpoint"], before["last_confirmed_checkpoint"])
        self.assertEqual(rejected["planned_route"], before["planned_route"])
        unknown = simulation.observe_checkpoint(
            {
                "tag_id": 999,
                "timestamp_s": 0.5,
                "detection_source": "adaptive_evaluation",
            }
        )
        self.assertEqual(unknown["observed_checkpoint"]["classification"], "unknown_marker")
        self.assertEqual(unknown["estimate"], before["estimate"])


if __name__ == "__main__":
    unittest.main()
