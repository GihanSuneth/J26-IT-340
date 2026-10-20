"""Adaptive mapped-checkpoint plausibility and correction tests."""

from __future__ import annotations

import unittest

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import PositionEstimate
from component3.backend.comp3_reco_navigation.navigation.route_anchor import node_route_anchor
from component3.simulations.navigation_dashboard.checkpoint_observations import (
    CheckpointObservation,
    CheckpointObservationProcessor,
    CheckpointPlausibilityContext,
)
from component3.simulations.navigation_dashboard.demo_store import load_demo_store


class AdaptiveCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = load_demo_store()
        self.processor = CheckpointObservationProcessor(
            self.store.checkpoint_layout, self.store.data["map_id"]
        )

    def observation(
        self, tag_id: int, timestamp_s: float, *, source: str = "adaptive_evaluation"
    ) -> CheckpointObservation:
        return CheckpointObservation(
            tag_id, timestamp_s, source, self.store.data["map_id"], confidence=1.0
        )

    def context(
        self, node_id: str, *, last: str | None = "N0_0", camera_available: bool = True
    ) -> CheckpointPlausibilityContext:
        return CheckpointPlausibilityContext(
            graph=self.store.graph,
            estimated_anchor=node_route_anchor(self.store.graph, node_id),
            position_uncertainty_m=0.2,
            maximum_speed_m_s=1.6,
            distance_tolerance_m=1.0,
            last_verified_checkpoint_node_id=last,
            camera_available=camera_available,
        )

    def test_unexpected_but_reachable_mapped_checkpoint_is_accepted(self) -> None:
        node = self.store.graph.node("N2_3")
        result = self.processor.process(
            self.observation(201, 20.0),
            PositionEstimate(node.x_m, node.y_m, 0.0, 20.0),
            expected_tag_id=202,
            allow_unexpected_mapped=True,
            plausibility=self.context("N2_3"),
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason, "accepted_unexpected_plausible")
        self.assertEqual(
            result.classification, "unexpected_but_plausible_mapped_checkpoint"
        )

    def test_spatially_implausible_mapped_checkpoint_does_not_correct(self) -> None:
        node = self.store.graph.node("N0_0")
        pose = PositionEstimate(node.x_m, node.y_m, 0.0, 1.0)
        result = self.processor.process(
            self.observation(202, 1.0), pose, expected_tag_id=201,
            allow_unexpected_mapped=True, plausibility=self.context("N0_0"),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "spatially_implausible_observation")
        self.assertIsNone(result.corrected_pose)
        self.assertGreater(
            result.graph_distance_from_last_checkpoint_m,
            result.reachable_distance_limit_m,
        )

    def test_duplicate_and_stale_observations_are_classified(self) -> None:
        entrance = self.store.graph.node("N0_0")
        pose = PositionEstimate(entrance.x_m, entrance.y_m, 0.0, 2.0)
        first = self.processor.process(
            self.observation(200, 2.0), pose, expected_tag_id=200,
            allow_unexpected_mapped=True, plausibility=self.context("N0_0", last=None),
        )
        self.assertTrue(first.accepted)
        duplicate = self.processor.process(
            self.observation(200, 3.0), pose, expected_tag_id=201,
            allow_unexpected_mapped=True, plausibility=self.context("N0_0"),
        )
        self.assertEqual(duplicate.classification, "duplicate")
        stale = self.processor.process(
            self.observation(201, 1.0), pose, expected_tag_id=201,
            allow_unexpected_mapped=True, plausibility=self.context("N0_0"),
        )
        self.assertEqual(stale.reason, "stale_observation")

    def test_unknown_map_source_and_camera_availability_are_distinct(self) -> None:
        entrance = self.store.graph.node("N0_0")
        pose = PositionEstimate(entrance.x_m, entrance.y_m, 0.0, 1.0)
        unknown = self.processor.process(
            self.observation(999, 1.0), pose, expected_tag_id=200,
            allow_unexpected_mapped=True, plausibility=self.context("N0_0"),
        )
        self.assertEqual(unknown.classification, "unknown_marker")
        wrong_map = CheckpointObservation(
            200, 1.0, "adaptive_evaluation", "wrong-map", confidence=1.0
        )
        result = self.processor.process(
            wrong_map, pose, expected_tag_id=200, allow_unexpected_mapped=True,
            plausibility=self.context("N0_0"),
        )
        self.assertEqual(result.classification, "map_version_mismatch")
        invalid_source = self.processor.process(
            self.observation(200, 1.0, source="invented_source"), pose,
            expected_tag_id=200, allow_unexpected_mapped=True,
            plausibility=self.context("N0_0"),
        )
        self.assertEqual(invalid_source.reason, "invalid_detection_source")
        camera_unavailable = self.processor.process(
            self.observation(200, 1.0, source="mac_camera_opencv"), pose,
            expected_tag_id=200, allow_unexpected_mapped=True,
            plausibility=self.context("N0_0", camera_available=False),
        )
        self.assertEqual(camera_unavailable.reason, "camera_unavailable")


if __name__ == "__main__":
    unittest.main()
