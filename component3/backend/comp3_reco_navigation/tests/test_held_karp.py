"""Tests for exact deterministic Held-Karp multi-stop routing."""

from __future__ import annotations

import argparse
from datetime import datetime
import io
import itertools
from pathlib import Path
import sys
import unittest

from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    UnknownNodeError,
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    StopLimitExceededError,
    UnreachableLocationError,
    held_karp_route,
    route_for_stop_order,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    StoreGraph,
    load_store_graph,
)


def small_graph(
    node_ids: tuple[str, ...],
    edges: tuple[tuple[str, str, float], ...],
) -> StoreGraph:
    return StoreGraph.from_dict(
        {
            "nodes": [
                {
                    "id": node_id,
                    "name": f"Node {node_id}",
                    "type": "test",
                    "x_m": index,
                    "y_m": 0,
                }
                for index, node_id in enumerate(node_ids)
            ],
            "edges": [
                {"source": source, "target": target, "distance_m": weight}
                for source, target, weight in edges
            ],
        }
    )


def exhaustive_reference(
    graph: StoreGraph,
    start: str,
    stops: tuple[str, ...],
    checkout: str,
) -> tuple[float, tuple[str, ...]]:
    """Independent factorial reference used only by controlled tests."""
    candidates: list[tuple[float, tuple[str, ...]]] = []
    for order in itertools.permutations(stops):
        locations = (start, *order, checkout)
        distance = sum(
            dijkstra_shortest_path(graph, source, destination).total_distance_m
            for source, destination in zip(locations, locations[1:])
        )
        candidates.append((distance, order))
    return min(candidates)


class HeldKarpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_store_graph()

    def test_empty_shopping_list(self) -> None:
        result = held_karp_route(self.graph, "ENT", [], "CHK")
        self.assertEqual(result.optimized_stop_ids, ())
        self.assertEqual(result.route_node_ids, ("ENT", "B4", "B5", "CHK"))
        self.assertAlmostEqual(result.total_distance_m, 8.69)

    def test_single_shopping_stop(self) -> None:
        result = held_karp_route(self.graph, "ENT", ["B1"], "CHK")
        self.assertEqual(result.optimized_stop_ids, ("B1",))
        self.assertIn("B1", result.route_node_ids)

    def test_multiple_stops_matches_exhaustive_reference(self) -> None:
        stops = ("B1", "B3", "B5")
        expected_distance, expected_order = exhaustive_reference(
            self.graph, "ENT", stops, "CHK"
        )
        result = held_karp_route(self.graph, "ENT", stops, "CHK")
        self.assertEqual(result.optimized_stop_ids, expected_order)
        self.assertAlmostEqual(result.total_distance_m, expected_distance)

    def test_duplicate_stops_are_removed_stably(self) -> None:
        result = held_karp_route(
            self.graph, "ENT", ["B3", "B1", "B3", "B1"], "CHK"
        )
        self.assertEqual(result.unique_required_stop_ids, ("B3", "B1"))
        self.assertEqual(set(result.optimized_stop_ids), {"B1", "B3"})

    def test_start_included_as_stop(self) -> None:
        result = held_karp_route(self.graph, "ENT", ["ENT", "B1"], "CHK")
        self.assertEqual(result.unique_required_stop_ids, ("B1",))
        self.assertEqual(result.route_node_ids[0], "ENT")

    def test_checkout_included_as_stop(self) -> None:
        result = held_karp_route(self.graph, "ENT", ["B1", "CHK"], "CHK")
        self.assertEqual(result.unique_required_stop_ids, ("B1",))
        self.assertEqual(result.route_node_ids[-1], "CHK")

    def test_invalid_start_node(self) -> None:
        with self.assertRaisesRegex(UnknownNodeError, "Unknown start node"):
            held_karp_route(self.graph, "UNKNOWN", ["B1"], "CHK")

    def test_invalid_shopping_stop(self) -> None:
        with self.assertRaisesRegex(UnknownNodeError, "Unknown shopping-stop node"):
            held_karp_route(self.graph, "ENT", ["UNKNOWN"], "CHK")

    def test_invalid_checkout_node(self) -> None:
        with self.assertRaisesRegex(UnknownNodeError, "Unknown checkout node"):
            held_karp_route(self.graph, "ENT", ["B1"], "UNKNOWN")

    def test_unreachable_shopping_stop(self) -> None:
        graph = small_graph(("S", "A", "U"), (("S", "A", 1.0),))
        with self.assertRaisesRegex(UnreachableLocationError, "unreachable"):
            held_karp_route(graph, "S", ["U"], "A")

    def test_unreachable_checkout(self) -> None:
        graph = small_graph(("S", "A", "C"), (("S", "A", 1.0),))
        with self.assertRaisesRegex(UnreachableLocationError, "unreachable"):
            held_karp_route(graph, "S", ["A"], "C")

    def test_equal_cost_orders_use_lexical_tie_break(self) -> None:
        graph = small_graph(
            ("S", "A", "B", "C"),
            (
                ("S", "A", 1.0),
                ("S", "B", 1.0),
                ("A", "B", 1.0),
                ("A", "C", 1.0),
                ("B", "C", 1.0),
            ),
        )
        result = held_karp_route(graph, "S", ["B", "A"], "C")
        self.assertEqual(result.optimized_stop_ids, ("A", "B"))
        self.assertEqual(result.total_distance_m, 3.0)

    def test_route_distance_equals_expanded_edge_sum(self) -> None:
        result = held_karp_route(self.graph, "ENT", ["B1", "B3", "B5"], "CHK")
        edge_sum = sum(
            self.graph.edge_weight(source, target)
            for source, target in zip(result.route_node_ids, result.route_node_ids[1:])
        )
        self.assertAlmostEqual(result.total_distance_m, edge_sum)

    def test_every_consecutive_route_node_is_connected(self) -> None:
        result = held_karp_route(self.graph, "ENT", ["B6", "B2", "B4"], "CHK")
        for source, target in zip(result.route_node_ids, result.route_node_ids[1:]):
            self.assertGreater(self.graph.edge_weight(source, target), 0.0)

    def test_input_list_remains_unchanged(self) -> None:
        requested = ["B5", "B1", "B3", "B1"]
        before = requested.copy()
        result = held_karp_route(self.graph, "ENT", requested, "CHK")
        self.assertEqual(requested, before)
        self.assertEqual(result.original_requested_stop_ids, tuple(before))

    def test_deterministic_repeated_execution(self) -> None:
        results = {
            held_karp_route(self.graph, "ENT", ["B5", "B1", "B3"], "CHK")
            for _ in range(20)
        }
        self.assertEqual(len(results), 1)

    def test_stop_count_limit_enforcement(self) -> None:
        with self.assertRaisesRegex(StopLimitExceededError, "at most 2"):
            held_karp_route(
                self.graph,
                "ENT",
                ["B1", "B2", "B3"],
                "CHK",
                max_unique_stops=2,
            )

    def test_optimization_is_no_worse_than_original_order(self) -> None:
        requested = ["B5", "B1", "B3", "B2"]
        baseline = route_for_stop_order(self.graph, "ENT", requested, "CHK")
        optimized = held_karp_route(self.graph, "ENT", requested, "CHK")
        self.assertLessEqual(optimized.total_distance_m, baseline.total_distance_m)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HeldKarpTests)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    body = stream.getvalue()
    report = (
        "Component 3 Held-Karp Test Execution\n"
        "=====================================\n"
        f"Executed: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"Python: {sys.version.split()[0]}\n"
        "Command: python3 -B -m "
        "component3.backend.comp3_reco_navigation.tests.test_held_karp "
        "--output component3/evaluation/test_results/held_karp_tests.txt\n"
        "Framework: Python standard-library unittest\n\n"
        f"{body}\n"
        f"Tests executed: {result.testsRun}\n"
        f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}\n"
        f"Failed: {len(result.failures)}\n"
        f"Errors: {len(result.errors)}\n"
        f"Overall result: {'PASS' if result.wasSuccessful() else 'FAIL'}\n"
    )
    print(report, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
