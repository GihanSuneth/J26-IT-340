"""Regression tests for Phase 7A structured automatic customer guidance."""

from __future__ import annotations

import json
import math
import unittest

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import PositionEstimate
from component3.simulations.navigation_dashboard.checkpoint_observations import (
    CheckpointObservation,
    CheckpointObservationProcessor,
)
from component3.simulations.navigation_dashboard.demo_store import (
    DEFAULT_DEMO_MAP_PATH,
    DemoMapValidationError,
    build_demo_store,
    load_demo_store,
)
from component3.simulations.navigation_dashboard.guidance import (
    GuidanceEngine,
    ProductArrivalMonitor,
    classify_turn,
    product_shelf_side,
    resolve_product_location,
)
from component3.simulations.navigation_dashboard.spatial_simulation import (
    SpatialNavigationSimulation,
)


class ProductMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = load_demo_store()
        self.shelves = {item["shelf_id"]: item for item in self.store.data["shelves"]}

    def test_all_six_products_have_resolved_shelf_metadata(self) -> None:
        locations = [
            resolve_product_location(product, self.shelves, self.store.graph)
            for product in self.store.data["products"]
        ]
        self.assertEqual(len(locations), 6)
        self.assertTrue(all(item.available for item in locations))
        self.assertTrue(all(item.shelf_level and item.shelf_bay for item in locations))

    def test_missing_shelf_returns_explicit_unavailable_state(self) -> None:
        product = dict(self.store.data["products"][0], shelf_id="missing")
        result = resolve_product_location(product, self.shelves, self.store.graph)
        self.assertFalse(result.available)
        self.assertEqual(result.unavailable_reason, "missing_shelf")

    def test_invalid_level_is_rejected_by_map_validation(self) -> None:
        raw = json.loads(DEFAULT_DEMO_MAP_PATH.read_text(encoding="utf-8"))
        raw["products"][0]["shelf_level"] = 5
        with self.assertRaisesRegex(DemoMapValidationError, "invalid shelf level"):
            build_demo_store(raw)

    def test_unreachable_pickup_is_explicit(self) -> None:
        product = dict(self.store.data["products"][0], pickup_node="missing", pickup_node_id="missing")
        result = resolve_product_location(product, self.shelves, self.store.graph)
        self.assertEqual(result.unavailable_reason, "unreachable_pickup")


class GeometryGuidanceTests(unittest.TestCase):
    def test_turn_classifier_covers_all_maneuvers(self) -> None:
        self.assertEqual(classify_turn(0, 0), "STRAIGHT")
        self.assertEqual(classify_turn(0, math.pi / 2), "TURN_LEFT")
        self.assertEqual(classify_turn(0, -math.pi / 2), "TURN_RIGHT")
        self.assertEqual(classify_turn(0, math.pi), "U_TURN")

    def test_shelf_side_flips_for_opposite_approach(self) -> None:
        self.assertEqual(product_shelf_side(0, (0, 0), (0, 1)), "left")
        self.assertEqual(product_shelf_side(math.pi, (0, 0), (0, 1)), "right")

    def test_shelf_side_is_unavailable_for_ambiguous_orientation(self) -> None:
        self.assertIsNone(product_shelf_side(0, (0, 0), (1, 0)))

    def test_duplicate_guidance_transition_is_suppressed(self) -> None:
        engine = GuidanceEngine(load_demo_store().graph)
        first, first_new = engine.publish("STRAIGHT", "Continue.", timestamp=0, target_node="N0_1")
        second, second_new = engine.publish("STRAIGHT", "Continue.", timestamp=1, target_node="N0_1", distance_to_maneuver_m=2)
        self.assertTrue(first_new)
        self.assertFalse(second_new)
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(len(engine.events), 1)

    def test_route_revision_refreshes_instruction_identity(self) -> None:
        engine = GuidanceEngine(load_demo_store().graph)
        before, _ = engine.publish("STRAIGHT", "Continue.", timestamp=0, target_node="N0_1")
        engine.route_changed()
        after, is_new = engine.publish("STRAIGHT", "Continue.", timestamp=1, target_node="N0_1")
        self.assertTrue(is_new)
        self.assertNotEqual(before.event_id, after.event_id)


class CheckpointObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        store = load_demo_store()
        self.processor = CheckpointObservationProcessor(store.checkpoint_layout, store.data["map_id"])
        self.pose = PositionEstimate(2, 2, 0, 0)

    def observation(self, tag: int, time: float = 1, confidence: float = 1) -> CheckpointObservation:
        return CheckpointObservation(tag, time, "synthetic_test", "comp3-synthetic-supermarket-demo-v1", confidence)

    def test_valid_observation_corrects_to_mapped_checkpoint(self) -> None:
        result = self.processor.process(self.observation(200), self.pose, expected_tag_id=200)
        self.assertTrue(result.accepted)
        self.assertEqual((result.corrected_pose.x_m, result.corrected_pose.y_m), (1, 1))

    def test_unknown_duplicate_and_unexpected_are_rejected(self) -> None:
        self.assertEqual(self.processor.process(self.observation(999), self.pose, expected_tag_id=200).reason, "unknown_tag")
        self.assertTrue(self.processor.process(self.observation(200), self.pose, expected_tag_id=200).accepted)
        self.assertEqual(self.processor.process(self.observation(200, 2), self.pose, expected_tag_id=201).reason, "duplicate_observation")
        fresh = CheckpointObservationProcessor(load_demo_store().checkpoint_layout, "comp3-synthetic-supermarket-demo-v1")
        self.assertEqual(fresh.process(self.observation(201), self.pose, expected_tag_id=200).reason, "unexpected_checkpoint")

    def test_low_confidence_and_old_timestamp_are_rejected(self) -> None:
        self.assertEqual(self.processor.process(self.observation(200, confidence=.1), self.pose, expected_tag_id=200).reason, "confidence_below_threshold")
        self.assertTrue(self.processor.process(self.observation(200, 2), self.pose, expected_tag_id=200).accepted)
        self.assertEqual(self.processor.process(self.observation(201, 1), self.pose, expected_tag_id=201).reason, "out_of_order_observation")

    def test_missing_observation_is_rejected_without_correction(self) -> None:
        result = self.processor.process(None, self.pose, expected_tag_id=200)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "missing_observation")
        self.assertIsNone(result.corrected_pose)

    def test_far_away_observation_cannot_relocate_estimate(self) -> None:
        far_pose = PositionEstimate(19, 13, 0, 0)
        result = self.processor.process(self.observation(200), far_pose, expected_tag_id=200)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "correction_exceeds_limit")
        self.assertIsNone(result.corrected_pose)


class ArrivalAndIntegrationTests(unittest.TestCase):
    def test_arrival_needs_stable_estimates_and_rejects_uncertainty(self) -> None:
        monitor = ProductArrivalMonitor(arrival_radius_m=1, confirmations=2, max_uncertainty_m=.5)
        first = monitor.update(target_product_id="p", estimated_position_m=(.5, 0), pickup_coordinate_m=(0, 0), localization_uncertainty_m=.1)
        second = monitor.update(target_product_id="p", estimated_position_m=(.4, 0), pickup_coordinate_m=(0, 0), localization_uncertainty_m=.1)
        uncertain = monitor.update(target_product_id="q", estimated_position_m=(0, 0), pickup_coordinate_m=(0, 0), localization_uncertainty_m=.8)
        self.assertFalse(first.arrived)
        self.assertTrue(second.arrived)
        self.assertTrue(uncertain.localization_uncertain)
        self.assertFalse(uncertain.arrived)

    def test_guided_run_has_structured_customer_sequence(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.start_guided_demo()
        for _ in range(2500):
            if simulation.status == "complete":
                break
            simulation.step()
        snapshot = simulation.snapshot()
        types = [event["instruction_type"] for event in snapshot["guidance_events"]]
        required = {"START", "STRAIGHT", "TURN_LEFT", "TURN_RIGHT", "U_TURN", "CHECKPOINT_CONFIRMED", "PRODUCT_REACHED", "PICKUP_CONFIRMED", "REROUTING", "ARRIVED_CHECKOUT"}
        self.assertEqual(snapshot["status"], "complete")
        self.assertTrue(required.issubset(types))
        self.assertEqual(snapshot["collected_product_ids"], ["SIM-P-001", "SIM-P-006"])
        self.assertEqual(snapshot["detected_checkpoint_ids"], [200, 201, 202])
        self.assertEqual(snapshot["reroute_count"], 1)

    def test_manual_mode_does_not_auto_confirm_pickup(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-001"])
        simulation.start()
        for _ in range(1000):
            if simulation.status == "awaiting_product_confirmation":
                break
            simulation.step()
        self.assertEqual(simulation.status, "awaiting_product_confirmation")
        self.assertEqual(simulation.snapshot()["collected_product_ids"], [])

    def test_duplicate_pickup_confirmation_is_blocked(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-001"])
        simulation.start()
        for _ in range(1000):
            if simulation.status == "awaiting_product_confirmation":
                break
            simulation.step()
        simulation.confirm_product()
        with self.assertRaisesRegex(ValueError, "No product"):
            simulation.confirm_product()

    def test_repeated_guided_runs_are_deterministic(self) -> None:
        outputs = []
        for _ in range(2):
            simulation = SpatialNavigationSimulation()
            simulation.start_guided_demo()
            for _ in range(2500):
                if simulation.status == "complete":
                    break
                simulation.step()
            outputs.append((simulation.snapshot()["events"], simulation.snapshot()["guidance_events"]))
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
