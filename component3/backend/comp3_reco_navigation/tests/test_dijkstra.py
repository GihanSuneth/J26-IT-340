"""Automated tests for deterministic shortest-path routing."""

from __future__ import annotations

import unittest

from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    UnknownNodeError,
    UnreachablePathError,
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    GraphValidationError,
    StoreGraph,
    load_store_graph,
)


def small_graph(
    node_ids: tuple[str, ...],
    edges: tuple[tuple[str, str, float], ...],
) -> StoreGraph:
    """Build an independently specified graph fixture."""
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


class DijkstraStoreMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_store_graph()

    def test_entrance_to_checkout(self) -> None:
        route = dijkstra_shortest_path(self.graph, "ENT", "CHK")
        self.assertEqual(route.node_ids, ("ENT", "B4", "B5", "CHK"))
        self.assertAlmostEqual(route.total_distance_m, 8.69)

    def test_entrance_to_aisle_checkpoint(self) -> None:
        route = dijkstra_shortest_path(self.graph, "ENT", "B1")
        self.assertEqual(route.node_ids, ("ENT", "B4", "B3", "B2", "B1"))
        self.assertAlmostEqual(route.total_distance_m, 13.8)

    def test_between_aisle_checkpoints(self) -> None:
        route = dijkstra_shortest_path(self.graph, "B1", "B5")
        self.assertEqual(route.node_ids, ("B1", "B2", "B3", "B4", "B5"))
        self.assertAlmostEqual(route.total_distance_m, 14.4)

    def test_start_equals_destination(self) -> None:
        route = dijkstra_shortest_path(self.graph, "M3", "M3")
        self.assertEqual(route.node_ids, ("M3",))
        self.assertEqual(route.total_distance_m, 0.0)

    def test_invalid_start_node(self) -> None:
        with self.assertRaisesRegex(UnknownNodeError, "Unknown start node"):
            dijkstra_shortest_path(self.graph, "UNKNOWN", "B1")

    def test_invalid_destination_node(self) -> None:
        with self.assertRaisesRegex(UnknownNodeError, "Unknown destination node"):
            dijkstra_shortest_path(self.graph, "B1", "UNKNOWN")

    def test_disconnected_graph(self) -> None:
        graph = small_graph(("A", "B", "C"), (("A", "B", 1.0),))
        with self.assertRaisesRegex(UnreachablePathError, "No route exists"):
            dijkstra_shortest_path(graph, "A", "C")

    def test_equal_cost_paths_use_lexical_tie_break(self) -> None:
        graph = small_graph(
            ("S", "A", "B", "T"),
            (
                ("S", "B", 1.0),
                ("B", "T", 1.0),
                ("S", "A", 1.0),
                ("A", "T", 1.0),
            ),
        )
        route = dijkstra_shortest_path(graph, "S", "T")
        self.assertEqual(route.node_ids, ("S", "A", "T"))
        self.assertEqual(route.total_distance_m, 2.0)

    def test_weighted_distance_not_hop_count(self) -> None:
        graph = small_graph(
            ("S", "A", "T"),
            (("S", "T", 2.0), ("S", "A", 0.6), ("A", "T", 0.6)),
        )
        route = dijkstra_shortest_path(graph, "S", "T")
        self.assertEqual(route.node_ids, ("S", "A", "T"))
        self.assertAlmostEqual(route.total_distance_m, 1.2)

    def test_every_route_step_is_an_edge(self) -> None:
        route = dijkstra_shortest_path(self.graph, "ENT", "T6")
        accumulated = 0.0
        for source, target in zip(route.node_ids, route.node_ids[1:]):
            accumulated += self.graph.edge_weight(source, target)
        self.assertAlmostEqual(accumulated, route.total_distance_m)

    def test_graph_is_not_mutated(self) -> None:
        nodes_before = tuple(self.graph.nodes.items())
        edges_before = self.graph.edges
        neighbors_before = {
            node_id: self.graph.neighbors(node_id)
            for node_id in self.graph.node_ids
        }
        dijkstra_shortest_path(self.graph, "ENT", "T1")
        self.assertEqual(tuple(self.graph.nodes.items()), nodes_before)
        self.assertEqual(self.graph.edges, edges_before)
        self.assertEqual(
            {
                node_id: self.graph.neighbors(node_id)
                for node_id in self.graph.node_ids
            },
            neighbors_before,
        )

    def test_repeatability(self) -> None:
        results = {
            dijkstra_shortest_path(self.graph, "T1", "CHK")
            for _ in range(20)
        }
        self.assertEqual(len(results), 1)


class StoreGraphLoadingTests(unittest.TestCase):
    def test_actual_graph_counts_and_undirected_edges(self) -> None:
        graph = load_store_graph()
        self.assertEqual(len(graph.nodes), 20)
        self.assertEqual(len(graph.edges), 29)
        self.assertEqual(graph.edge_weight("B4", "ENT"), 3.0)

    def test_invalid_edge_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(GraphValidationError, "unknown nodes"):
            small_graph(("A",), (("A", "MISSING", 1.0),))

    def test_non_positive_edge_is_rejected(self) -> None:
        with self.assertRaisesRegex(GraphValidationError, "positive distance"):
            small_graph(("A", "B"), (("A", "B", 0.0),))


if __name__ == "__main__":
    unittest.main()
