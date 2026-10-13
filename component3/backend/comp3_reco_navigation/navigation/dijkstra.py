"""Deterministic Dijkstra shortest-path routing over the store graph."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

from .store_graph import StoreGraph


class UnknownNodeError(ValueError):
    """Raised when a route endpoint does not exist in the graph."""


class UnreachablePathError(ValueError):
    """Raised when no graph path connects the requested endpoints."""


@dataclass(frozen=True, slots=True)
class ShortestPath:
    """An ordered route and its accumulated graph-edge distance."""

    node_ids: tuple[str, ...]
    total_distance_m: float


def dijkstra_shortest_path(
    graph: StoreGraph,
    start_node_id: str,
    destination_node_id: str,
) -> ShortestPath:
    """Return the minimum-distance graph route between two nodes.

    Edge distances from the graph are accumulated directly. For equal-distance
    alternatives, the lexicographically smallest complete node sequence wins,
    making results repeatable regardless of input edge order.

    Complexity is ``O((V + E) log V)`` for ordinary sparse graphs, with a small
    additional tuple-comparison cost for deterministic tie breaking.
    """
    if start_node_id not in graph:
        raise UnknownNodeError(f"Unknown start node: {start_node_id!r}")
    if destination_node_id not in graph:
        raise UnknownNodeError(
            f"Unknown destination node: {destination_node_id!r}"
        )
    if start_node_id == destination_node_id:
        return ShortestPath((start_node_id,), 0.0)

    start_path = (start_node_id,)
    best: dict[str, tuple[float, tuple[str, ...]]] = {
        start_node_id: (0.0, start_path)
    }
    queue: list[tuple[float, tuple[str, ...], str]] = [
        (0.0, start_path, start_node_id)
    ]

    while queue:
        distance_m, path, node_id = heapq.heappop(queue)
        best_distance, best_path = best[node_id]
        if not math.isclose(distance_m, best_distance, abs_tol=1e-12) or path != best_path:
            continue
        if node_id == destination_node_id:
            return ShortestPath(path, distance_m)

        for neighbor_id, edge_distance_m in graph.neighbors(node_id):
            candidate_distance = distance_m + edge_distance_m
            candidate_path = path + (neighbor_id,)
            previous = best.get(neighbor_id)
            is_better = previous is None or candidate_distance < previous[0] - 1e-12
            is_equal_but_deterministic = (
                previous is not None
                and math.isclose(candidate_distance, previous[0], abs_tol=1e-12)
                and candidate_path < previous[1]
            )
            if is_better or is_equal_but_deterministic:
                best[neighbor_id] = (candidate_distance, candidate_path)
                heapq.heappush(
                    queue,
                    (candidate_distance, candidate_path, neighbor_id),
                )

    raise UnreachablePathError(
        f"No route exists from {start_node_id!r} to {destination_node_id!r}"
    )
