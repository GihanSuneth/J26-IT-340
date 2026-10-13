"""Exact deterministic multi-stop routing with Held-Karp dynamic programming."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from .dijkstra import (
    ShortestPath,
    UnknownNodeError,
    UnreachablePathError,
    dijkstra_shortest_path,
)
from .store_graph import StoreGraph


DEFAULT_MAX_UNIQUE_STOPS = 10
_DISTANCE_TOLERANCE = 1e-12


class StopLimitExceededError(ValueError):
    """Raised before optimization when the practical DP stop limit is exceeded."""


class UnreachableLocationError(ValueError):
    """Raised when required locations cannot be joined by graph paths."""


@dataclass(frozen=True, slots=True)
class OrderedRoute:
    """An expanded graph route through a specified stop order."""

    stop_ids: tuple[str, ...]
    route_node_ids: tuple[str, ...]
    total_distance_m: float


@dataclass(frozen=True, slots=True)
class HeldKarpRoute:
    """Complete result of fixed-start, fixed-checkout multi-stop optimization."""

    original_requested_stop_ids: tuple[str, ...]
    unique_required_stop_ids: tuple[str, ...]
    optimized_stop_ids: tuple[str, ...]
    route_node_ids: tuple[str, ...]
    total_distance_m: float
    start_node_id: str
    checkout_node_id: str


def _validate_locations(
    graph: StoreGraph,
    start_node_id: str,
    requested_stop_ids: tuple[str, ...],
    checkout_node_id: str,
) -> None:
    if start_node_id not in graph:
        raise UnknownNodeError(f"Unknown start node: {start_node_id!r}")
    for stop_id in requested_stop_ids:
        if stop_id not in graph:
            raise UnknownNodeError(f"Unknown shopping-stop node: {stop_id!r}")
    if checkout_node_id not in graph:
        raise UnknownNodeError(f"Unknown checkout node: {checkout_node_id!r}")


def _unique_required_stops(
    requested_stop_ids: tuple[str, ...],
    start_node_id: str,
    checkout_node_id: str,
) -> tuple[str, ...]:
    """Deduplicate stops stably and remove the fixed route endpoints."""
    seen = {start_node_id, checkout_node_id}
    unique: list[str] = []
    for stop_id in requested_stop_ids:
        if stop_id not in seen:
            seen.add(stop_id)
            unique.append(stop_id)
    return tuple(unique)


def _path_or_context(
    graph: StoreGraph,
    source_id: str,
    destination_id: str,
) -> ShortestPath:
    try:
        return dijkstra_shortest_path(graph, source_id, destination_id)
    except UnreachablePathError as exc:
        raise UnreachableLocationError(
            f"Required location {destination_id!r} is unreachable from {source_id!r}"
        ) from exc


def _expand_location_order(
    graph: StoreGraph,
    location_order: tuple[str, ...],
) -> tuple[tuple[str, ...], float]:
    """Expand location-to-location shortest paths into actual graph nodes."""
    if len(location_order) == 1:
        return location_order, 0.0

    expanded: list[str] = []
    total_distance_m = 0.0
    for source_id, destination_id in zip(location_order, location_order[1:]):
        segment = _path_or_context(graph, source_id, destination_id)
        if expanded:
            expanded.extend(segment.node_ids[1:])
        else:
            expanded.extend(segment.node_ids)
        total_distance_m += segment.total_distance_m
    return tuple(expanded), total_distance_m


def route_for_stop_order(
    graph: StoreGraph,
    start_node_id: str,
    shopping_stop_node_ids: Sequence[str],
    checkout_node_id: str,
) -> OrderedRoute:
    """Return the graph route for a requested order after stable deduplication.

    This helper supplies a reproducible original-order baseline. It is not an
    optimizer. Start and checkout remain fixed even when either is repeated in
    ``shopping_stop_node_ids``.
    """
    requested = tuple(shopping_stop_node_ids)
    _validate_locations(graph, start_node_id, requested, checkout_node_id)
    unique_stops = _unique_required_stops(requested, start_node_id, checkout_node_id)
    location_order = (start_node_id, *unique_stops, checkout_node_id)
    route_node_ids, total_distance_m = _expand_location_order(graph, location_order)
    return OrderedRoute(unique_stops, route_node_ids, total_distance_m)


def held_karp_route(
    graph: StoreGraph,
    start_node_id: str,
    shopping_stop_node_ids: Sequence[str],
    checkout_node_id: str,
    *,
    max_unique_stops: int = DEFAULT_MAX_UNIQUE_STOPS,
) -> HeldKarpRoute:
    """Optimize required stops between a fixed start and checkout.

    State ``DP[mask, j]`` stores the minimum distance from the start that visits
    exactly the stops in ``mask`` and finishes at stop ``j``. The recurrence is
    ``DP[mask, j] = min(DP[mask without j, k] + d(k, j))``. Distances and route
    segments are calculated by deterministic Dijkstra traversal over graph-edge
    weights. Equal-distance states select the lexicographically smaller stop
    order.

    With ``n`` unique required stops, time complexity is ``O(n^2 * 2^n)`` and
    memory complexity is ``O(n * 2^n)``, excluding Dijkstra preprocessing.
    ``max_unique_stops`` is enforced before allocating DP states.
    """
    if (
        isinstance(max_unique_stops, bool)
        or not isinstance(max_unique_stops, int)
        or max_unique_stops < 0
    ):
        raise ValueError("max_unique_stops must be a non-negative integer")

    requested = tuple(shopping_stop_node_ids)
    _validate_locations(graph, start_node_id, requested, checkout_node_id)
    unique_requested = _unique_required_stops(
        requested, start_node_id, checkout_node_id
    )
    if len(unique_requested) > max_unique_stops:
        raise StopLimitExceededError(
            f"Held-Karp supports at most {max_unique_stops} unique shopping stops; "
            f"received {len(unique_requested)}"
        )

    if not unique_requested:
        direct = _path_or_context(graph, start_node_id, checkout_node_id)
        return HeldKarpRoute(
            original_requested_stop_ids=requested,
            unique_required_stop_ids=(),
            optimized_stop_ids=(),
            route_node_ids=direct.node_ids,
            total_distance_m=direct.total_distance_m,
            start_node_id=start_node_id,
            checkout_node_id=checkout_node_id,
        )

    # Lexical indexing makes bit positions and equal-cost decisions stable.
    stops = tuple(sorted(unique_requested))
    pairwise: dict[tuple[str, str], ShortestPath] = {}

    def shortest(source_id: str, destination_id: str) -> ShortestPath:
        key = (source_id, destination_id)
        if key not in pairwise:
            pairwise[key] = _path_or_context(graph, source_id, destination_id)
        return pairwise[key]

    # Each state stores (distance from start, ordered visited stops).
    dp: dict[tuple[int, int], tuple[float, tuple[str, ...]]] = {}
    for index, stop_id in enumerate(stops):
        path = shortest(start_node_id, stop_id)
        dp[(1 << index, index)] = (path.total_distance_m, (stop_id,))

    full_mask = (1 << len(stops)) - 1
    for mask in range(1, full_mask + 1):
        for last_index, last_id in enumerate(stops):
            state = dp.get((mask, last_index))
            if state is None:
                continue
            distance_m, stop_order = state
            for next_index, next_id in enumerate(stops):
                bit = 1 << next_index
                if mask & bit:
                    continue
                candidate_distance = (
                    distance_m + shortest(last_id, next_id).total_distance_m
                )
                candidate_order = stop_order + (next_id,)
                key = (mask | bit, next_index)
                previous = dp.get(key)
                if previous is None or candidate_distance < previous[0] - _DISTANCE_TOLERANCE:
                    dp[key] = (candidate_distance, candidate_order)
                elif (
                    math.isclose(
                        candidate_distance,
                        previous[0],
                        abs_tol=_DISTANCE_TOLERANCE,
                    )
                    and candidate_order < previous[1]
                ):
                    dp[key] = (candidate_distance, candidate_order)

    best_distance = math.inf
    best_order: tuple[str, ...] | None = None
    for last_index, last_id in enumerate(stops):
        distance_to_last, stop_order = dp[(full_mask, last_index)]
        candidate_distance = (
            distance_to_last + shortest(last_id, checkout_node_id).total_distance_m
        )
        if candidate_distance < best_distance - _DISTANCE_TOLERANCE:
            best_distance = candidate_distance
            best_order = stop_order
        elif (
            math.isclose(
                candidate_distance,
                best_distance,
                abs_tol=_DISTANCE_TOLERANCE,
            )
            and (best_order is None or stop_order < best_order)
        ):
            best_order = stop_order

    assert best_order is not None
    route_node_ids, expanded_distance = _expand_location_order(
        graph,
        (start_node_id, *best_order, checkout_node_id),
    )
    return HeldKarpRoute(
        original_requested_stop_ids=requested,
        unique_required_stop_ids=unique_requested,
        optimized_stop_ids=best_order,
        route_node_ids=route_node_ids,
        total_distance_m=expanded_distance,
        start_node_id=start_node_id,
        checkout_node_id=checkout_node_id,
    )
