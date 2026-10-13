"""Test map adaptation and route-planning behavior for the dashboard."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    StoreGraph,
    load_store_graph,
)
from component3.simulations.navigation_dashboard import adapter
from component3.simulations.navigation_dashboard.adapter import (
    DashboardRouteError,
    calculate_dashboard_route,
    calculate_route,
    load_dashboard_data,
    project_map_coordinate,
    validate_destinations,
)
from component3.simulations.navigation_dashboard.config import (
    DEFAULT_DESTINATION_IDS,
    STORE_GRAPH_PATH,
)
from component3.simulations.navigation_dashboard.session import DashboardSession


COMPONENT_ROOT = Path(__file__).resolve().parents[2]


def disconnected_graph() -> StoreGraph:
    """Build a graph whose checkout is unreachable from the entrance."""
    return StoreGraph.from_dict(
        {
            "nodes": [
                {"id": "ENT", "name": "Entrance", "type": "entrance", "x_m": 0, "y_m": 0},
                {"id": "B1", "name": "Aisle", "type": "aisle_access", "x_m": 1, "y_m": 0},
                {"id": "CHK", "name": "Checkout", "type": "checkout", "x_m": 10, "y_m": 0},
            ],
            "edges": [{"source": "ENT", "target": "B1", "distance_m": 1}],
        }
    )


class NavigationDashboardAdapterTests(unittest.TestCase):
    """Verify actual map metadata and existing route algorithm integration."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load immutable actual Component 3 map documents once."""
        cls.graph = load_store_graph(STORE_GRAPH_PATH)
        cls.map_data = load_dashboard_data()

    def test_graph_loading_uses_component_store_map(self) -> None:
        """Load all authoritative graph nodes and edges."""
        self.assertEqual(len(self.graph.nodes), 20)
        self.assertEqual(len(self.graph.edges), 29)
        self.assertEqual(self.map_data["entrance_node_id"], "ENT")
        self.assertEqual(self.map_data["checkout_node_id"], "CHK")

    def test_map_data_includes_sections_and_checkpoint_layout(self) -> None:
        """Expose real graph geometry, six aisle destinations, and eight tags."""
        self.assertEqual(self.map_data["dimensions_m"], {"width": 24.0, "height": 18.0})
        self.assertEqual(len(self.map_data["nodes"]), 20)
        self.assertEqual(len(self.map_data["edges"]), 29)
        self.assertEqual(len(self.map_data["sections"]), 6)
        self.assertEqual(len(self.map_data["destinations"]), 6)
        self.assertEqual(len(self.map_data["tags"]), 8)
        self.assertEqual(self.map_data["product_location_count"], 0)

    def test_coordinate_scaling_preserves_equal_axis_scale(self) -> None:
        """Use the smaller viewport scale and center the actual metric map."""
        result = project_map_coordinate(
            24.0,
            18.0,
            width_m=24.0,
            height_m=18.0,
            viewport_width_px=1200,
            viewport_height_px=600,
        )
        self.assertEqual(result.scale_px_per_m, 33.333333333333336)
        self.assertAlmostEqual(result.offset_x_px, 200.0)
        self.assertEqual(result.offset_y_px, 0.0)
        self.assertAlmostEqual(result.x_px - result.offset_x_px, 24 * result.scale_px_per_m)
        self.assertAlmostEqual(600 - result.y_px, 18 * result.scale_px_per_m)

    def test_coordinate_scaling_rejects_out_of_bounds_and_invalid_values(self) -> None:
        """Do not distort or silently draw invalid coordinates."""
        with self.assertRaises(ValueError):
            project_map_coordinate(
                25, 0, width_m=24, height_m=18,
                viewport_width_px=1200, viewport_height_px=900,
            )
        with self.assertRaises(ValueError):
            project_map_coordinate(
                float("nan"), 0, width_m=24, height_m=18,
                viewport_width_px=1200, viewport_height_px=900,
            )

    def test_destination_validation_deduplicates_and_rejects_unmapped_nodes(self) -> None:
        """Accept only mapped aisle nodes while retaining selection order."""
        selected = validate_destinations(["B3", "B1", "B3"], self.map_data)
        self.assertEqual(selected, ("B3", "B1"))
        with self.assertRaises(DashboardRouteError):
            validate_destinations(["M3"], self.map_data)
        with self.assertRaises(DashboardRouteError):
            validate_destinations(["missing"], self.map_data)

    def test_held_karp_and_dijkstra_are_reused(self) -> None:
        """Verify the adapter calls the established optimizer and shortest path."""
        with (
            patch.object(
                adapter, "held_karp_route", wraps=adapter.held_karp_route
            ) as held_karp,
            patch.object(
                adapter,
                "dijkstra_shortest_path",
                wraps=adapter.dijkstra_shortest_path,
            ) as dijkstra,
        ):
            plan = calculate_dashboard_route(
                self.map_data, DEFAULT_DESTINATION_IDS, self.graph
            )
        self.assertTrue(held_karp.called)
        self.assertGreaterEqual(dijkstra.call_count, 2)
        self.assertEqual(plan.selected_destination_ids, DEFAULT_DESTINATION_IDS)
        self.assertEqual(set(plan.optimized_visit_order), set(DEFAULT_DESTINATION_IDS))
        self.assertEqual(plan.route_node_ids[0], "ENT")
        self.assertEqual(plan.route_node_ids[-1], "CHK")
        self.assertGreater(plan.total_distance_m, 0.0)

    def test_empty_selection_routes_directly_to_checkout(self) -> None:
        """An empty list is a valid entrance-to-checkout route."""
        plan = calculate_dashboard_route(self.map_data, [], self.graph)
        self.assertEqual(plan.optimized_visit_order, ())
        self.assertEqual(plan.route_node_ids[0], "ENT")
        self.assertEqual(plan.route_node_ids[-1], "CHK")
        self.assertEqual(plan.total_distance_m, 8.69)

    def test_duplicate_destinations_are_counted_once(self) -> None:
        """Route unique mapped stops once even when a client repeats a choice."""
        plan = calculate_dashboard_route(
            self.map_data, ["B1", "B3", "B1"], self.graph
        )
        self.assertEqual(plan.selected_destination_ids, ("B1", "B3"))
        self.assertEqual(len(plan.optimized_visit_order), 2)

    def test_unreachable_destination_returns_explicit_error(self) -> None:
        """Report an unreachable checkout without inventing a fallback route."""
        graph = disconnected_graph()
        with self.assertRaisesRegex(DashboardRouteError, "Unable to calculate route"):
            calculate_route(
                graph,
                ["B1"],
                valid_destination_ids=["B1"],
                start_node_id="ENT",
                checkout_node_id="CHK",
            )

    def test_invalid_graph_nodes_are_reported(self) -> None:
        """Reject invalid route endpoints and destination IDs explicitly."""
        with self.assertRaises(DashboardRouteError):
            calculate_route(
                self.graph,
                ["not-a-node"],
                valid_destination_ids=["not-a-node"],
            )
        with self.assertRaises(DashboardRouteError):
            calculate_route(
                self.graph,
                [],
                valid_destination_ids=[],
                start_node_id="missing",
            )

    def test_session_calculation_and_reset(self) -> None:
        """Calculate a default route then reset to the deterministic defaults."""
        session = DashboardSession(self.map_data, self.graph)
        plan = session.calculate()
        self.assertEqual(plan.selected_destination_ids, DEFAULT_DESTINATION_IDS)
        self.assertIsNotNone(session.route_plan)
        session.reset()
        self.assertEqual(session.selected_destination_ids, DEFAULT_DESTINATION_IDS)
        self.assertIsNone(session.route_plan)

    def test_failed_session_calculation_preserves_previous_route(self) -> None:
        """A rejected selection must not overwrite a previously valid plan."""
        session = DashboardSession(self.map_data, self.graph)
        original = session.calculate()
        with self.assertRaises(DashboardRouteError):
            session.calculate(["unknown"])
        self.assertEqual(session.route_plan, original)
        self.assertEqual(session.selected_destination_ids, original.selected_destination_ids)


if __name__ == "__main__":
    unittest.main()
