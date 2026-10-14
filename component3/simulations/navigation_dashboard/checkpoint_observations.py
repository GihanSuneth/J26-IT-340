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

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.corrected_pose is not None:
            result["corrected_pose"] = asdict(self.corrected_pose)
        return result


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
    ) -> CheckpointObservationResult:
        """Validate an observation before applying the existing map correction."""
        if observation is None:
            return self._finish(CheckpointObservationResult(False, "missing_observation", None))
        self.last_observation = observation
        checkpoint = self.layout.checkpoint_for(observation.tag_id)
        if observation.map_id != self.map_id:
            return self._finish(
                CheckpointObservationResult(False, "wrong_map_version", observation)
            )
        if checkpoint is None:
            return self._finish(
                CheckpointObservationResult(False, "unknown_tag", observation)
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
                )
            )
        if (
            self.last_accepted_timestamp_s is not None
            and observation.timestamp_s < self.last_accepted_timestamp_s
        ):
            return self._finish(
                CheckpointObservationResult(
                    False,
                    "out_of_order_observation",
                    observation,
                    checkpoint_id=observation.tag_id,
                    checkpoint_node_id=checkpoint.node_id,
                    out_of_order=True,
                )
            )
        if expected_tag_id is not None and observation.tag_id != expected_tag_id:
            return self._finish(
                CheckpointObservationResult(
                    False,
                    "unexpected_checkpoint",
                    observation,
                    checkpoint_id=observation.tag_id,
                    checkpoint_node_id=checkpoint.node_id,
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
                )
            )
        self.accepted_tag_ids.append(observation.tag_id)
        self.last_accepted_timestamp_s = observation.timestamp_s
        return self._finish(
            CheckpointObservationResult(
                True,
                "accepted",
                observation,
                checkpoint_id=observation.tag_id,
                checkpoint_node_id=checkpoint.node_id,
                correction_m=correction_m,
                corrected_pose=corrected,
            )
        )

    def _finish(self, result: CheckpointObservationResult) -> CheckpointObservationResult:
        self.last_result = result
        return result
