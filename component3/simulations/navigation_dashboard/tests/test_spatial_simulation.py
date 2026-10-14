"""Test synthetic store geometry, aisle navigation, products, and spatial API."""

from __future__ import annotations

import copy
import json
from http.server import ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from component3.simulations.navigation_dashboard.demo_store import (
    DEFAULT_DEMO_MAP_PATH,
    DemoMapValidationError,
    build_demo_store,
    load_demo_store,
)
from component3.simulations.navigation_dashboard.dashboard import make_handler
from component3.simulations.navigation_dashboard.spatial_simulation import (
    SpatialNavigationSimulation,
    heading_between,
    turn_instruction,
)


def advance_until(simulation: SpatialNavigationSimulation, status: str) -> None:
    """Advance by fixed samples until a status is reached or fail the test."""
    for _ in range(2500):
        if simulation.status == status:
            return
        simulation.step()
    raise AssertionError(f"Spatial simulation did not reach {status!r}")


def run_guided_demo(simulation: SpatialNavigationSimulation) -> dict[str, object]:
    """Run the server-owned guided state machine to checkout."""
    simulation.start_guided_demo()
    for _ in range(2500):
        snapshot = simulation.snapshot()
        if snapshot["status"] == "complete":
            return snapshot
        simulation.step()
    raise AssertionError("Guided demo did not reach checkout")


class SyntheticMapTests(unittest.TestCase):
    """Validate the synthetic layout independently of the research graph."""

    def test_map_is_versioned_and_does_not_load_research_store_graph(self) -> None:
        """Load a separate 30-node graph with explicit synthetic disclosure."""
        store = load_demo_store()
        self.assertEqual(store.data["map_id"], "comp3-synthetic-supermarket-demo-v1")
        self.assertEqual(store.data["data_classification"], "synthetic_demonstration_only")
        self.assertEqual(len(store.graph.node_ids), 30)
        self.assertEqual(len(store.data["shelves"]), 6)
        self.assertEqual(len(store.checkpoint_layout.tag_ids), 3)

    def test_every_route_edge_is_axis_aligned_walkable_and_avoids_shelves(self) -> None:
        """Verify edge segments stay in lane centerlines, outside shelf bounds."""
        store = load_demo_store()
        for edge in store.graph.edges:
            start, end = store.graph.node(edge.source), store.graph.node(edge.target)
            self.assertTrue(
                start.x_m == end.x_m or start.y_m == end.y_m,
                f"diagonal edge {edge.source}-{edge.target}",
            )
            for shelf in store.data["shelves"]:
                left, bottom, right, top = shelf["bounds_m"]
                crosses_shelf = (
                    start.y_m == end.y_m
                    and bottom < start.y_m < top
                    and max(min(start.x_m, end.x_m), left)
                    < min(max(start.x_m, end.x_m), right)
                ) or (
                    start.x_m == end.x_m
                    and left < start.x_m < right
                    and max(min(start.y_m, end.y_m), bottom)
                    < min(max(start.y_m, end.y_m), top)
                )
                self.assertFalse(crosses_shelf, f"{edge.source}-{edge.target} hits {shelf['shelf_id']}")

    def test_shelf_pickups_are_accessible_graph_nodes(self) -> None:
        """Require every synthetic product pickup to map to a safe aisle node."""
        store = load_demo_store()
        shelves = {shelf["shelf_id"]: shelf for shelf in store.data["shelves"]}
        for product in store.data["products"]:
            node = store.graph.node(product["pickup_node_id"])
            self.assertEqual(shelves[product["shelf_id"]]["pickup_node_id"], node.node_id)
            left, bottom, right, top = shelves[product["shelf_id"]]["bounds_m"]
            self.assertFalse(left < node.x_m < right and bottom < node.y_m < top)

    def test_invalid_shelf_lane_overlap_is_rejected(self) -> None:
        """Reject invalid geometry before creating a graph for navigation."""
        raw = json.loads(DEFAULT_DEMO_MAP_PATH.read_text(encoding="utf-8"))
        invalid = copy.deepcopy(raw)
        invalid["shelves"][0]["bounds_m"] = [4.6, 3.8, 5.4, 5.0]
        with self.assertRaisesRegex(DemoMapValidationError, "overlaps a horizontal"):
            build_demo_store(invalid)


class SpatialNavigationTests(unittest.TestCase):
    """Exercise turn guidance, checkpoints, products, and safe rerouting."""

    def test_heading_and_relative_turn_instructions(self) -> None:
        """Derive cardinal headings and four relative maneuver classes."""
        import math

        self.assertAlmostEqual(heading_between((0.0, 0.0), (1.0, 0.0)), 0.0)
        self.assertAlmostEqual(heading_between((0.0, 0.0), (0.0, 1.0)), math.pi / 2)
        self.assertEqual(turn_instruction(0.0, 0.0), "Continue straight")
        self.assertEqual(turn_instruction(0.0, math.pi / 2), "Turn left")
        self.assertEqual(turn_instruction(0.0, -math.pi / 2), "Turn right")
        self.assertEqual(turn_instruction(0.0, math.pi), "Make a U-turn")

    def test_guidance_is_derived_from_selected_route_and_has_maneuver_distance(self) -> None:
        """Generate changing route guidance from geometry and product target."""
        simulation = SpatialNavigationSimulation()
        initial = simulation.snapshot()
        self.assertEqual(initial["guidance"]["maneuver"], "Turn left")
        self.assertEqual(initial["guidance"]["distance_to_maneuver_m"], 0.0)
        self.assertIn("Bananas", initial["guidance"]["instruction"])
        self.assertIn("DEMO-SHELF-", initial["guidance"]["instruction"])
        simulation.start()
        after_departure = simulation.step()
        self.assertGreater(after_departure["guidance"]["distance_to_maneuver_m"], 0)

    def test_checkpoint_sequence_is_route_specific_not_every_graph_node(self) -> None:
        """Expose only configured checkpoint mappings, beginning at the entrance."""
        simulation = SpatialNavigationSimulation()
        initial = simulation.snapshot()
        self.assertEqual(initial["last_confirmed_checkpoint"]["checkpoint_id"], 200)
        self.assertEqual(initial["next_checkpoint"]["checkpoint_id"], 201)
        self.assertEqual(
            set(initial["detected_checkpoint_ids"]).issubset(
                set(simulation.store.checkpoint_layout.tag_ids)
            ),
            True,
        )
        checkpoint_node = initial["next_checkpoint"]["node_id"]
        checkpoint_index = initial["planned_route"].index(checkpoint_node)
        expected_distance = sum(
            simulation.graph.edge_weight(
                initial["planned_route"][index],
                initial["planned_route"][index + 1],
            )
            for index in range(checkpoint_index)
        )
        self.assertAlmostEqual(
            initial["distance_to_checkpoint_m"], expected_distance
        )

    def test_product_collection_requires_explicit_confirmation(self) -> None:
        """Reach a mapped product point without collecting until user confirmation."""
        simulation = SpatialNavigationSimulation()
        simulation.start()
        advance_until(simulation, "awaiting_product_confirmation")
        arrived = simulation.snapshot()
        product = arrived["active_product"]
        self.assertEqual(product["pickup_node_id"], simulation.current_node_id)
        self.assertEqual(arrived["collected_product_ids"], [])
        self.assertEqual(len(arrived["remaining_products"]), 6)
        simulation.confirm_product()
        confirmed = simulation.snapshot()
        self.assertEqual(confirmed["collected_product_ids"], [product["demo_product_id"]])
        self.assertEqual(len(confirmed["remaining_products"]), 5)

    def test_checkout_completion_with_empty_product_selection(self) -> None:
        """Plan and navigate directly to checkout when no products are selected."""
        simulation = SpatialNavigationSimulation()
        simulation.set_products([])
        self.assertEqual(simulation.snapshot()["planned_route"][-1], "N4_5")
        simulation.start()
        advance_until(simulation, "complete")
        self.assertEqual(simulation.current_node_id, "N4_5")

    def test_confirmed_wrong_turn_reuses_route_manager_and_preserves_products(self) -> None:
        """Reroute only after detector confirmation over a valid wrong lane edge."""
        simulation = SpatialNavigationSimulation()
        original = simulation.snapshot()
        original_products = list(original["selected_product_ids"])
        simulation.start()
        simulation.wrong_turn()
        for _ in range(20):
            simulation.step()
            if simulation.snapshot()["reroute_count"]:
                break
        snapshot = simulation.snapshot()
        self.assertEqual(snapshot["reroute_count"], 1)
        wrong_turn = next(event for event in snapshot["events"] if event["event_type"] == "wrong_turn")
        source, target = wrong_turn["details"]["from_node"], wrong_turn["details"]["to_node"]
        self.assertIn(target, [node_id for node_id, _ in simulation.graph.neighbors(source)])
        self.assertEqual(set(snapshot["selected_product_ids"]), set(original_products))
        self.assertEqual(snapshot["planned_route"][-1], "N4_5")
        self.assertEqual(snapshot["previous_planned_route"], original["planned_route"])
        self.assertTrue(
            any(event["event_type"] == "reroute_success" for event in snapshot["events"])
        )

    def test_wrong_turn_waits_for_intersection_and_never_backtracks(self) -> None:
        """Skip corridor nodes and choose a branch other than the incoming edge."""
        simulation = SpatialNavigationSimulation(speed_m_s=1.6)
        simulation.set_products(["SIM-P-001"])
        simulation.start()
        advance_until(simulation, "awaiting_product_confirmation")
        simulation.confirm_product()
        route = simulation.snapshot()["planned_route"]
        simulation.wrong_turn()
        for _ in range(100):
            simulation.step()
            event = next(
                (
                    item
                    for item in reversed(simulation.snapshot()["events"])
                    if item["event_type"] == "wrong_turn"
                ),
                None,
            )
            if event is not None:
                break
        else:
            self.fail("Wrong turn did not reach an alternative lane intersection")
        source = event["details"]["from_node"]
        target = event["details"]["to_node"]
        self.assertGreaterEqual(len(simulation.graph.neighbors(source)), 3)
        self.assertIn(target, [node_id for node_id, _ in simulation.graph.neighbors(source)])
        source_index = route.index(source)
        self.assertNotEqual(target, route[source_index - 1])

    def test_wrong_turn_episode_does_not_trigger_duplicate_reroutes(self) -> None:
        """Suppress the same off-route episode while the trolley rejoins its new route."""
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-006"])
        simulation.configure_speed(1.6)
        simulation.start()
        simulation.wrong_turn()
        for _ in range(100):
            snapshot = simulation.step()
            if 201 in snapshot["detected_checkpoint_ids"]:
                break
        else:
            self.fail("Simulation did not reach the mapped central checkpoint")
        self.assertEqual(snapshot["reroute_count"], 1)
        self.assertEqual(
            sum(event["event_type"] == "reroute_success" for event in snapshot["events"]),
            1,
        )

    def test_wrong_turn_episode_stays_suppressed_through_checkout(self) -> None:
        """Require confirmed recovery between successive reroutes while finishing."""
        simulation = SpatialNavigationSimulation(speed_m_s=1.6)
        simulation.start()
        simulation.wrong_turn()
        for _ in range(5000):
            if simulation.status == "awaiting_product_confirmation":
                simulation.confirm_product()
            elif simulation.status == "complete":
                break
            else:
                simulation.step()
        snapshot = simulation.snapshot()
        self.assertEqual(snapshot["status"], "complete")
        self.assertEqual(snapshot["collected_product_ids"], snapshot["selected_product_ids"])
        reroutes = [
            event
            for event in snapshot["events"]
            if event["event_type"] == "reroute_success"
        ]
        recoveries = [
            event
            for event in snapshot["events"]
            if event["event_type"] == "deviation_recovered"
        ]
        self.assertEqual(snapshot["reroute_count"], len(reroutes))
        self.assertGreaterEqual(len(reroutes), 1)
        self.assertGreaterEqual(len(recoveries), len(reroutes) - 1)
        previous_event = None
        for event in snapshot["events"]:
            if event["event_type"] == "reroute_success":
                self.assertNotEqual(previous_event, "reroute_success")
                previous_event = "reroute_success"
            elif event["event_type"] == "deviation_recovered":
                self.assertEqual(previous_event, "reroute_success")
                previous_event = "deviation_recovered"

    def test_deterministic_replay_and_pause_resume_step_reset(self) -> None:
        """Keep seeded sample paths and events identical across reset and replay."""
        first = SpatialNavigationSimulation()
        first.start()
        first.wrong_turn()
        first.step(6)
        expected = first.snapshot()
        second = SpatialNavigationSimulation()
        second.start()
        second.wrong_turn()
        second.step(6)
        self.assertEqual(second.snapshot()["travelled_ground_truth"], expected["travelled_ground_truth"])
        self.assertEqual(second.snapshot()["events"], expected["events"])
        first.pause()
        paused_time = first.simulation_time_s
        first.step()
        self.assertGreater(first.simulation_time_s, paused_time)
        first.resume()
        first.reset()
        self.assertEqual(first.status, "ready")
        self.assertEqual(first.snapshot()["selected_product_ids"], expected["selected_product_ids"])

    def test_unknown_product_is_rejected_without_mutating_selection(self) -> None:
        """Reject invalid demo catalog IDs without replacing the active shopping list."""
        simulation = SpatialNavigationSimulation()
        selected = simulation.snapshot()["selected_product_ids"]
        with self.assertRaisesRegex(ValueError, "Unknown synthetic demo product"):
            simulation.set_products(["REAL-POS-RECORD"])
        self.assertEqual(simulation.snapshot()["selected_product_ids"], selected)


class GuidedSpatialDemoTests(unittest.TestCase):
    """Protect the one-click guided scenario and manual-mode isolation."""

    def test_guided_start_resets_and_selects_required_products(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-003"])
        started = simulation.start_guided_demo()
        self.assertTrue(started["running"])
        self.assertEqual(started["current_node_id"], "N0_0")
        self.assertEqual(started["selected_product_ids"], ["SIM-P-001", "SIM-P-006"])
        self.assertEqual(started["guided_demo"]["stage"], 1)
        self.assertEqual(started["guided_demo"]["seed"], 6042)

    def test_all_nine_stages_progress_in_order(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.start_guided_demo()
        stages = [1]
        for _ in range(2500):
            snapshot = simulation.step()
            stage = snapshot["guided_demo"]["stage"]
            if stage != stages[-1]:
                stages.append(stage)
            if snapshot["status"] == "complete":
                break
        self.assertEqual(stages, list(range(1, 10)))

    def test_automatic_pickups_are_labeled_and_not_duplicated(self) -> None:
        snapshot = run_guided_demo(SpatialNavigationSimulation())
        pickups = [
            event for event in snapshot["events"]
            if event["event_type"] == "product_collected"
        ]
        self.assertEqual(snapshot["collected_product_ids"], ["SIM-P-001", "SIM-P-006"])
        self.assertEqual(len(pickups), 2)
        self.assertEqual(
            [event["details"]["confirmation_mode"] for event in pickups],
            ["guided_demo_automated_simulated"] * 2,
        )

    def test_one_valid_wrong_turn_is_confirmed_and_rerouted(self) -> None:
        simulation = SpatialNavigationSimulation()
        snapshot = run_guided_demo(simulation)
        events = snapshot["events"]
        wrong_turns = [event for event in events if event["event_type"] == "wrong_turn"]
        deviations = [event for event in events if event["event_type"] == "deviation_confirmed"]
        reroutes = [event for event in events if event["event_type"] == "reroute_success"]
        self.assertEqual(len(wrong_turns), 1)
        source = wrong_turns[0]["details"]["from_node"]
        target = wrong_turns[0]["details"]["to_node"]
        self.assertIn(target, [node for node, _ in simulation.graph.neighbors(source)])
        self.assertEqual(len(deviations), 1)
        self.assertEqual(len(reroutes), 1)
        self.assertEqual(snapshot["reroute_count"], 1)
        self.assertTrue(reroutes[0]["details"]["previous_route_node_ids"])
        self.assertTrue(reroutes[0]["details"]["route_node_ids"])

    def test_checkpoints_progress_sequentially_and_checkout_finishes(self) -> None:
        snapshot = run_guided_demo(SpatialNavigationSimulation())
        self.assertEqual(snapshot["detected_checkpoint_ids"], [200, 201, 202])
        self.assertEqual(snapshot["current_node_id"], "N4_5")
        self.assertEqual(snapshot["status"], "complete")
        summary = snapshot["guided_demo"]["completion_summary"]
        self.assertEqual(summary["checkpoint_sequence"], [200, 201, 202])
        self.assertEqual(summary["reroute_count"], 1)

    def test_guided_pause_resume_and_reset_are_safe(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.start_guided_demo()
        simulation.step(2)
        before_pause = simulation.simulation_time_s
        self.assertEqual(simulation.pause()["status"], "paused")
        self.assertEqual(simulation.simulation_time_s, before_pause)
        self.assertEqual(simulation.resume()["status"], "navigating")
        reset = simulation.reset()
        self.assertEqual(reset["status"], "ready")
        self.assertFalse(reset["guided_demo"]["active"])
        self.assertEqual(reset["current_node_id"], "N0_0")

    def test_repeated_guided_runs_have_identical_events_and_paths(self) -> None:
        simulation = SpatialNavigationSimulation()
        first = run_guided_demo(simulation)
        second = run_guided_demo(simulation)
        self.assertEqual(second["events"], first["events"])
        self.assertEqual(second["travelled_ground_truth"], first["travelled_ground_truth"])
        self.assertEqual(second["travelled_estimate"], first["travelled_estimate"])

    def test_manual_mode_never_auto_confirms_or_injects_wrong_turn(self) -> None:
        simulation = SpatialNavigationSimulation()
        simulation.set_products(["SIM-P-001"])
        simulation.start()
        advance_until(simulation, "awaiting_product_confirmation")
        snapshot = simulation.snapshot()
        self.assertFalse(snapshot["guided_demo"]["active"])
        self.assertEqual(snapshot["collected_product_ids"], [])
        self.assertFalse(any(
            event["event_type"] == "wrong_turn" for event in snapshot["events"]
        ))

    def test_guided_event_order_is_deterministic_and_chronological(self) -> None:
        snapshot = run_guided_demo(SpatialNavigationSimulation())
        events = snapshot["events"]
        timestamps = [event["timestamp_s"] for event in events]
        self.assertEqual(timestamps, sorted(timestamps))
        event_types = [event["event_type"] for event in events]
        ordered = [
            "guided_demo_started", "pickup_reached", "product_collected",
            "wrong_turn", "deviation_confirmed", "reroute_success",
            "product_collected", "checkout_complete", "guided_demo_complete",
        ]
        cursor = -1
        for event_type in ordered:
            cursor = event_types.index(event_type, cursor + 1)


class SpatialApiTests(unittest.TestCase):
    """Exercise synthetic map/control API failure responses and recovery."""

    def setUp(self) -> None:
        """Start an isolated local server with one spatial simulation."""
        self.simulation = SpatialNavigationSimulation()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(spatial_simulation=self.simulation),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        """Stop the local listener and wait for its serving thread."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path: str, payload: dict[str, object] | None = None) -> tuple[int, object]:
        """Send an API request and decode JSON for success or HTTP error responses."""
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        try:
            return response.status, json.loads(response.read())
        finally:
            response.close()

    def test_map_failure_is_explicit_then_valid_api_recovers(self) -> None:
        """Return useful JSON for invalid actions and keep healthy endpoints available."""
        status, failure = self.request(
            "/api/spatial/control", {"action": "not-a-control"}
        )
        self.assertEqual(status, 400)
        self.assertIn("Unknown spatial simulation action", failure["error"])
        status, recovered = self.request("/api/spatial/map")
        self.assertEqual(status, 200)
        self.assertEqual(recovered["data_classification"], "synthetic_demonstration_only")
        status, state = self.request("/api/spatial/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["status"], "ready")

    def test_product_route_control_roundtrip_and_validation(self) -> None:
        """Validate product-selection requests and expose computed graph route."""
        status, error = self.request(
            "/api/spatial/control",
            {"action": "set_products", "product_ids": ["NOT-A-DEMO-ID"]},
        )
        self.assertEqual(status, 400)
        self.assertIn("Unknown synthetic demo product", error["error"])
        status, state = self.request(
            "/api/spatial/control",
            {"action": "set_products", "product_ids": ["SIM-P-001"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(state["selected_product_ids"], ["SIM-P-001"])
        self.assertEqual(state["planned_route"][-1], "N4_5")

    def test_paused_navigation_accepts_fixed_step_and_resumes(self) -> None:
        """Keep fixed-step progress available while paused, then resume safely."""
        status, started = self.request(
            "/api/spatial/control", {"action": "start"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(started["status"], "navigating")
        status, paused = self.request(
            "/api/spatial/control", {"action": "pause"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(paused["status"], "paused")
        status, stepped = self.request(
            "/api/spatial/control", {"action": "step", "count": 1}
        )
        self.assertEqual(status, 200)
        self.assertEqual(stepped["status"], "paused")
        self.assertEqual(stepped["simulation_time_s"], 0.25)
        status, resumed = self.request(
            "/api/spatial/control", {"action": "resume"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(resumed["status"], "navigating")

    def test_guided_demo_api_action_starts_one_click_scenario(self) -> None:
        """Expose a documented single API action for the full guided run."""
        status, started = self.request(
            "/api/spatial/control", {"action": "guided_demo"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(started["guided_demo"]["active"])
        self.assertEqual(started["guided_demo"]["stage"], 1)
        self.assertEqual(started["selected_product_ids"], ["SIM-P-001", "SIM-P-006"])
        self.assertTrue(started["running"])


if __name__ == "__main__":
    unittest.main()
