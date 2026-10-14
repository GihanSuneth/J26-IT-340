"""Generate deterministic synthetic encoder and IMU samples for simulation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    MotionMeasurement,
)


@dataclass(frozen=True, slots=True)
class SensorConfig:
    """Explicit simulated sensor noise and bias settings."""

    seed: int = 6042
    encoder_noise_std_m: float = 0.004
    encoder_bias_fraction: float = 0.008
    imu_yaw_noise_std_rad: float = math.radians(0.35)
    imu_yaw_bias_rad_per_sample: float = math.radians(0.08)

    def __post_init__(self) -> None:
        values = (
            self.encoder_noise_std_m,
            self.encoder_bias_fraction,
            self.imu_yaw_noise_std_rad,
            self.imu_yaw_bias_rad_per_sample,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in values
        ):
            raise ValueError("sensor noise and bias values must be finite and nonnegative")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("sensor seed must be an integer")


class SimulatedSensorGenerator:
    """Produce sensor-only motion measurements with a reproducible RNG."""

    def __init__(self, config: SensorConfig) -> None:
        """Initialize a seeded sensor stream."""
        self.config = config
        self._random = random.Random(config.seed)

    def measurement(
        self,
        timestamp_s: float,
        true_displacement_m: float,
        true_yaw_delta_rad: float,
    ) -> MotionMeasurement:
        """Add configured bias and seeded noise without returning truth values."""
        values = (timestamp_s, true_displacement_m, true_yaw_delta_rad)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("simulated sensor inputs must be finite numbers")
        if timestamp_s <= 0 or true_displacement_m < 0:
            raise ValueError("sensor timestamp must be positive and displacement nonnegative")
        measured_wheel = (
            true_displacement_m * (1.0 + self.config.encoder_bias_fraction)
            + self._random.gauss(0.0, self.config.encoder_noise_std_m)
        )
        measured_yaw = (
            true_yaw_delta_rad
            + self.config.imu_yaw_bias_rad_per_sample
            + self._random.gauss(0.0, self.config.imu_yaw_noise_std_rad)
        )
        return MotionMeasurement(
            timestamp_s=timestamp_s,
            wheel_displacement_m=measured_wheel,
            imu_yaw_delta_rad=measured_yaw,
        )
