"""Tests for exact node and mid-edge route starts."""

from __future__ import annotations

import unittest

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import PositionEstimate
from component3.backend.comp3_reco_navigation.navigation.route_anchor import (
    edge_route_anchor,
    held_karp_route_from_anchor,
    node_route_anchor,
    route_anchor_from_position,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import StoreGraph


def graph() -> StoreGraph:
    return StoreGraph.from_dict(
        {
            "nodes": [
                {"id": "A", "name": "A", "type": "lane", "x_m": 0, "y_m": 0},
                {"id": "B", "name": "B", "type": "lane", "x_m": 10, "y_m": 0},
                {"id": "C", "name": "C", "type": "product", "x_m": 10, "y_m": 4},
                {"id": "D", "name": "D", "type": "checkout", "x_m": 14, "y_m": 4},
            ],
            "edges": [
                {"source": "A", "target": "B", "distance_m": 10},
                {"source": "B", "target": "C", "distance_m": 4},
                {"source": "C", "target": "D", "distance_m": 4},
                {"source": "A", "target": "D", "distance_m": 30},
            ],
        }
    )


class RouteAnchorTests(unittest.TestCase):
    def test_node_anchor_has_zero_partial_cost(self) -> None:
        store = graph()
        plan = held_karp_route_from_anchor(
            store, node_route_anchor(store, "B", route_revision=2), ["C"], "D"
        )
        self.assertEqual(plan.route_node_ids, ("B", "C", "D"))
        self.assertEqual(plan.partial_edge_distance_m, 0.0)
        self.assertEqual(plan.total_distance_m, 8.0)

    def test_mid_edge_cost_includes_independent_partial_distance(self) -> None:
        store = graph()
        anchor = edge_route_anchor(store, "A", "B", 7.0)
        plan = held_karp_route_from_anchor(store, anchor, ["C"], "D")
        # Independently: 3 m to B + 4 m B-C + 4 m C-D = 11 m.
        self.assertEqual(plan.chosen_endpoint_node_id, "B")
        self.assertEqual(plan.partial_edge_distance_m, 3.0)
        self.assertEqual(plan.graph_route_distance_m, 8.0)
        self.assertEqual(plan.total_distance_m, 11.0)

    def test_direction_can_bound_route_to_forward_endpoint(self) -> None:
        store = graph()
        anchor = edge_route_anchor(
            store, "A", "B", 2.0, travel_direction="toward_end"
        )
        plan = held_karp_route_from_anchor(
            store, anchor, [], "D", allow_reverse=False
        )
        self.assertEqual(plan.chosen_endpoint_node_id, "B")
        self.assertEqual(plan.partial_edge_distance_m, 8.0)
        self.assertEqual(plan.total_distance_m, 16.0)

    def test_estimated_pose_projection_preserves_both_endpoint_distances(self) -> None:
        store = graph()
        anchor = route_anchor_from_position(
            store, PositionEstimate(2.5, 0.1, 0.0, 1.0), max_snap_distance_m=0.2
        )
        self.assertEqual(anchor.anchor_type, "edge")
        self.assertAlmostEqual(anchor.distance_to_start_m, 2.5)
        self.assertAlmostEqual(anchor.distance_to_end_m, 7.5)
        self.assertAlmostEqual(anchor.snap_distance_m, 0.1)


if __name__ == "__main__":
    unittest.main()
