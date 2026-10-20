"""Exact graph routing from node or mid-edge navigation positions."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Sequence

from .dead_reckoning import PositionEstimate
from .held_karp import HeldKarpRoute, held_karp_route
from .store_graph import StoreGraph


TravelDirection = Literal["stopped", "toward_start", "toward_end"]


@dataclass(frozen=True, slots=True)
class RouteAnchor:
    """A graph node or exact position on one undirected graph edge."""

    anchor_type: Literal["node", "edge"]
    node_id: str | None
    edge_start_node_id: str | None
    edge_end_node_id: str | None
    distance_to_start_m: float
    distance_to_end_m: float
    edge_length_m: float
    projected_x_m: float
    projected_y_m: float
    snap_distance_m: float
    travel_direction: TravelDirection
    route_revision: int

    def endpoint_costs(self, *, allow_reverse: bool = True) -> tuple[tuple[str, float], ...]:
        """Return reachable graph endpoints and exact partial-edge costs."""
        if self.anchor_type == "node":
            assert self.node_id is not None
            return ((self.node_id, 0.0),)
        assert self.edge_start_node_id is not None and self.edge_end_node_id is not None
        candidates = (
            (self.edge_start_node_id, self.distance_to_start_m),
            (self.edge_end_node_id, self.distance_to_end_m),
        )
        if allow_reverse or self.travel_direction == "stopped":
            return candidates
        if self.travel_direction == "toward_start":
            return (candidates[0],)
        return (candidates[1],)

    def to_dict(self) -> dict[str, object]:
        return {
            "anchor_type": self.anchor_type,
            "node_id": self.node_id,
            "edge_start_node_id": self.edge_start_node_id,
            "edge_end_node_id": self.edge_end_node_id,
            "distance_to_start_m": self.distance_to_start_m,
            "distance_to_end_m": self.distance_to_end_m,
            "edge_length_m": self.edge_length_m,
            "projected_x_m": self.projected_x_m,
            "projected_y_m": self.projected_y_m,
            "snap_distance_m": self.snap_distance_m,
            "travel_direction": self.travel_direction,
            "route_revision": self.route_revision,
        }


@dataclass(frozen=True, slots=True)
class AnchoredRoutePlan:
    """Held–Karp result plus the exact cost from a non-node route anchor."""

    anchor: RouteAnchor
    chosen_endpoint_node_id: str
    partial_edge_distance_m: float
    optimized_stop_ids: tuple[str, ...]
    route_node_ids: tuple[str, ...]
    graph_route_distance_m: float
    total_distance_m: float

    def to_dict(self) -> dict[str, object]:
        return {
            "anchor": self.anchor.to_dict(),
            "chosen_endpoint_node_id": self.chosen_endpoint_node_id,
            "partial_edge_distance_m": self.partial_edge_distance_m,
            "optimized_stop_ids": list(self.optimized_stop_ids),
            "route_node_ids": list(self.route_node_ids),
            "graph_route_distance_m": self.graph_route_distance_m,
            "total_distance_m": self.total_distance_m,
        }


def node_route_anchor(
    graph: StoreGraph,
    node_id: str,
    *,
    route_revision: int = 0,
    travel_direction: TravelDirection = "stopped",
) -> RouteAnchor:
    """Create a zero-partial-distance anchor at one graph node."""
    if node_id not in graph:
        raise ValueError(f"Unknown route-anchor node: {node_id!r}")
    if route_revision < 0:
        raise ValueError("route_revision must be nonnegative")
    node = graph.node(node_id)
    return RouteAnchor(
        "node", node_id, None, None, 0.0, 0.0, 0.0,
        node.x_m, node.y_m, 0.0, travel_direction, route_revision,
    )


def edge_route_anchor(
    graph: StoreGraph,
    edge_start_node_id: str,
    edge_end_node_id: str,
    distance_from_start_m: float,
    *,
    route_revision: int = 0,
    travel_direction: TravelDirection = "stopped",
    snap_distance_m: float = 0.0,
) -> RouteAnchor:
    """Create an exact distance-based position on a validated graph edge."""
    if travel_direction not in {"stopped", "toward_start", "toward_end"}:
        raise ValueError("invalid route-anchor travel direction")
    if route_revision < 0:
        raise ValueError("route_revision must be nonnegative")
    try:
        edge_length = graph.edge_weight(edge_start_node_id, edge_end_node_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    values = (distance_from_start_m, snap_distance_m)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or value < 0
        for value in values
    ):
        raise ValueError("anchor distances must be finite and nonnegative")
    distance_from_start = float(distance_from_start_m)
    if distance_from_start > edge_length + 1e-9:
        raise ValueError("distance_from_start_m exceeds the graph edge length")
    distance_from_start = min(edge_length, distance_from_start)
    start = graph.node(edge_start_node_id)
    end = graph.node(edge_end_node_id)
    fraction = distance_from_start / edge_length
    return RouteAnchor(
        "edge",
        None,
        edge_start_node_id,
        edge_end_node_id,
        distance_from_start,
        edge_length - distance_from_start,
        edge_length,
        start.x_m + (end.x_m - start.x_m) * fraction,
        start.y_m + (end.y_m - start.y_m) * fraction,
        float(snap_distance_m),
        travel_direction,
        route_revision,
    )


def route_anchor_from_position(
    graph: StoreGraph,
    position: PositionEstimate,
    *,
    max_snap_distance_m: float,
    route_revision: int = 0,
    travel_direction: TravelDirection = "stopped",
    preferred_edge: tuple[str, str] | None = None,
) -> RouteAnchor:
    """Project an estimated pose onto a graph edge without choosing one endpoint."""
    if not math.isfinite(max_snap_distance_m) or max_snap_distance_m < 0:
        raise ValueError("max_snap_distance_m must be finite and nonnegative")
    if not isinstance(position, PositionEstimate):
        raise ValueError("position must be a PositionEstimate")
    edges = graph.edges
    if preferred_edge is not None:
        try:
            graph.edge_weight(*preferred_edge)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        edges = tuple(
            edge for edge in graph.edges
            if {edge.source, edge.target} == set(preferred_edge)
        )
    best: tuple[float, str, str, float] | None = None
    for edge in edges:
        start_id, end_id = edge.source, edge.target
        start, end = graph.node(start_id), graph.node(end_id)
        dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
        geometric_length_sq = dx * dx + dy * dy
        fraction = 0.0 if geometric_length_sq == 0 else (
            ((position.x_m - start.x_m) * dx + (position.y_m - start.y_m) * dy)
            / geometric_length_sq
        )
        fraction = min(1.0, max(0.0, fraction))
        px, py = start.x_m + fraction * dx, start.y_m + fraction * dy
        snap = math.hypot(position.x_m - px, position.y_m - py)
        candidate = (snap, min(start_id, end_id), max(start_id, end_id), fraction)
        if best is None or candidate[:3] < best[:3]:
            best = candidate
    if best is None or best[0] > max_snap_distance_m:
        raise ValueError("position exceeds maximum graph snap distance")
    snap, lexical_start, lexical_end, fraction = best
    # Projection used the edge's stored orientation; recover its distance in the
    # deterministic lexical orientation for stable serialization.
    stored = next(
        edge for edge in edges
        if {edge.source, edge.target} == {lexical_start, lexical_end}
    )
    if stored.source != lexical_start:
        fraction = 1.0 - fraction
    edge_length = graph.edge_weight(lexical_start, lexical_end)
    distance = edge_length * fraction
    if distance <= 1e-9:
        return node_route_anchor(
            graph, lexical_start, route_revision=route_revision,
            travel_direction=travel_direction,
        )
    if edge_length - distance <= 1e-9:
        return node_route_anchor(
            graph, lexical_end, route_revision=route_revision,
            travel_direction=travel_direction,
        )
    return edge_route_anchor(
        graph, lexical_start, lexical_end, distance,
        route_revision=route_revision, travel_direction=travel_direction,
        snap_distance_m=snap,
    )


def held_karp_route_from_anchor(
    graph: StoreGraph,
    anchor: RouteAnchor,
    shopping_stop_node_ids: Sequence[str],
    checkout_node_id: str,
    *,
    allow_reverse: bool = True,
) -> AnchoredRoutePlan:
    """Return the exact best route through either reachable edge endpoint."""
    candidates: list[tuple[float, str, HeldKarpRoute, float]] = []
    for endpoint, partial_cost in anchor.endpoint_costs(allow_reverse=allow_reverse):
        route = held_karp_route(
            graph, endpoint, shopping_stop_node_ids, checkout_node_id
        )
        candidates.append(
            (partial_cost + route.total_distance_m, endpoint, route, partial_cost)
        )
    total, endpoint, route, partial = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2].optimized_stop_ids),
    )
    return AnchoredRoutePlan(
        anchor=anchor,
        chosen_endpoint_node_id=endpoint,
        partial_edge_distance_m=partial,
        optimized_stop_ids=route.optimized_stop_ids,
        route_node_ids=route.route_node_ids,
        graph_route_distance_m=route.total_distance_m,
        total_distance_m=total,
    )
