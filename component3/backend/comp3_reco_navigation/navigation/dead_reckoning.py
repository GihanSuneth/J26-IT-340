"""Integrate wheel-displacement and IMU-yaw measurements for planar position."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .apriltag import AprilTagLayout, AprilTagCheckpoint


def normalize_heading(heading_rad: float) -> float:
    """Normalize a finite angle to [-pi, pi)."""
    if not math.isfinite(heading_rad):
        raise ValueError("heading_rad must be finite")
    normalized = (heading_rad + math.pi) % (2.0 * math.pi) - math.pi
    return 0.0 if normalized == 0.0 else normalized


@dataclass(frozen=True, slots=True)
class MotionMeasurement:
    """Sensor-only movement sample; it intentionally contains no ground truth."""

    timestamp_s: float
    wheel_displacement_m: float
    imu_yaw_delta_rad: float


@dataclass(frozen=True, slots=True)
class PositionEstimate:
    """Estimated planar pose and the timestamp of its latest measurement."""

    x_m: float
    y_m: float
    heading_rad: float
    timestamp_s: float

    def __post_init__(self) -> None:
        if self.timestamp_s < 0:
            raise ValueError("initial pose timestamp must be nonnegative")
        if not all(
            math.isfinite(value)
            for value in (self.x_m, self.y_m, self.heading_rad, self.timestamp_s)
        ):
            raise ValueError("pose coordinates, heading, and timestamp must be finite")
        object.__setattr__(self, "heading_rad", normalize_heading(self.heading_rad))


@dataclass(frozen=True, slots=True)
class SimulatedCheckpointObservation:
    """Explicit simulation event, distinct from an OpenCV image detection."""

    tag_id: int
    timestamp_s: float
    node_id: str


class UnknownCheckpointError(ValueError):
    """Raised when a simulated observation references an unmapped tag."""


class DeadReckoner:
    """Midpoint-integrate forward wheel displacement and IMU yaw increments."""

    def __init__(self, initial_pose: PositionEstimate) -> None:
        self._pose = initial_pose

    @property
    def pose(self) -> PositionEstimate:
        """Return the current immutable pose estimate."""
        return self._pose

    def update(self, measurement: MotionMeasurement) -> PositionEstimate:
        """Integrate one strictly newer sensor sample using the midpoint rule."""
        values = (
            measurement.timestamp_s,
            measurement.wheel_displacement_m,
            measurement.imu_yaw_delta_rad,
        )
        if any(isinstance(value, bool) for value in values) or not all(
            math.isfinite(value) for value in values
        ):
            raise ValueError("measurement values must be finite")
        if measurement.timestamp_s < 0:
            raise ValueError("measurement timestamp must be nonnegative")
        if measurement.timestamp_s <= self._pose.timestamp_s:
            raise ValueError("measurement timestamp must increase strictly")

        midpoint_heading = normalize_heading(
            self._pose.heading_rad + measurement.imu_yaw_delta_rad / 2.0
        )
        x_m = self._pose.x_m + measurement.wheel_displacement_m * math.cos(
            midpoint_heading
        )
        y_m = self._pose.y_m + measurement.wheel_displacement_m * math.sin(
            midpoint_heading
        )
        self._pose = PositionEstimate(
            x_m=x_m,
            y_m=y_m,
            heading_rad=self._pose.heading_rad + measurement.imu_yaw_delta_rad,
            timestamp_s=measurement.timestamp_s,
        )
        return self._pose


def correct_to_checkpoint(
    pose: PositionEstimate,
    layout: AprilTagLayout,
    tag_id: int,
) -> PositionEstimate:
    """Snap estimated x/y to a known mapped tag while preserving heading/time."""
    checkpoint: AprilTagCheckpoint | None = layout.checkpoint_for(tag_id)
    if checkpoint is None:
        raise UnknownCheckpointError(f"Unknown AprilTag checkpoint ID: {tag_id}")
    return PositionEstimate(
        checkpoint.x_m,
        checkpoint.y_m,
        pose.heading_rad,
        pose.timestamp_s,
    )
