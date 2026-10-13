"""Measure trolley distance from a graph route and confirm deviation state."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from .dead_reckoning import PositionEstimate
from .store_graph import StoreGraph


@dataclass(frozen=True, slots=True)
class RouteDeviationResult:
    """Geometric distance and threshold result for one estimated position."""

    distance_m: float
    threshold_m: float
    nearest_segment_index: int | None
    nearest_segment_start_node: str
    nearest_segment_end_node: str
    projection_x_m: float
    projection_y_m: float
    route_progress_m: float
    is_deviating: bool


@dataclass(frozen=True, slots=True)
class DeviationState:
    """One hysteresis-filtered sample and any state transition it caused."""

    measurement: RouteDeviationResult
    exit_threshold_m: float
    is_deviated: bool
    entered_deviation: bool
    recovered: bool
    consecutive_enter_samples: int
    consecutive_recovery_samples: int


def _finite_nonnegative(value: float, name: str) -> float:
    """Validate a finite nonnegative scalar threshold or distance."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return converted


def _route_segments(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
) -> tuple[tuple[str, str, float, float, float, float], ...]:
    """Validate a graph route and return its coordinate line segments."""
    if isinstance(route_node_ids, (str, bytes)):
        raise ValueError("route_node_ids must be a non-empty sequence of node IDs")
    route = tuple(route_node_ids)
    if not route:
        raise ValueError("route_node_ids must not be empty")
    if any(not isinstance(node_id, str) or node_id not in graph for node_id in route):
        raise ValueError("route contains an invalid or unknown graph node")
    for node_id in route:
        node = graph.node(node_id)
        if not math.isfinite(node.x_m) or not math.isfinite(node.y_m):
            raise ValueError(f"graph node {node_id!r} has invalid coordinates")
    segments: list[tuple[str, str, float, float, float, float]] = []
    for start_id, end_id in zip(route, route[1:]):
        try:
            graph.edge_weight(start_id, end_id)
        except KeyError as exc:
            raise ValueError(
                f"consecutive route nodes {start_id!r} and {end_id!r} are not connected"
            ) from exc
        start = graph.node(start_id)
        end = graph.node(end_id)
        segments.append(
            (start_id, end_id, start.x_m, start.y_m, end.x_m, end.y_m)
        )
    return tuple(segments)


def _position_coordinates(position: PositionEstimate) -> tuple[float, float]:
    """Validate and return finite planar coordinates from an estimate."""
    if not isinstance(position, PositionEstimate):
        raise ValueError("position must be a PositionEstimate")
    coordinates = (position.x_m, position.y_m)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in coordinates
    ):
        raise ValueError("position coordinates must be finite numbers")
    return float(position.x_m), float(position.y_m)


def _nearest_route_point(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    segments: tuple[tuple[str, str, float, float, float, float], ...],
    x_m: float,
    y_m: float,
) -> tuple[float, int | None, str, str, float, float, float]:
    """Project a point onto every clamped route segment and choose the nearest."""
    if not segments:
        node_id = route_node_ids[0]
        node = graph.node(node_id)
        return (
            math.hypot(x_m - node.x_m, y_m - node.y_m),
            None,
            node_id,
            node_id,
            node.x_m,
            node.y_m,
            0.0,
        )

    best: tuple[float, int | None, str, str, float, float, float] | None = None
    cumulative_m = 0.0
    for index, (start_id, end_id, x1, y1, x2, y2) in enumerate(segments):
        dx = x2 - x1
        dy = y2 - y1
        length_squared = dx * dx + dy * dy
        length_m = math.sqrt(length_squared)
        if length_squared == 0.0:
            fraction = 0.0
        else:
            fraction = ((x_m - x1) * dx + (y_m - y1) * dy) / length_squared
            fraction = min(1.0, max(0.0, fraction))
        projected_x = x1 + fraction * dx
        projected_y = y1 + fraction * dy
        distance = math.hypot(x_m - projected_x, y_m - projected_y)
        candidate = (
            distance,
            index,
            start_id,
            end_id,
            projected_x,
            projected_y,
            cumulative_m + fraction * length_m,
        )
        if best is None or candidate[0] < best[0]:
            best = candidate
        cumulative_m += length_m
    if best is None:
        raise ValueError("route must contain at least one node")
    return best


def evaluate_route_deviation(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    position: PositionEstimate,
    threshold_m: float,
) -> RouteDeviationResult:
    """Measure minimum Euclidean distance to a connected graph-node polyline.

    ``threshold_m`` is an explicit metre-valued boundary; distance strictly
    greater than the boundary is classified as an instantaneous deviation.
    """
    threshold = _finite_nonnegative(threshold_m, "threshold_m")
    x_m, y_m = _position_coordinates(position)
    route = tuple(route_node_ids) if not isinstance(route_node_ids, (str, bytes)) else ()
    segments = _route_segments(graph, route_node_ids)
    (
        distance,
        segment_index,
        start_id,
        end_id,
        projected_x,
        projected_y,
        route_progress,
    ) = _nearest_route_point(
        graph, route, segments, x_m, y_m
    )
    return RouteDeviationResult(
        distance_m=distance,
        threshold_m=threshold,
        nearest_segment_index=segment_index,
        nearest_segment_start_node=start_id,
        nearest_segment_end_node=end_id,
        projection_x_m=projected_x,
        projection_y_m=projected_y,
        route_progress_m=route_progress,
        is_deviating=distance > threshold,
    )


class RouteDeviationMonitor:
    """Apply deterministic distance hysteresis and consecutive-sample rules."""

    def __init__(
        self,
        graph: StoreGraph,
        route_node_ids: Sequence[str],
        *,
        threshold_m: float | None = None,
        base_threshold_m: float = 0.3,
        threshold_slope_per_m: float = 0.02,
        hysteresis_m: float = 0.15,
        enter_confirmations: int = 3,
        recovery_confirmations: int = 2,
    ) -> None:
        """Configure a fixed or progress-scaled threshold and state counts."""
        self._graph = graph
        self._route_node_ids = tuple(route_node_ids)
        self._segments = _route_segments(graph, self._route_node_ids)
        self._fixed_threshold_m = (
            None
            if threshold_m is None
            else _finite_nonnegative(threshold_m, "threshold_m")
        )
        self._base_threshold_m = _finite_nonnegative(
            base_threshold_m, "base_threshold_m"
        )
        self._threshold_slope_per_m = _finite_nonnegative(
            threshold_slope_per_m, "threshold_slope_per_m"
        )
        self._hysteresis_m = _finite_nonnegative(hysteresis_m, "hysteresis_m")
        if self._fixed_threshold_m is None and (
            self._base_threshold_m == 0.0 and self._threshold_slope_per_m == 0.0
        ):
            self._fixed_threshold_m = 0.0
        if (
            isinstance(enter_confirmations, bool)
            or not isinstance(enter_confirmations, int)
            or enter_confirmations < 1
        ):
            raise ValueError("enter_confirmations must be a positive integer")
        if (
            isinstance(recovery_confirmations, bool)
            or not isinstance(recovery_confirmations, int)
            or recovery_confirmations < 1
        ):
            raise ValueError("recovery_confirmations must be a positive integer")
        self._enter_confirmations = enter_confirmations
        self._recovery_confirmations = recovery_confirmations
        self.reset()

    @property
    def is_deviated(self) -> bool:
        """Return whether the confirmed state is currently off-route."""
        return self._is_deviated

    def reset(self) -> None:
        """Reset the confirmation state and consecutive-sample counters."""
        self._is_deviated = False
        self._above_count = 0
        self._below_count = 0

    def update(self, position: PositionEstimate) -> DeviationState:
        """Consume one estimate and return its deterministic filtered state."""
        x_m, y_m = _position_coordinates(position)
        preliminary = _nearest_route_point(
            self._graph,
            self._route_node_ids,
            self._segments,
            x_m,
            y_m,
        )
        route_progress_m = preliminary[6]
        threshold = (
            self._fixed_threshold_m
            if self._fixed_threshold_m is not None
            else self._base_threshold_m
            + self._threshold_slope_per_m * route_progress_m
        )
        measurement = evaluate_route_deviation(
            self._graph, self._route_node_ids, position, threshold
        )
        exit_threshold = max(0.0, measurement.threshold_m - self._hysteresis_m)
        entered = False
        recovered = False
        if not self._is_deviated:
            self._below_count = 0
            if measurement.is_deviating:
                self._above_count += 1
                if self._above_count >= self._enter_confirmations:
                    self._is_deviated = True
                    entered = True
                    self._above_count = 0
            else:
                self._above_count = 0
        else:
            self._above_count = 0
            if measurement.distance_m <= exit_threshold:
                self._below_count += 1
                if self._below_count >= self._recovery_confirmations:
                    self._is_deviated = False
                    recovered = True
                    self._below_count = 0
            else:
                self._below_count = 0
        return DeviationState(
            measurement=measurement,
            exit_threshold_m=exit_threshold,
            is_deviated=self._is_deviated,
            entered_deviation=entered,
            recovered=recovered,
            consecutive_enter_samples=self._above_count,
            consecutive_recovery_samples=self._below_count,
        )
