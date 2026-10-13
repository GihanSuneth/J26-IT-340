"""Tests for graph localization, shopping sessions, and atomic rerouting."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import unittest

from component3.backend.comp3_reco_navigation.navigation.deviation import (
    DeviationState,
    RouteDeviationMonitor,
)
from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    PositionEstimate,
)
from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    held_karp_route,
)
from component3.backend.comp3_reco_navigation.navigation.route_manager import (
    RouteManager,
    localize_position_to_graph,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    StoreGraph,
    load_store_graph,
)


COMPONENT_ROOT = Path(__file__).resolve().parents[3]


def estimate(x_m: float, y_m: float, timestamp_s: float = 1.0) -> PositionEstimate:
    """Build a valid east/north metric position estimate."""
    return PositionEstimate(x_m, y_m, 0.0, timestamp_s)


def confirmed_state(manager: RouteManager, position: PositionEstimate) -> DeviationState:
    """Generate the actual three-sample detector entry event for one estimate."""
    monitor = RouteDeviationMonitor(
        manager.graph, manager.current_route, enter_confirmations=1
    )
    state = monitor.update(position)
    if not state.entered_deviation:
        state = monitor.update(position)
    return state


def disconnected_graph() -> StoreGraph:
    """Build two valid edge components to exercise a safe unreachable reroute."""
    return StoreGraph.from_dict(
        {
            "nodes": [
                {"id": "A", "name": "A", "type": "test", "x_m": 0, "y_m": 0},
                {"id": "B", "name": "B", "type": "test", "x_m": 1, "y_m": 0},
                {"id": "C", "name": "C", "type": "test", "x_m": 2, "y_m": 0},
                {"id": "D", "name": "D", "type": "test", "x_m": 10, "y_m": 0},
                {"id": "E", "name": "E", "type": "test", "x_m": 11, "y_m": 0},
            ],
            "edges": [
                {"source": "A", "target": "B", "distance_m": 1.0},
                {"source": "B", "target": "C", "distance_m": 1.0},
                {"source": "D", "target": "E", "distance_m": 1.0},
            ],
        }
    )


class RouteManagerTests(unittest.TestCase):
    """Verify route state transitions and integrations with existing algorithms."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the repository's authoritative store graph."""
        cls.graph = load_store_graph(COMPONENT_ROOT / "data/store_map/store_graph.json")

    def manager(
        self,
        stops: tuple[str, ...] = ("B1", "B3", "B5"),
        *,
        start: str = "ENT",
        checkout: str = "CHK",
    ) -> RouteManager:
        """Create a fresh route manager for a test session."""
        return RouteManager(self.graph, start, stops, checkout)

    def test_session_initialization_uses_held_karp_route(self) -> None:
        """Initialize route, destination lists, checkout, and route length."""
        manager = self.manager()
        expected = held_karp_route(self.graph, "ENT", ["B1", "B3", "B5"], "CHK")
        self.assertEqual(manager.current_route, expected.route_node_ids)
        self.assertEqual(manager.original_shopping_destinations, ("B1", "B3", "B5"))
        self.assertEqual(manager.remaining_destinations, ("B1", "B3", "B5"))
        self.assertEqual(manager.visited_destinations, [])
        self.assertEqual(manager.checkout_node_id, "CHK")
        self.assertAlmostEqual(manager.current_route_distance_m, expected.total_distance_m)

    def test_graph_localization_projects_and_chooses_nearest_endpoint(self) -> None:
        """Project onto a known store edge and select the closer endpoint."""
        result = localize_position_to_graph(self.graph, estimate(13.8, 1.0), 0.0)
        self.assertTrue(result.success)
        self.assertEqual((result.edge_start_node_id, result.edge_end_node_id), ("B4", "ENT"))
        self.assertEqual(result.start_node_id, "ENT")
        self.assertAlmostEqual(result.snap_distance_m, 0.0)

    def test_localization_threshold_boundary_and_distant_rejection(self) -> None:
        """Accept a snap exactly at maximum distance and reject a larger one."""
        on_edge = estimate(13.8, 1.5)
        near_edge = estimate(13.81, 1.5)
        accepted = localize_position_to_graph(self.graph, near_edge, 0.01)
        rejected = localize_position_to_graph(self.graph, near_edge, 0.009)
        boundary = localize_position_to_graph(self.graph, on_edge, 0.0)
        self.assertTrue(accepted.success)
        self.assertFalse(rejected.success)
        self.assertEqual(rejected.failure_reason, "position_exceeds_max_snapping_distance")
        self.assertTrue(boundary.success)

    def test_invalid_position_and_maximum_distance(self) -> None:
        """Return safe localization failure for malformed estimates."""
        result = localize_position_to_graph(self.graph, object(), 1.0)  # type: ignore[arg-type]
        self.assertFalse(result.success)
        self.assertEqual(result.failure_reason, "invalid_position")
        with self.assertRaises(ValueError):
            localize_position_to_graph(self.graph, estimate(0, 0), math.inf)
        with self.assertRaises(ValueError):
            RouteManager(
                self.graph,
                "ENT",
                (),
                "CHK",
                max_snapping_distance_m=math.nan,
            )

    def test_explicit_visit_confirmation_only(self) -> None:
        """Passing a shopping node in the route does not mark it visited."""
        manager = self.manager()
        self.assertEqual(manager.visited_destinations, [])
        confirmation = manager.confirm_destination_visit("B1", 3.0)
        self.assertTrue(confirmation.confirmed)
        self.assertEqual(manager.visited_destinations, ["B1"])
        self.assertEqual(manager.remaining_destinations, ("B3", "B5"))
        self.assertEqual(manager.current_route[0], "B1")

    def test_duplicate_destinations_are_stably_deduplicated(self) -> None:
        """Keep original requests but route each required destination once."""
        manager = self.manager(("B3", "B1", "B3", "B1"))
        self.assertEqual(manager.original_shopping_destinations, ("B3", "B1", "B3", "B1"))
        self.assertEqual(manager.remaining_destinations, ("B3", "B1"))
        expected = held_karp_route(self.graph, "ENT", ["B3", "B1"], "CHK")
        self.assertEqual(expected.unique_required_stop_ids, ("B3", "B1"))
        self.assertEqual(manager.current_route, expected.route_node_ids)

    def test_visit_recalculation_with_no_remaining_stops(self) -> None:
        """Keep checkout as the route after the final explicit visit."""
        manager = self.manager(("B1",))
        result = manager.confirm_destination_visit("B1", 2.0)
        self.assertTrue(result.confirmed)
        self.assertEqual(manager.remaining_destinations, ())
        self.assertEqual(manager.current_route[-1], "CHK")

    def test_dijkstra_and_held_karp_are_used_for_rerouting(self) -> None:
        """Reroute from the localized node while retaining every pending stop."""
        manager = self.manager()
        position = estimate(14.3, 1.5, 5.0)
        state = confirmed_state(manager, position)
        result = manager.process_position(position, state)
        self.assertIsNotNone(result)
        self.assertTrue(result.successful)
        self.assertEqual(result.localization.start_node_id, "B4")
        self.assertEqual(result.remaining_destinations, ("B1", "B3", "B5"))
        expected = held_karp_route(self.graph, "B4", ["B1", "B3", "B5"], "CHK")
        self.assertEqual(result.new_route, expected.route_node_ids)
        self.assertEqual(result.new_route[-1], "CHK")
        self.assertEqual(
            dijkstra_shortest_path(self.graph, "ENT", "CHK").node_ids,
            ("ENT", "B4", "B5", "CHK"),
        )

    def test_successful_reroute_is_atomic_and_tracks_history(self) -> None:
        """Record distances and timestamps only after route calculation succeeds."""
        manager = self.manager()
        old_route = manager.current_route
        old_distance = manager.current_route_distance_m
        position = estimate(14.3, 1.5, 10.0)
        state = confirmed_state(manager, position)
        result = manager.process_position(position, state)
        self.assertIsNotNone(result)
        self.assertTrue(result.successful)
        self.assertEqual(result.previous_route, old_route)
        self.assertEqual(result.previous_route_distance_m, old_distance)
        self.assertEqual(result.trigger_timestamp_s, 10.0)
        self.assertEqual(result.reroute_timestamp_s, 10.0)
        self.assertEqual(manager.current_route, result.new_route)
        self.assertEqual(manager.rerouting_history, [result])

    def test_unreachable_destination_preserves_active_session(self) -> None:
        """Keep route and stops unchanged when localized component cannot reach stops."""
        graph = disconnected_graph()
        manager = RouteManager(graph, "A", ("B",), "C")
        old_route = manager.current_route
        old_stops = manager.remaining_destinations
        position = estimate(10.2, 0.0, 4.0)
        state = RouteDeviationMonitor(
            graph, old_route, threshold_m=0.1, enter_confirmations=1
        ).update(position)
        result = manager.process_position(position, state)
        self.assertIsNotNone(result)
        self.assertFalse(result.successful)
        self.assertIn("route_computation_failed", result.failure_reason)
        self.assertEqual(manager.current_route, old_route)
        self.assertEqual(manager.remaining_destinations, old_stops)

    def test_failed_localization_is_atomic(self) -> None:
        """Keep previous route and shopping list after too-distant estimate."""
        manager = RouteManager(
            self.graph, "ENT", ("B1", "B3"), "CHK", max_snapping_distance_m=0.2
        )
        old_route = manager.current_route
        old_stops = manager.remaining_destinations
        position = estimate(100.0, 100.0, 7.0)
        state = RouteDeviationMonitor(
            self.graph, old_route, threshold_m=0.1, enter_confirmations=1
        ).update(position)
        result = manager.process_position(position, state)
        self.assertFalse(result.successful)
        self.assertEqual(
            result.failure_reason, "position_exceeds_max_snapping_distance"
        )
        self.assertEqual(manager.current_route, old_route)
        self.assertEqual(manager.remaining_destinations, old_stops)

    def test_no_repeated_rerouting_while_deviation_persists(self) -> None:
        """Suppress repeated attempts until detector exits and re-enters."""
        manager = self.manager()
        off_route = estimate(14.3, 1.5, 1.0)
        monitor = RouteDeviationMonitor(
            manager.graph, manager.current_route, enter_confirmations=1
        )
        entered = monitor.update(off_route)
        first = manager.process_position(off_route, entered)
        self.assertIsNotNone(first)
        held = monitor.update(off_route)
        second = manager.process_position(
            estimate(14.3, 1.5, 2.0), held
        )
        self.assertIsNone(second)
        self.assertEqual(len(manager.rerouting_history), 1)

    def test_rerouting_requires_enter_transition(self) -> None:
        """Do not recalculate from a latched state without a new entry event."""
        manager = self.manager()
        position = estimate(14.3, 1.5, 1.0)
        detector = RouteDeviationMonitor(
            manager.graph, manager.current_route, enter_confirmations=1
        )
        entered = detector.update(position)
        not_entry = replace(entered, entered_deviation=False)
        self.assertIsNone(manager.process_position(position, not_entry))
        actual_entry = replace(entered, entered_deviation=True)
        self.assertIsNotNone(manager.process_position(position, actual_entry))

    def test_detector_recovery_rearms_rerouting(self) -> None:
        """Allow another reroute only after the deviation state has recovered."""
        manager = self.manager()
        deviated_position = estimate(14.3, 1.5, 1.0)
        detector = RouteDeviationMonitor(
            manager.graph,
            manager.current_route,
            enter_confirmations=1,
            recovery_confirmations=1,
        )
        entered = detector.update(deviated_position)
        self.assertIsNotNone(manager.process_position(deviated_position, entered))
        node = self.graph.node(manager.current_route[0])
        recovered_position = estimate(node.x_m, node.y_m, 2.0)
        recovered = detector.update(recovered_position)
        self.assertFalse(recovered.is_deviated)
        self.assertIsNone(manager.process_position(recovered_position, recovered))
        reentry_position = estimate(14.3, 1.5, 3.0)
        reentered = detector.update(reentry_position)
        self.assertTrue(reentered.entered_deviation)
        self.assertIsNotNone(
            manager.process_position(reentry_position, reentered)
        )
        self.assertEqual(len(manager.rerouting_history), 2)

    def test_already_at_checkout_and_checkout_preservation(self) -> None:
        """Return a singleton checkout route when no shopping stops remain."""
        manager = self.manager(())
        position = estimate(18.0, 1.0, 3.0)
        result = manager.recalculate_after_deviation(position)
        self.assertTrue(result.successful)
        self.assertEqual(result.new_route, ("CHK",))
        self.assertEqual(result.new_route_distance_m, 0.0)

    def test_already_at_checkout_with_stops_fails_atomically(self) -> None:
        """Do not claim shopping stops are complete at checkout."""
        manager = self.manager(("B1",))
        old_route = manager.current_route
        position = estimate(18.0, 1.0, 3.0)
        result = manager.recalculate_after_deviation(position)
        self.assertFalse(result.successful)
        self.assertEqual(
            result.failure_reason,
            "already_at_checkout_with_remaining_destinations",
        )
        self.assertEqual(manager.current_route, old_route)
        self.assertEqual(manager.remaining_destinations, ("B1",))

    def test_invalid_localization_failure_has_structured_record(self) -> None:
        """Store a malformed estimate failure without touching session state."""
        manager = self.manager()
        old_route = manager.current_route
        result = manager.recalculate_after_deviation(object())  # type: ignore[arg-type]
        self.assertFalse(result.successful)
        self.assertEqual(result.failure_reason, "invalid_position")
        self.assertEqual(manager.current_route, old_route)
        self.assertEqual(manager.rerouting_history[-1], result)

    def test_boolean_position_does_not_update_estimate_or_route(self) -> None:
        """Reject bool coordinates even though bool is a Python numeric subtype."""
        manager = self.manager()
        old_route = manager.current_route
        invalid = PositionEstimate(True, 0.0, 0.0, 5.0)  # type: ignore[arg-type]
        valid_deviation = estimate(14.3, 1.5, 5.0)
        state = confirmed_state(manager, valid_deviation)
        result = manager.process_position(invalid, state)
        self.assertIsNotNone(result)
        self.assertFalse(result.successful)
        self.assertEqual(result.failure_reason, "invalid_position")
        self.assertIsNone(manager.current_position_estimate)
        self.assertEqual(manager.current_route, old_route)

    def test_deterministic_rerouting(self) -> None:
        """Repeat equivalent reroutes and compare graph route and distance."""
        results = []
        for _ in range(2):
            manager = self.manager(("B5", "B1", "B3", "B1"))
            result = manager.recalculate_after_deviation(
                estimate(14.3, 1.5, 5.0)
            )
            results.append((result.new_route, result.new_route_distance_m))
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
