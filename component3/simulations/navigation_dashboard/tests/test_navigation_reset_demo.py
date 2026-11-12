"""Standalone navigation Reset Demo state and generation tests."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from component3.backend.navigation.apriltag import AprilTagDetection
from component3.backend.navigation.camera_scanner import (
    CameraScanner,
    DetectionConsensus,
)
from component3.simulations.navigation_dashboard.shared_session import (
    SessionConflictError,
    SharedNavigationSession,
)
from component3.simulations.navigation_dashboard.spatial_simulation import SpatialNavigationSimulation


class NavigationResetDemoTests(unittest.TestCase):
    def assert_idle(self, state: dict) -> None:
        self.assertEqual(state["status"], "idle")
        self.assertEqual(state["navigation_state"], "IDLE") if "navigation_state" in state else None
        self.assertFalse(state["running"])
        self.assertEqual(state["selected_product_ids"], [])
        self.assertEqual(state["shopping_session"]["items"], [])
        self.assertEqual(state["planned_route"], [])
        self.assertEqual(state["remaining_route"], [])
        self.assertEqual(state["route_revision"], 0)
        self.assertEqual(state["remaining_distance_m"], 0.0)
        self.assertEqual(state["detected_checkpoint_ids"], [])
        self.assertIsNone(state["last_confirmed_checkpoint"])
        self.assertIsNone(state["observed_checkpoint"])
        self.assertEqual(state["checkpoint_observation_history"], [])
        self.assertEqual(state["current_node_id"], state["planned_route"][0] if state["planned_route"] else "N0_0")
        self.assertEqual(state["recommendations"], [])

    def test_reset_from_idle(self) -> None:
        simulation = SpatialNavigationSimulation()
        self.assert_idle(simulation.reset_navigation_demo())

    def test_reset_with_populated_wishlist(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(("SIM-P-001", "SIM-P-002"))
        self.assert_idle(simulation.reset_navigation_demo())

    def test_reset_during_active_navigation(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(("SIM-P-001", "SIM-P-004"))
        simulation.start()
        simulation.step(3)
        state = simulation.reset_navigation_demo()
        self.assert_idle(state)
        self.assertEqual(state["ground_truth"], {"x_m": 1.0, "y_m": 1.0})
        self.assertEqual(state["travelled_ground_truth"], [])
        self.assertEqual(state["travelled_estimate"], [])

    def test_reset_after_checkpoint_confirmation(self) -> None:
        simulation = SpatialNavigationSimulation()
        before = simulation.snapshot()
        self.assertEqual(before["detected_checkpoint_ids"], [200])
        self.assertIsNotNone(before["last_confirmed_checkpoint"])
        self.assert_idle(simulation.reset_navigation_demo())

    def test_reset_during_mocked_camera_capture_releases_and_clears_consensus(self) -> None:
        started = threading.Event()

        class Capture:
            released = False

            def isOpened(self):
                return True

            def read(self):
                started.set()
                return True, object()

            def release(self):
                self.released = True

            def getBackendName(self):
                return "TEST"

        capture = Capture()

        class CV2:
            @staticmethod
            def VideoCapture(_index):
                return capture

        detection = AprilTagDetection(215, ((0.0, 0.0),) * 4)
        scanner = CameraScanner(required_frames=3, max_fps=60)
        with patch(
            "component3.backend.navigation.camera_scanner._load_aruco",
            return_value=(CV2, object()),
        ), patch(
            "component3.backend.navigation.camera_scanner.detect_apriltags_frame",
            return_value=(detection,),
        ):
            self.assertTrue(scanner.start(0)["scanning"])
            self.assertTrue(started.wait(1.0))
            reset = scanner.reset()
        self.assertTrue(capture.released)
        self.assertFalse(reset["scanning"])
        self.assertEqual(reset["consistent_frames"], 0)
        self.assertIsNone(reset["detected_tag_id"])
        self.assertEqual(reset["scan_events"], [])
        self.assertIsNone(scanner.consensus.candidate)

    def test_old_camera_observation_cannot_mutate_new_generation(self) -> None:
        shared = SharedNavigationSession(SpatialNavigationSimulation())
        old_generation = shared.session_generation
        shared.reset_demo()
        called = False

        def stale_mutation() -> dict:
            nonlocal called
            called = True
            return shared.simulation.observe_camera_detection(200, 1.0)

        revision = shared.state_revision
        accepted, state = shared.apply_external_mutation(old_generation, stale_mutation)
        self.assertFalse(accepted)
        self.assertFalse(called)
        self.assertEqual(state["state_revision"], revision)
        self.assert_idle(state)

    def test_old_route_command_cannot_update_new_generation(self) -> None:
        shared = SharedNavigationSession(SpatialNavigationSimulation())
        old_generation = shared.session_generation
        shared.reset_demo()
        called = False

        def stale_dispatch(_action: str, _payload: dict) -> dict:
            nonlocal called
            called = True
            return shared.simulation.start()

        with self.assertRaisesRegex(SessionConflictError, "Stale session generation"):
            shared.apply(
                {
                    "action": "start",
                    "client_id": "stale-route-client",
                    "command_id": "stale-route-command",
                    "session_generation": old_generation,
                },
                stale_dispatch,
            )
        self.assertFalse(called)
        self.assert_idle(shared.snapshot())

    def test_repeated_reset_is_idempotent(self) -> None:
        shared = SharedNavigationSession(SpatialNavigationSimulation())
        first = shared.reset_demo()
        second = shared.reset_demo()
        self.assert_idle(first)
        self.assert_idle(second)
        self.assertEqual(second["session_generation"], first["session_generation"] + 1)
        self.assertEqual(second["state_revision"], 0)

    def test_separate_recommendation_state_is_unchanged(self) -> None:
        recommendation = SpatialNavigationSimulation()
        before = recommendation.set_products(("SIM-P-001", "SIM-P-002"))
        offered = before["recommendations"]
        navigation = SpatialNavigationSimulation()
        navigation.reset_navigation_demo()
        after = recommendation.snapshot()
        self.assertEqual(after["shopping_session"], before["shopping_session"])
        self.assertEqual(after["recommendations"], offered)


class ExistingTemporalConfirmationTests(unittest.TestCase):
    def test_noisy_sequence_confirms_only_three_consecutive_215_observations(self) -> None:
        consensus = DetectionConsensus(required_frames=3)
        sequence = (215, 246, 216, 246, 215, 215, 215)
        confirmed = [consensus.update((tag_id,)) for tag_id in sequence]
        self.assertEqual([tag_id for tag_id in confirmed if tag_id is not None], [215])


if __name__ == "__main__":
    unittest.main()
