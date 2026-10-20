"""Observation-driven checkpoint validation for synthetic and future camera inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from component3.backend.comp3_reco_navigation.navigation.apriltag import AprilTagLayout
from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    PositionEstimate,
    correct_to_checkpoint,
)
from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.route_anchor import RouteAnchor
from component3.backend.comp3_reco_navigation.navigation.store_graph import StoreGraph


MIN_CHECKPOINT_CONFIDENCE = 0.5
MAX_CHECKPOINT_CORRECTION_M = 2.0


@dataclass(frozen=True, slots=True)
class CheckpointObservation:
    """One labeled tag observation independent of its detection implementation."""

    tag_id: int
    timestamp_s: float
    detection_source: str
    map_id: str
    confidence: float | None = None
    observed_x_m: float | None = None
    observed_y_m: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.tag_id, bool) or not isinstance(self.tag_id, int):
            raise ValueError("checkpoint tag_id must be an integer")
        if (
            isinstance(self.timestamp_s, bool)
            or not isinstance(self.timestamp_s, (int, float))
            or not math.isfinite(self.timestamp_s)
            or self.timestamp_s < 0
        ):
            raise ValueError("checkpoint timestamp must be finite and nonnegative")
        if not isinstance(self.detection_source, str) or not self.detection_source.strip():
            raise ValueError("checkpoint detection_source must be a non-empty string")
        if not isinstance(self.map_id, str) or not self.map_id.strip():
            raise ValueError("checkpoint map_id must be a non-empty string")
        if self.confidence is not None and (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("checkpoint confidence must be within [0, 1]")
        if (self.observed_x_m is None) != (self.observed_y_m is None):
            raise ValueError("checkpoint observed pose requires both x and y")
        if self.observed_x_m is not None and any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in (self.observed_x_m, self.observed_y_m)
        ):
            raise ValueError("checkpoint observed pose must be finite")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CheckpointObservationResult:
    """Validated observation outcome and optional localization correction."""

    accepted: bool
    reason: str
    observation: CheckpointObservation | None
    checkpoint_id: int | None = None
    checkpoint_node_id: str | None = None
    correction_m: float | None = None
    corrected_pose: PositionEstimate | None = None
    duplicate: bool = False
    out_of_order: bool = False
    classification: str = "rejected"
    graph_distance_from_last_checkpoint_m: float | None = None
    graph_distance_from_estimate_m: float | None = None
    reachable_distance_limit_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.corrected_pose is not None:
            result["corrected_pose"] = asdict(self.corrected_pose)
        return result


@dataclass(frozen=True, slots=True)
class CheckpointPlausibilityContext:
    """Online-only inputs for graph and motion plausibility validation."""

    graph: StoreGraph
    estimated_anchor: RouteAnchor
    position_uncertainty_m: float
    maximum_speed_m_s: float
    distance_tolerance_m: float
    last_verified_checkpoint_node_id: str | None = None
    camera_available: bool = True
    allowed_detection_sources: frozenset[str] = frozenset(
        {"mac_camera_opencv", "external_simulated_input", "adaptive_evaluation"}
    )

    def __post_init__(self) -> None:
        for value, label in (
            (self.position_uncertainty_m, "position_uncertainty_m"),
            (self.maximum_speed_m_s, "maximum_speed_m_s"),
            (self.distance_tolerance_m, "distance_tolerance_m"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{label} must be finite and nonnegative")


def _anchor_distance_to_node(
    graph: StoreGraph, anchor: RouteAnchor, node_id: str
) -> float:
    """Return exact graph distance from an anchor to one node."""
    return min(
        partial + dijkstra_shortest_path(graph, endpoint, node_id).total_distance_m
        for endpoint, partial in anchor.endpoint_costs()
    )


class CheckpointObservationProcessor:
    """Accept valid expected checkpoints once and reject unsafe observations."""

    def __init__(
        self,
        layout: AprilTagLayout,
        map_id: str,
        *,
        minimum_confidence: float = MIN_CHECKPOINT_CONFIDENCE,
        maximum_correction_m: float = MAX_CHECKPOINT_CORRECTION_M,
    ) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum checkpoint confidence must be within [0, 1]")
        if not math.isfinite(maximum_correction_m) or maximum_correction_m <= 0:
            raise ValueError("maximum checkpoint correction must be positive")
        self.layout = layout
        self.map_id = map_id
        self.minimum_confidence = float(minimum_confidence)
        self.maximum_correction_m = float(maximum_correction_m)
        self.reset()

    def reset(self) -> None:
        """Clear accepted IDs and observation history for a new navigation run."""
        self.accepted_tag_ids: list[int] = []
        self.last_accepted_timestamp_s: float | None = None
        self.last_observation: CheckpointObservation | None = None
        self.last_result: CheckpointObservationResult | None = None

    def process(
        self,
        observation: CheckpointObservation | None,
        pose: PositionEstimate,
        *,
        expected_tag_id: int | None,
        allow_unexpected_mapped: bool = False,
        plausibility: CheckpointPlausibilityContext | None = None,
    ) -> CheckpointObservationResult:
        """Validate an observation before applying the existing map correction."""
        if observation is None:
            return self._finish(CheckpointObservationResult(False, "missing_observation", None))
        self.last_observation = observation
        checkpoint = self.layout.checkpoint_for(observation.tag_id)
        if plausibility is not None:
            if (
                observation.detection_source == "mac_camera_opencv"
                and not plausibility.camera_available
            ):
                return self._finish(
                    CheckpointObservationResult(
                        False, "camera_unavailable", observation,
                        classification="camera_unavailable_or_invalid_source",
                    )
                )
            if observation.detection_source not in plausibility.allowed_detection_sources:
                return self._finish(
                    CheckpointObservationResult(
                        False, "invalid_detection_source", observation,
                        classification="camera_unavailable_or_invalid_source",
                    )
                )
        if observation.map_id != self.map_id:
            return self._finish(
                CheckpointObservationResult(
                    False, "wrong_map_version", observation,
                    classification="map_version_mismatch",
                )
            )
        if checkpoint is None:
            return self._finish(
                CheckpointObservationResult(
                    False, "unknown_tag", observation,
                    classification="unknown_marker",
                )
            )
        if observation.tag_id in self.accepted_tag_ids:
            return self._finish(
                CheckpointObservationResult(
                    False,
                    "duplicate_observation",
                    observation,
                    checkpoint_id=observation.tag_id,
                    checkpoint_node_id=checkpoint.node_id,
                    duplicate=True,
                    classification="duplicate",
                )
            )
        if (
            self.last_accepted_timestamp_s is not None
            and observation.timestamp_s < self.last_accepted_timestamp_s
        ):
            stale_reason = "stale_observation" if allow_unexpected_mapped else "out_of_order_observation"
            return self._finish(
                CheckpointObservationResult(
                    False,
                    stale_reason,
                    observation,
                    checkpoint_id=observation.tag_id,
                    checkpoint_node_id=checkpoint.node_id,
                    out_of_order=True,
                    classification="stale_observation",
                )
            )
        distance_from_estimate: float | None = None
        distance_from_last: float | None = None
        reachable_limit: float | None = None
        if expected_tag_id is not None and observation.tag_id != expected_tag_id:
            if not allow_unexpected_mapped or plausibility is None:
                return self._finish(
                    CheckpointObservationResult(
                        False,
                        "unexpected_checkpoint",
                        observation,
                        checkpoint_id=observation.tag_id,
                        checkpoint_node_id=checkpoint.node_id,
                        classification="unexpected_mapped_checkpoint",
                    )
                )
            distance_from_estimate = _anchor_distance_to_node(
                plausibility.graph, plausibility.estimated_anchor, checkpoint.node_id
            )
            elapsed_s = (
                observation.timestamp_s - self.last_accepted_timestamp_s
                if self.last_accepted_timestamp_s is not None
                else observation.timestamp_s
            )
            reachable_limit = (
                plausibility.maximum_speed_m_s * max(0.0, elapsed_s)
                + plausibility.position_uncertainty_m
                + plausibility.distance_tolerance_m
            )
            if plausibility.last_verified_checkpoint_node_id is not None:
                distance_from_last = dijkstra_shortest_path(
                    plausibility.graph,
                    plausibility.last_verified_checkpoint_node_id,
                    checkpoint.node_id,
                ).total_distance_m
            estimate_limit = max(
                self.maximum_correction_m,
                plausibility.position_uncertainty_m
                + plausibility.distance_tolerance_m,
            )
            if (
                distance_from_estimate > estimate_limit + 1e-9
                or (
                    distance_from_last is not None
                    and distance_from_last > reachable_limit + 1e-9
                )
            ):
                return self._finish(
                    CheckpointObservationResult(
                        False,
                        "spatially_implausible_observation",
                        observation,
                        checkpoint_id=observation.tag_id,
                        checkpoint_node_id=checkpoint.node_id,
                        classification="spatially_implausible_observation",
                        graph_distance_from_last_checkpoint_m=distance_from_last,
                        graph_distance_from_estimate_m=distance_from_estimate,
                        reachable_distance_limit_m=reachable_limit,
                    )
                )
        if (
            observation.confidence is not None
            and observation.confidence < self.minimum_confidence
        ):
            return self._finish(
                CheckpointObservationResult(
                    False,
                    "confidence_below_threshold",
                    observation,
                    checkpoint_id=observation.tag_id,
                    checkpoint_node_id=checkpoint.node_id,
                    classification="spatially_implausible_observation",
                )
            )
        corrected = correct_to_checkpoint(pose, self.layout, observation.tag_id)
        correction_m = math.hypot(corrected.x_m - pose.x_m, corrected.y_m - pose.y_m)
        if observation.observed_x_m is not None:
            observed_distance_m = math.hypot(
                observation.observed_x_m - checkpoint.x_m,
                observation.observed_y_m - checkpoint.y_m,
            )
            if observed_distance_m > self.maximum_correction_m:
                return self._finish(
                    CheckpointObservationResult(
                        False,
                        "observed_pose_inconsistent",
                        observation,
                        checkpoint_id=observation.tag_id,
                        checkpoint_node_id=checkpoint.node_id,
                        classification="spatially_implausible_observation",
                    )
                )
        if correction_m > self.maximum_correction_m:
            return self._finish(
                CheckpointObservationResult(
                    False,
                    "correction_exceeds_limit",
                    observation,
                    checkpoint_id=observation.tag_id,
                    checkpoint_node_id=checkpoint.node_id,
                    correction_m=correction_m,
                    classification="spatially_implausible_observation",
                )
            )
        self.accepted_tag_ids.append(observation.tag_id)
        self.last_accepted_timestamp_s = observation.timestamp_s
        unexpected_accepted = (
            expected_tag_id is not None
            and observation.tag_id != expected_tag_id
            and allow_unexpected_mapped
        )
        return self._finish(
            CheckpointObservationResult(
                True,
                "accepted_unexpected_plausible" if unexpected_accepted else "accepted",
                observation,
                checkpoint_id=observation.tag_id,
                checkpoint_node_id=checkpoint.node_id,
                correction_m=correction_m,
                corrected_pose=corrected,
                classification=(
                    "unexpected_but_plausible_mapped_checkpoint"
                    if unexpected_accepted
                    else "expected_mapped_checkpoint"
                ),
                graph_distance_from_estimate_m=distance_from_estimate,
                graph_distance_from_last_checkpoint_m=distance_from_last,
                reachable_distance_limit_m=reachable_limit,
            )
        )

    def _finish(self, result: CheckpointObservationResult) -> CheckpointObservationResult:
        self.last_result = result
        return result
