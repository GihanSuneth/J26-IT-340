"""Tests for sensor integration and the reproducible position simulation."""

from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from component3.backend.comp3_reco_navigation.navigation.apriltag import (
    AprilTagLayout,
)
from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    DeadReckoner,
    MotionMeasurement,
    PositionEstimate,
    UnknownCheckpointError,
    correct_to_checkpoint,
    normalize_heading,
)
from component3.backend.comp3_reco_navigation.navigation.position_tracking_simulation import (
    SimulationConfig,
    build_simulation_trace,
    calculate_metrics,
    run_scenario,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    load_store_graph,
)


COMPONENT_ROOT = Path(__file__).resolve().parents[3]


class DeadReckoningTests(unittest.TestCase):
    """Verify estimator math, input guards, and simulation behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the existing store graph and AprilTag mapping once."""
        graph = load_store_graph(COMPONENT_ROOT / "data/store_map/store_graph.json")
        with (COMPONENT_ROOT / "data/store_map/apriltag_layout.json").open(
            encoding="utf-8"
        ) as handle:
            layout_data = json.load(handle)
        cls.graph = graph
        cls.layout = AprilTagLayout.from_dict(layout_data, graph)
        cls.config = SimulationConfig()

    def test_straight_line_motion(self) -> None:
        """Integrate forward movement along the positive x-axis."""
        reckoner = DeadReckoner(PositionEstimate(0.0, 0.0, 0.0, 0.0))
        pose = reckoner.update(MotionMeasurement(1.0, 2.0, 0.0))
        self.assertAlmostEqual(pose.x_m, 2.0)
        self.assertAlmostEqual(pose.y_m, 0.0)

    def test_turning_and_forward_motion(self) -> None:
        """Integrate a stationary quarter turn followed by northward travel."""
        reckoner = DeadReckoner(PositionEstimate(1.0, 2.0, 0.0, 0.0))
        turned = reckoner.update(MotionMeasurement(0.5, 0.0, math.pi / 2))
        moved = reckoner.update(MotionMeasurement(1.0, 3.0, 0.0))
        self.assertAlmostEqual(turned.x_m, 1.0)
        self.assertAlmostEqual(turned.y_m, 2.0)
        self.assertAlmostEqual(moved.x_m, 1.0, places=12)
        self.assertAlmostEqual(moved.y_m, 5.0, places=12)

    def test_stationary_measurement(self) -> None:
        """Keep position unchanged for a stationary zero-yaw sample."""
        reckoner = DeadReckoner(PositionEstimate(2.0, 4.0, 1.0, 0.0))
        pose = reckoner.update(MotionMeasurement(0.25, 0.0, 0.0))
        self.assertEqual((pose.x_m, pose.y_m), (2.0, 4.0))

    def test_heading_normalization(self) -> None:
        """Normalize initial and integrated headings to [-pi, pi)."""
        pose = PositionEstimate(0.0, 0.0, 5.0 * math.pi, 0.0)
        self.assertGreaterEqual(pose.heading_rad, -math.pi)
        self.assertLess(pose.heading_rad, math.pi)
        self.assertEqual(normalize_heading(math.pi), -math.pi)
        self.assertEqual(normalize_heading(-math.pi), -math.pi)

    def test_zero_distance_turn(self) -> None:
        """Allow heading updates when wheel displacement is zero."""
        reckoner = DeadReckoner(PositionEstimate(1.0, 1.0, 0.0, 0.0))
        pose = reckoner.update(MotionMeasurement(1.0, 0.0, math.pi / 3))
        self.assertEqual((pose.x_m, pose.y_m), (1.0, 1.0))
        self.assertAlmostEqual(pose.heading_rad, math.pi / 3)

    def test_invalid_measurement_values(self) -> None:
        """Reject non-finite displacement and yaw values."""
        reckoner = DeadReckoner(PositionEstimate(0.0, 0.0, 0.0, 0.0))
        for measurement in (
            MotionMeasurement(1.0, math.nan, 0.0),
            MotionMeasurement(1.0, 0.0, math.inf),
            MotionMeasurement(math.inf, 0.0, 0.0),
        ):
            with self.subTest(measurement=measurement):
                with self.assertRaises(ValueError):
                    reckoner.update(measurement)

    def test_invalid_timestamps(self) -> None:
        """Reject repeated and backwards timestamps."""
        reckoner = DeadReckoner(PositionEstimate(0.0, 0.0, 0.0, 1.0))
        for timestamp in (1.0, 0.5, -0.1, math.nan, math.inf):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(ValueError):
                    reckoner.update(MotionMeasurement(timestamp, 0.0, 0.0))

    def test_repeated_simulation_is_deterministic(self) -> None:
        """Reproduce ground truth, sensor streams, and events for a fixed seed."""
        first = build_simulation_trace(self.graph, self.layout, self.config)
        second = build_simulation_trace(self.graph, self.layout, self.config)
        self.assertEqual(first, second)

    def test_simulated_checkpoint_correction(self) -> None:
        """Correct x/y to the known checkpoint and preserve heading and time."""
        checkpoint = self.layout.checkpoint_for(110)
        self.assertIsNotNone(checkpoint)
        estimate = PositionEstimate(100.0, -20.0, 0.7, 12.0)
        corrected = correct_to_checkpoint(estimate, self.layout, 110)
        self.assertEqual((corrected.x_m, corrected.y_m), (checkpoint.x_m, checkpoint.y_m))
        self.assertEqual(corrected.heading_rad, estimate.heading_rad)
        self.assertEqual(corrected.timestamp_s, estimate.timestamp_s)

    def test_unknown_checkpoint_is_rejected(self) -> None:
        """Do not map a simulated unknown tag to a graph position."""
        with self.assertRaises(UnknownCheckpointError):
            correct_to_checkpoint(
                PositionEstimate(0.0, 0.0, 0.0, 1.0), self.layout, 999
            )

    def test_noisy_measurements_are_nonideal(self) -> None:
        """Seeded noise and bias produce position error along the route."""
        trace = build_simulation_trace(self.graph, self.layout, self.config)
        result = run_scenario(
            "noisy",
            trace.noisy_measurements,
            trace,
            self.layout,
            apply_checkpoint_corrections=False,
        )
        self.assertGreater(max(result.errors_m), 0.0)

    def test_no_correction_scenario_does_not_snap_at_checkpoints(self) -> None:
        """Known checkpoint arrivals do not alter an uncorrected estimate."""
        trace = build_simulation_trace(self.graph, self.layout, self.config)
        result = run_scenario(
            "no correction",
            trace.noisy_measurements,
            trace,
            self.layout,
            apply_checkpoint_corrections=False,
        )
        self.assertEqual(result.checkpoint_errors, ())

    def test_checkpointed_and_uncorrected_scenarios_share_measurements(self) -> None:
        """Compare correction strategies over the exact same noisy trajectory."""
        trace = build_simulation_trace(self.graph, self.layout, self.config)
        without = run_scenario(
            "without",
            trace.noisy_measurements,
            trace,
            self.layout,
            apply_checkpoint_corrections=False,
        )
        with_correction = run_scenario(
            "with",
            trace.noisy_measurements,
            trace,
            self.layout,
            apply_checkpoint_corrections=True,
        )
        self.assertEqual(without.estimates[1], with_correction.estimates[1])
        self.assertGreater(len(with_correction.checkpoint_errors), 0)
        self.assertEqual(len(without.estimates), len(with_correction.estimates))

    def test_checkpoint_correction_reduces_error_at_mapped_node(self) -> None:
        """A simulated map snap has zero node-position error at arrival."""
        trace = build_simulation_trace(self.graph, self.layout, self.config)
        corrected = run_scenario(
            "corrected",
            trace.noisy_measurements,
            trace,
            self.layout,
            apply_checkpoint_corrections=True,
        )
        self.assertTrue(corrected.checkpoint_errors)
        for _, before, after in corrected.checkpoint_errors:
            self.assertGreaterEqual(before, 0.0)
            self.assertAlmostEqual(after, 0.0, places=9)

    def test_estimator_does_not_receive_ground_truth(self) -> None:
        """The sensor input and estimator state expose no truth coordinates."""
        measurement = MotionMeasurement(1.0, 0.25, 0.0)
        reckoner = DeadReckoner(PositionEstimate(0.0, 0.0, 0.0, 0.0))
        self.assertEqual(
            set(measurement.__dataclass_fields__),
            {"timestamp_s", "wheel_displacement_m", "imu_yaw_delta_rad"},
        )
        self.assertFalse(hasattr(reckoner, "ground_truth"))
        self.assertFalse(hasattr(reckoner, "ground_truth_x_m"))

    def test_ideal_measurements_have_zero_error(self) -> None:
        """The zero-noise scenario exactly follows its generated path."""
        trace = build_simulation_trace(self.graph, self.layout, self.config)
        ideal = run_scenario(
            "ideal",
            trace.ideal_measurements,
            trace,
            self.layout,
            apply_checkpoint_corrections=False,
        )
        self.assertLess(max(ideal.errors_m), 1e-9)
        metrics = calculate_metrics(ideal, "zero-noise")
        self.assertLess(metrics.rmse_position_error_m, 1e-9)


if __name__ == "__main__":
    unittest.main()
