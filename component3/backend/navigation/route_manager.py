"""Manage shopping destinations and atomically recalculate a route on deviation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from .deviation import DeviationState
from .dead_reckoning import PositionEstimate
from .dijkstra import UnknownNodeError
from .held_karp import held_karp_route
from .store_graph import StoreGraph


def _validated_snap_distance(value: float) -> float:
    """Return a finite, nonnegative maximum snapping distance."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("max_snapping_distance_m must be finite and nonnegative")
    return float(value)


def _is_valid_position(position: object) -> bool:
    """Check that an estimate contains four finite, non-boolean numbers."""
    if not isinstance(position, PositionEstimate):
        return False
    values = (
        position.x_m,
        position.y_m,
        position.heading_rad,
        position.timestamp_s,
    )
    return all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        for value in values
    )


@dataclass(frozen=True, slots=True)
class GraphLocalization:
    """Nearest-edge projection and deterministic node anchor for routing."""

    success: bool
    start_node_id: str | None
    edge_start_node_id: str | None
    edge_end_node_id: str | None
    projected_x_m: float | None
    projected_y_m: float | None
    snap_distance_m: float | None
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class RouteRecalculation:
    """One reroute attempt, including enough data to audit atomic outcomes."""

    trigger_timestamp_s: float
    reroute_timestamp_s: float
    previous_route: tuple[str, ...]
    new_route: tuple[str, ...]
    localization: GraphLocalization
    remaining_destinations: tuple[str, ...]
    previous_route_distance_m: float
    new_route_distance_m: float | None
    failure_reason: str | None
    successful: bool

    @property
    def delay_s(self) -> float:
        """Return trigger-to-route-computation delay in seconds."""
        return self.reroute_timestamp_s - self.trigger_timestamp_s


@dataclass(frozen=True, slots=True)
class VisitConfirmation:
    """Result of an explicit destination-arrival confirmation event."""

    destination_node_id: str
    timestamp_s: float
    confirmed: bool
    remaining_destinations: tuple[str, ...]
    failure_reason: str | None


def localize_position_to_graph(
    graph: StoreGraph,
    position: PositionEstimate,
    max_snapping_distance_m: float,
) -> GraphLocalization:
    """Project an estimate onto its closest valid edge and select an endpoint.

    Endpoint selection minimizes distance from the projected point to either
    edge endpoint; ties select the lexicographically smaller node ID. Equal
    edge projection distances select the lexicographically smaller unordered
    edge. The node-only routing algorithms then begin at that endpoint.
    """
    maximum_distance = _validated_snap_distance(max_snapping_distance_m)
    if not _is_valid_position(position):
        return GraphLocalization(
            False, None, None, None, None, None, None, "invalid_position"
        )
    assert isinstance(position, PositionEstimate)
    x_m, y_m = float(position.x_m), float(position.y_m)
    best: tuple[float, tuple[str, str], str, str, float, float] | None = None
    for edge in graph.edges:
        start_id, end_id = sorted((edge.source, edge.target))
        start = graph.node(start_id)
        end = graph.node(end_id)
        if not all(
            math.isfinite(coordinate)
            for coordinate in (start.x_m, start.y_m, end.x_m, end.y_m)
        ):
            return GraphLocalization(
                False,
                None,
                start_id,
                end_id,
                None,
                None,
                None,
                "graph_contains_invalid_coordinates",
            )
        dx = end.x_m - start.x_m
        dy = end.y_m - start.y_m
        length_squared = dx * dx + dy * dy
        if length_squared == 0.0:
            fraction = 0.0
        else:
            fraction = ((x_m - start.x_m) * dx + (y_m - start.y_m) * dy) / length_squared
            fraction = min(1.0, max(0.0, fraction))
        projected_x = start.x_m + fraction * dx
        projected_y = start.y_m + fraction * dy
        distance = math.hypot(x_m - projected_x, y_m - projected_y)
        candidate = (distance, (start_id, end_id), start_id, end_id, projected_x, projected_y)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        return GraphLocalization(
            False, None, None, None, None, None, None, "graph_has_no_edges"
        )
    distance, _, edge_start, edge_end, projected_x, projected_y = best
    if distance > maximum_distance:
        return GraphLocalization(
            False,
            None,
            edge_start,
            edge_end,
            projected_x,
            projected_y,
            distance,
            "position_exceeds_max_snapping_distance",
        )
    start_node = graph.node(edge_start)
    end_node = graph.node(edge_end)
    start_distance = math.hypot(projected_x - start_node.x_m, projected_y - start_node.y_m)
    end_distance = math.hypot(projected_x - end_node.x_m, projected_y - end_node.y_m)
    anchor = (
        edge_start
        if start_distance < end_distance
        or (math.isclose(start_distance, end_distance) and edge_start < edge_end)
        else edge_end
    )
    return GraphLocalization(
        True,
        anchor,
        edge_start,
        edge_end,
        projected_x,
        projected_y,
        distance,
        None,
    )


class RouteManager:
    """Maintain shopping-session route state and reroute only on confirmed entry."""

    def __init__(
        self,
        graph: StoreGraph,
        start_node_id: str,
        shopping_destination_ids: Sequence[str],
        checkout_node_id: str,
        *,
        max_snapping_distance_m: float = 1.0,
    ) -> None:
        """Initialize a validated optimized route and unique remaining stops."""
        if start_node_id not in graph:
            raise UnknownNodeError(f"Unknown route start node: {start_node_id!r}")
        if checkout_node_id not in graph:
            raise UnknownNodeError(f"Unknown checkout node: {checkout_node_id!r}")
        self.graph = graph
        self.original_shopping_destinations = tuple(shopping_destination_ids)
        self.visited_destinations: list[str] = []
        self.remaining_destinations = self._stable_unique(
            node_id
            for node_id in self.original_shopping_destinations
            if node_id not in {start_node_id, checkout_node_id}
        )
        self.checkout_node_id = checkout_node_id
        self.max_snapping_distance_m = _validated_snap_distance(
            max_snapping_distance_m
        )
        self.current_position_estimate: PositionEstimate | None = None
        self.current_start_node_id = start_node_id
        initial = held_karp_route(
            graph,
            start_node_id,
            self.remaining_destinations,
            checkout_node_id,
        )
        self.current_planned_route = initial.route_node_ids
        self.current_route_distance_m = initial.total_distance_m
        self.confirmed_deviation = False
        self._reroute_latched = False
        self.rerouting_history: list[RouteRecalculation] = []

    @staticmethod
    def _stable_unique(node_ids: Iterable[str]) -> tuple[str, ...]:
        """Return stable unique node IDs from an iterable."""
        result: list[str] = []
        seen: set[str] = set()
        for node_id in node_ids:
            if node_id not in seen:
                seen.add(node_id)
                result.append(node_id)
        return tuple(result)

    @property
    def current_route(self) -> tuple[str, ...]:
        """Alias for the active planned route."""
        return self.current_planned_route

    def confirm_destination_visit(
        self,
        destination_node_id: str,
        timestamp_s: float,
    ) -> VisitConfirmation:
        """Mark a stop visited only from an explicit valid confirmation event."""
        if (
            isinstance(timestamp_s, bool)
            or not isinstance(timestamp_s, (int, float))
            or not math.isfinite(timestamp_s)
            or timestamp_s < 0
        ):
            return VisitConfirmation(
                destination_node_id,
                timestamp_s,
                False,
                self.remaining_destinations,
                "invalid_visit_timestamp",
            )
        if destination_node_id not in self.remaining_destinations:
            return VisitConfirmation(
                destination_node_id,
                timestamp_s,
                False,
                self.remaining_destinations,
                "destination_not_remaining",
            )
        proposed_remaining = tuple(
            node_id
            for node_id in self.remaining_destinations
            if node_id != destination_node_id
        )
        try:
            planned = held_karp_route(
                self.graph,
                destination_node_id,
                proposed_remaining,
                self.checkout_node_id,
            )
        except (ValueError, KeyError) as exc:
            return VisitConfirmation(
                destination_node_id,
                timestamp_s,
                False,
                self.remaining_destinations,
                f"visit_route_recalculation_failed: {exc}",
            )
        self.visited_destinations.append(destination_node_id)
        self.remaining_destinations = proposed_remaining
        self.current_start_node_id = destination_node_id
        self.current_planned_route = planned.route_node_ids
        self.current_route_distance_m = planned.total_distance_m
        return VisitConfirmation(
            destination_node_id,
            timestamp_s,
            True,
            self.remaining_destinations,
            None,
        )

    def process_position(
        self,
        position: PositionEstimate,
        deviation_state: DeviationState,
    ) -> RouteRecalculation | None:
        """Update the estimate and reroute once on detector entry transition."""
        if _is_valid_position(position):
            assert isinstance(position, PositionEstimate)
            self.current_position_estimate = position
        self.confirmed_deviation = deviation_state.is_deviated
        if not deviation_state.is_deviated:
            self._reroute_latched = False
            return None
        if not deviation_state.entered_deviation or self._reroute_latched:
            return None
        self._reroute_latched = True
        return self.recalculate_after_deviation(position)

    def recalculate_after_deviation(
        self,
        position: PositionEstimate,
    ) -> RouteRecalculation:
        """Attempt localization and route optimization with atomic route updates."""
        previous_route = self.current_planned_route
        previous_distance = self.current_route_distance_m
        localization = localize_position_to_graph(
            self.graph, position, self.max_snapping_distance_m
        )
        trigger_time = (
            position.timestamp_s
            if isinstance(position, PositionEstimate)
            and math.isfinite(position.timestamp_s)
            and position.timestamp_s >= 0
            else 0.0
        )
        failure: str | None = localization.failure_reason
        planned_route = previous_route
        planned_distance: float | None = None
        if localization.success:
            start_node_id = localization.start_node_id
            if start_node_id is None:
                failure = "localization_missing_start_node"
            elif start_node_id == self.checkout_node_id and self.remaining_destinations:
                failure = "already_at_checkout_with_remaining_destinations"
            else:
                try:
                    planned = held_karp_route(
                        self.graph,
                        start_node_id,
                        self.remaining_destinations,
                        self.checkout_node_id,
                    )
                    planned_route = planned.route_node_ids
                    planned_distance = planned.total_distance_m
                except (ValueError, KeyError) as exc:
                    failure = f"route_computation_failed: {exc}"
        record = RouteRecalculation(
            trigger_timestamp_s=trigger_time,
            reroute_timestamp_s=trigger_time,
            previous_route=previous_route,
            new_route=planned_route if failure is None else previous_route,
            localization=localization,
            remaining_destinations=self.remaining_destinations,
            previous_route_distance_m=previous_distance,
            new_route_distance_m=planned_distance,
            failure_reason=failure,
            successful=failure is None,
        )
        self.rerouting_history.append(record)
        if record.successful:
            self.current_planned_route = record.new_route
            self.current_route_distance_m = planned_distance or 0.0
            self.current_start_node_id = localization.start_node_id or self.current_start_node_id
        return record
