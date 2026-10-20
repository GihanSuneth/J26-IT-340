"""Phase 7G acceptance tests for playback, decisions, workflow and tag coverage."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from component3.simulations.navigation_dashboard.shared_session import SharedNavigationSession
from component3.simulations.navigation_dashboard.spatial_simulation import SpatialNavigationSimulation
from component3.simulations.navigation_dashboard.workflow import NavigationState, contract


ROOT = Path(__file__).resolve().parents[4]


class BackendAutoplayTests(unittest.TestCase):
    def test_reads_are_pure_and_backend_tick_is_single_owner(self) -> None:
        shared = SharedNavigationSession()
        shared.simulation.set_products(["SIM-P-001"])
        shared.simulation.start()
        shared.set_autoplay(True, 2.0)
        before = shared.snapshot()["simulation_time_s"]
        self.assertEqual(shared.snapshot()["simulation_time_s"], before)
        self.assertTrue(shared.autoplay_tick(10**9))
        after = shared.snapshot()
        self.assertGreater(after["simulation_time_s"], before)
        self.assertFalse(shared.autoplay_tick(10**9))
        self.assertEqual(after["simulation_time_s"], shared.snapshot()["simulation_time_s"])
        self.assertFalse(after["simulation_clock"]["read_requests_advance_time"])


class ProductDecisionTests(unittest.TestCase):
    def _arrive(self, simulation: SpatialNavigationSimulation) -> None:
        for _ in range(1000):
            simulation.step()
            if simulation.status == "awaiting_product_confirmation":
                return
        self.fail("product arrival was not reached")

    def test_keep_for_later_leaves_shelf_before_reoffer(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-001"])
        simulation.start()
        self._arrive(simulation)
        node = simulation.current_node_id
        simulation.skip_product("keep_for_later", simulation.shopping_session.revision)
        self.assertEqual(simulation.status, "navigating")
        self.assertEqual(simulation.shopping_session.remaining_product_ids, ("SIM-P-001",))
        left_shelf = False
        for _ in range(1000):
            simulation.step()
            left_shelf |= simulation.current_node_id != node or simulation._edge_target is not None
            if simulation.status == "awaiting_product_confirmation":
                break
        self.assertTrue(left_shelf)
        self.assertEqual(simulation.status, "awaiting_product_confirmation")
        self.assertTrue(any(event["event_type"] == "product_skipped_deferred" for event in simulation.snapshot()["events"]))

    def test_remove_remaining_does_not_fabricate_collection(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-001"])
        simulation.start()
        self._arrive(simulation)
        simulation.skip_product("remove_remaining", simulation.shopping_session.revision)
        self.assertEqual(simulation.shopping_session.remaining_product_ids, ())
        self.assertEqual(simulation.shopping_session.collected_product_ids, ())
        self.assertFalse(any(event["event_type"] == "product_collected" for event in simulation.snapshot()["events"]))


class DenseLayoutTests(unittest.TestCase):
    def test_layout_is_unique_retained_and_covers_every_edge(self) -> None:
        path = ROOT / "component3/data/demo_store/v2/dense_apriltag_layout.json"
        layout = json.loads(path.read_text(encoding="utf-8"))
        ids = [tag["tag_id"] for tag in layout["tags"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({200, 201, 202}.issubset(ids))
        self.assertTrue(layout["coverage_report"]["all_edges_pass"])
        self.assertLessEqual(layout["coverage_report"]["observed_maximum_spacing_m"], 2.0)
        all_manifest = json.loads((
            ROOT / "component3/data/apriltag_cards/generated_dense_all/manifest.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(set(all_manifest["tag_ids"]), set(ids))
        self.assertTrue(all_manifest["decode_verified"])
        placement = ROOT / "component3/data/apriltag_cards/generated_dense_all/placement_sheet.csv"
        self.assertEqual(len(placement.read_text(encoding="utf-8").splitlines()), len(ids) + 1)

    def test_public_workflow_contract_contains_all_required_states(self) -> None:
        self.assertEqual(set(contract()["states"]), {state.value for state in NavigationState})


class LocalizationHealthTests(unittest.TestCase):
    def test_health_candidates_are_graph_derived_and_camera_loss_is_explicit(self) -> None:
        simulation = SpatialNavigationSimulation()
        health = simulation.localization_health({"connection": "stopped", "scanning": False})
        self.assertEqual(health["status"], "CONFIRMED")
        self.assertTrue(health["candidate_checkpoints"])
        self.assertTrue(all("graph_distance_m" in item for item in health["candidate_checkpoints"]))
        self.assertFalse(health["visibility_claimed"])
        simulation.start_camera_evaluation()
        unavailable = simulation.localization_health({"connection": "stopped", "scanning": False})
        self.assertEqual(unavailable["status"], "CAMERA_UNAVAILABLE")
        self.assertTrue(unavailable["warning"])
        simulation.acknowledge_localization_warning(
            unavailable["warning_key"], {"connection": "stopped", "scanning": False}
        )
        acknowledged = simulation.localization_health({"connection": "stopped", "scanning": False})
        self.assertTrue(acknowledged["acknowledged"])

    def test_missing_observation_becomes_overdue_without_sequential_id_assumption(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.start()
        simulation._distance_since_checkpoint_m = 6.1
        health = simulation.localization_health({"connection": "running", "scanning": True})
        self.assertEqual(health["status"], "SCAN_OVERDUE")
        self.assertTrue(health["warning"])
        self.assertGreater(len(health["candidate_checkpoints"]), 1)
        self.assertNotIn("next sequential", health["explanation"].lower())

    def test_dense_camera_acceptance_moves_only_estimate_and_replans(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.start_camera_evaluation()
        simulation.camera_reconnected()
        simulation.observe_camera_detection(200, 0.0)
        truth = simulation.snapshot()["ground_truth"]
        before_revision = simulation.snapshot()["route_revision"]
        accepted = simulation.observe_camera_detection(231, 0.5)
        self.assertTrue(accepted["observed_checkpoint"]["accepted"])
        self.assertEqual(accepted["last_confirmed_checkpoint"]["checkpoint_id"], 231)
        self.assertEqual(accepted["ground_truth"], truth)
        self.assertNotEqual(accepted["estimate"], truth)
        self.assertGreater(accepted["route_revision"], before_revision)
        estimate = accepted["estimate"]
        rejected = simulation.observe_camera_detection(217, 0.75)
        self.assertFalse(rejected["observed_checkpoint"]["accepted"])
        self.assertEqual(rejected["observed_checkpoint"]["reason"], "implausible_position_jump")
        self.assertEqual(rejected["estimate"], estimate)
        self.assertEqual(rejected["last_confirmed_checkpoint"]["checkpoint_id"], 231)
        health = simulation.localization_health({"connection": "running", "scanning": True})
        self.assertEqual(health["status"], "OBSERVATION_REJECTED")


if __name__ == "__main__":
    unittest.main()
