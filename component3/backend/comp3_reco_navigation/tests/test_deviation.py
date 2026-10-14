"""Tests for geometric route-deviation detection and synthetic evaluation."""

from __future__ import annotations

import inspect
import math
from pathlib import Path
import unittest

from component3.backend.comp3_reco_navigation.navigation.deviation import (
    RouteDeviationMonitor,
    evaluate_route_deviation,
)
from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    PositionEstimate,
)
from component3.backend.comp3_reco_navigation.navigation.deviation_simulation import (
    DeviationSimulationConfig,
    _process_scenario,
    build_scenarios,
)
from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    held_karp_route,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    StoreGraph,
    load_store_graph,
)


COMPONENT_ROOT = Path(__file__).resolve().parents[3]


def coordinate_graph(
    coordinates: tuple[tuple[str, float, float], ...],
    edges: tuple[tuple[str, str], ...],
) -> StoreGraph:
    """Create a small graph whose node coordinates are controlled by a test."""
    return StoreGraph.from_dict(
        {
            "nodes": [
                {
                    "id": node_id,
                    "name": node_id,
                    "type": "test",
                    "x_m": x_m,
                    "y_m": y_m,
                }
                for node_id, x_m, y_m in coordinates
            ],
            "edges": [
                {"source": source, "target": target, "distance_m": 1.0}
                for source, target in edges
            ],
        }
    )


def estimate(x_m: float, y_m: float) -> PositionEstimate:
    """Construct a test position estimate with a nondecreasing timestamp."""
    return PositionEstimate(x_m, y_m, 0.0, 1.0)


class RouteDeviationTests(unittest.TestCase):
    """Verify projection math, validation, state confirmation, and replay."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the authoritative store graph once for route simulations."""
        cls.graph = load_store_graph(COMPONENT_ROOT / "data/store_map/store_graph.json")
        result = held_karp_route(cls.graph, "ENT", ["B1", "B3", "B5"], "CHK")
        cls.route = result.route_node_ids

    def test_horizontal_segment_distance(self) -> None:
        """Measure perpendicular distance to a horizontal route segment."""
        graph = coordinate_graph((("A", 0, 0), ("B", 10, 0)), (("A", "B"),))
        result = evaluate_route_deviation(graph, ("A", "B"), estimate(4, 3), 2.0)
        self.assertAlmostEqual(result.distance_m, 3.0)
        self.assertEqual(result.nearest_segment_index, 0)

    def test_vertical_segment_distance(self) -> None:
        """Measure perpendicular distance to a vertical route segment."""
        graph = coordinate_graph((("A", 0, 0), ("B", 0, 10)), (("A", "B"),))
        result = evaluate_route_deviation(graph, ("A", "B"), estimate(4, 3), 5.0)
        self.assertAlmostEqual(result.distance_m, 4.0)
        self.assertAlmostEqual(result.projection_y_m, 3.0)

    def test_diagonal_segment_distance(self) -> None:
        """Project onto a diagonal route using Euclidean coordinates."""
        graph = coordinate_graph((("A", 0, 0), ("B", 4, 4)), (("A", "B"),))
        result = evaluate_route_deviation(graph, ("A", "B"), estimate(0, 2), 1.0)
        self.assertAlmostEqual(result.distance_m, math.sqrt(2.0))
        self.assertAlmostEqual(result.projection_x_m, 1.0)
        self.assertAlmostEqual(result.projection_y_m, 1.0)

    def test_projection_before_segment_start_is_clamped(self) -> None:
        """Use the segment start rather than an unbounded projection."""
        graph = coordinate_graph((("A", 0, 0), ("B", 10, 0)), (("A", "B"),))
        result = evaluate_route_deviation(graph, ("A", "B"), estimate(-3, 4), 5.0)
        self.assertAlmostEqual(result.distance_m, 5.0)
        self.assertEqual((result.projection_x_m, result.projection_y_m), (0.0, 0.0))

    def test_projection_after_segment_end_is_clamped(self) -> None:
        """Use the segment end rather than an unbounded projection."""
        graph = coordinate_graph((("A", 0, 0), ("B", 10, 0)), (("A", "B"),))
        result = evaluate_route_deviation(graph, ("A", "B"), estimate(13, 4), 5.0)
        self.assertAlmostEqual(result.distance_m, 5.0)
        self.assertEqual((result.projection_x_m, result.projection_y_m), (10.0, 0.0))

    def test_zero_length_coordinate_segment(self) -> None:
        """Handle adjacent valid nodes with identical stored coordinates."""
        graph = coordinate_graph((("A", 1, 2), ("B", 1, 2)), (("A", "B"),))
        result = evaluate_route_deviation(graph, ("A", "B"), estimate(4, 6), 5.0)
        self.assertAlmostEqual(result.distance_m, 5.0)
        self.assertEqual((result.projection_x_m, result.projection_y_m), (1.0, 2.0))

    def test_route_with_multiple_segments(self) -> None:
        """Choose the nearest of all consecutive route segments."""
        graph = coordinate_graph(
            (("A", 0, 0), ("B", 10, 0), ("C", 10, 10)),
            (("A", "B"), ("B", "C")),
        )
        result = evaluate_route_deviation(graph, ("A", "B", "C"), estimate(11, 5), 1.0)
        self.assertAlmostEqual(result.distance_m, 1.0)
        self.assertEqual(result.nearest_segment_index, 1)

    def test_single_node_route_endpoint(self) -> None:
        """Treat a one-node route as a point endpoint."""
        graph = coordinate_graph((("A", 2, 3),), ())
        result = evaluate_route_deviation(graph, ("A",), estimate(5, 7), 5.0)
        self.assertIsNone(result.nearest_segment_index)
        self.assertAlmostEqual(result.distance_m, 5.0)

    def test_invalid_graph_nodes_and_disconnected_route(self) -> None:
        """Reject unknown nodes and non-edge consecutive route pairs."""
        graph = coordinate_graph(
            (("A", 0, 0), ("B", 1, 0), ("C", 2, 0)), (("A", "B"),)
        )
        for route in ((), ("A", "missing"), ("A", "C")):
            with self.subTest(route=route), self.assertRaises(ValueError):
                evaluate_route_deviation(graph, route, estimate(0, 0), 1.0)

    def test_invalid_graph_coordinates_are_rejected(self) -> None:
        """Do not accept nonfinite coordinates from a malformed graph."""
        graph = coordinate_graph((("A", math.nan, 0.0),), ())
        with self.assertRaises(ValueError):
            evaluate_route_deviation(graph, ("A",), estimate(0.0, 0.0), 1.0)

    def test_invalid_coordinates_and_threshold(self) -> None:
        """Reject nonfinite, boolean, and negative position/threshold values."""
        graph = coordinate_graph((("A", 0, 0),), ())
        with self.assertRaises(ValueError):
            evaluate_route_deviation(
                graph, ("A",), PositionEstimate(True, 0.0, 0.0, 1.0), 1.0
            )
        with self.assertRaises(ValueError):
            PositionEstimate(math.nan, 0.0, 0.0, 1.0)
        for threshold in (-0.1, math.nan, math.inf, True):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                evaluate_route_deviation(graph, ("A",), estimate(0, 0), threshold)

    def test_threshold_boundary_is_on_route(self) -> None:
        """The detector only classifies distances strictly above threshold."""
        graph = coordinate_graph((("A", 0, 0),), ())
        boundary = evaluate_route_deviation(graph, ("A",), estimate(1, 0), 1.0)
        above = evaluate_route_deviation(
            graph, ("A",), estimate(1.0001, 0), 1.0
        )
        self.assertFalse(boundary.is_deviating)
        self.assertTrue(above.is_deviating)

    def test_progress_scaled_threshold(self) -> None:
        """Apply the configured epsilon(d) threshold along the planned route."""
        monitor = RouteDeviationMonitor(self.graph, self.route)
        start = self.graph.node(self.route[0])
        state = monitor.update(estimate(start.x_m, start.y_m + 0.31))
        self.assertAlmostEqual(
            state.measurement.threshold_m,
            0.3 + 0.02 * state.measurement.route_progress_m,
        )

    def test_consecutive_confirmation_resets_on_a_good_sample(self) -> None:
        """Require uninterrupted above-threshold observations before entry."""
        graph = coordinate_graph((("A", 0, 0),), ())
        monitor = RouteDeviationMonitor(
            graph, ("A",), threshold_m=1.0, enter_confirmations=2
        )
        self.assertFalse(monitor.update(estimate(1.1, 0)).is_deviated)
        self.assertFalse(monitor.update(estimate(0.0, 0)).is_deviated)
        self.assertFalse(monitor.update(estimate(1.1, 0)).is_deviated)
        entered = monitor.update(estimate(1.1, 0))
        self.assertTrue(entered.entered_deviation)
        self.assertTrue(entered.is_deviated)

    def test_hysteresis_and_recovery_confirmation(self) -> None:
        """Hold state between enter and exit thresholds and confirm recovery."""
        graph = coordinate_graph((("A", 0, 0),), ())
        monitor = RouteDeviationMonitor(
            graph,
            ("A",),
            threshold_m=1.0,
            hysteresis_m=0.4,
            enter_confirmations=1,
            recovery_confirmations=2,
        )
        self.assertTrue(monitor.update(estimate(1.1, 0)).is_deviated)
        between = monitor.update(estimate(0.8, 0))
        self.assertTrue(between.is_deviated)
        self.assertAlmostEqual(between.exit_threshold_m, 0.6)
        self.assertTrue(monitor.update(estimate(0.5, 0)).is_deviated)
        recovered = monitor.update(estimate(0.5, 0))
        self.assertTrue(recovered.recovered)
        self.assertFalse(recovered.is_deviated)

    def test_confirmed_deviation_can_be_carried_to_a_replanned_route(self) -> None:
        """Preserve an active deviation episode across route replacement."""
        graph = coordinate_graph((("A", 0, 0),), ())
        monitor = RouteDeviationMonitor(
            graph,
            ("A",),
            threshold_m=1.0,
            hysteresis_m=0.2,
            recovery_confirmations=2,
            initially_deviated=True,
        )
        first = monitor.update(estimate(0.5, 0))
        self.assertTrue(first.is_deviated)
        self.assertFalse(first.recovered)
        second = monitor.update(estimate(0.5, 0))
        self.assertFalse(second.is_deviated)
        self.assertTrue(second.recovered)

    def test_state_reset(self) -> None:
        """Clear active deviation state and both consecutive counters."""
        graph = coordinate_graph((("A", 0, 0),), ())
        monitor = RouteDeviationMonitor(
            graph, ("A",), threshold_m=1.0, enter_confirmations=1
        )
        monitor.update(estimate(2.0, 0))
        self.assertTrue(monitor.is_deviated)
        monitor.reset()
        self.assertFalse(monitor.is_deviated)
        self.assertFalse(monitor.update(estimate(0.0, 0)).is_deviated)

    def test_invalid_position_does_not_advance_confirmation(self) -> None:
        """Reject an invalid sample without mutating the pending count."""
        graph = coordinate_graph((("A", 0, 0),), ())
        monitor = RouteDeviationMonitor(
            graph, ("A",), threshold_m=1.0, enter_confirmations=2
        )
        monitor.update(estimate(2.0, 0.0))
        with self.assertRaises(ValueError):
            monitor.update(PositionEstimate(True, 0.0, 0.0, 2.0))
        self.assertTrue(monitor.update(estimate(2.0, 0.0)).entered_deviation)

    def test_sustained_deviation_and_recovery(self) -> None:
        """Latch sustained distance and recover after consecutive close samples."""
        graph = coordinate_graph((("A", 0, 0),), ())
        monitor = RouteDeviationMonitor(
            graph,
            ("A",),
            threshold_m=1.0,
            hysteresis_m=0.2,
            enter_confirmations=3,
            recovery_confirmations=2,
        )
        states = [monitor.update(estimate(1.5, 0)) for _ in range(3)]
        self.assertTrue(states[-1].entered_deviation)
        self.assertTrue(states[-1].is_deviated)
        self.assertTrue(monitor.update(estimate(0.5, 0)).is_deviated)
        self.assertTrue(monitor.update(estimate(0.5, 0)).recovered)

    def test_small_noisy_positions_do_not_raise_alarm(self) -> None:
        """Keep deterministic small perturbations within the route threshold."""
        config = DeviationSimulationConfig(position_noise_std_m=0.02)
        scenarios = dict(build_scenarios(self.graph, self.route, config))
        observations = _process_scenario(
            self.graph, self.route, scenarios["small_position_noise"], config
        )
        self.assertFalse(any(item.entered_deviation for item in observations))
        self.assertFalse(any(item.detected_deviation for item in observations))

    def test_scenario_generation_is_reproducible_and_labeled(self) -> None:
        """Reproduce labeled truth and sensor estimates using the fixed seed."""
        config = DeviationSimulationConfig()
        first = build_scenarios(self.graph, self.route, config)
        second = build_scenarios(self.graph, self.route, config)
        for first_scenario, second_scenario in zip(first, second):
            self.assertEqual(first_scenario[0], second_scenario[0])
            self.assertEqual(len(first_scenario[1]), len(second_scenario[1]))
            for first_sample, second_sample in zip(
                first_scenario[1], second_scenario[1]
            ):
                self.assertEqual(
                    first_sample.ground_truth_off_route,
                    second_sample.ground_truth_off_route,
                )
                self.assertEqual(
                    (
                        first_sample.scenario,
                        first_sample.sample_index,
                        first_sample.timestamp_s,
                        first_sample.ground_truth_x_m,
                        first_sample.ground_truth_y_m,
                    ),
                    (
                        second_sample.scenario,
                        second_sample.sample_index,
                        second_sample.timestamp_s,
                        second_sample.ground_truth_x_m,
                        second_sample.ground_truth_y_m,
                    ),
                )
                for first_value, second_value in (
                    (first_sample.estimate_x_m, second_sample.estimate_x_m),
                    (first_sample.estimate_y_m, second_sample.estimate_y_m),
                ):
                    if math.isnan(first_value):
                        self.assertTrue(math.isnan(second_value))
                    else:
                        self.assertEqual(first_value, second_value)
        self.assertEqual(len(first), 8)
        self.assertIn(
            "brief_single_sample_deviation",
            dict(first),
        )

    def test_sustained_scenario_confirms_and_truth_is_not_detector_input(self) -> None:
        """Confirm synthetic sustained offsets while estimate API stays sensor-only."""
        config = DeviationSimulationConfig()
        scenarios = dict(build_scenarios(self.graph, self.route, config))
        observations = _process_scenario(
            self.graph,
            self.route,
            scenarios["sustained_off_route_movement"],
            config,
        )
        self.assertTrue(any(item.entered_deviation for item in observations))
        self.assertNotIn(
            "ground_truth_off_route",
            inspect.signature(evaluate_route_deviation).parameters,
        )

    def test_invalid_scenario_positions_are_excluded_without_alarm(self) -> None:
        """Reject invalid estimate coordinates and exclude them from metrics."""
        config = DeviationSimulationConfig()
        scenarios = dict(build_scenarios(self.graph, self.route, config))
        observations = _process_scenario(
            self.graph, self.route, scenarios["invalid_position_data"], config
        )
        invalid = [item for item in observations if not item.valid_position]
        self.assertEqual(len(invalid), 2)
        self.assertTrue(all(not item.classification_included for item in invalid))
        self.assertTrue(all(item.detected_deviation is None for item in invalid))


if __name__ == "__main__":
    unittest.main()
