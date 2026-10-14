"""Test deterministic movement, sensor isolation, navigation integration, and API."""

from __future__ import annotations

import json
import math
from http.server import ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    MotionMeasurement,
    PositionEstimate,
)
from component3.backend.comp3_reco_navigation.navigation.deviation import (
    RouteDeviationMonitor,
)
from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    held_karp_route,
)
from component3.simulations.navigation_dashboard.dashboard import make_handler
from component3.simulations.navigation_dashboard.engine import (
    FIXED_TIMESTEP_S,
    NavigationSimulation,
)
from component3.simulations.navigation_dashboard.sensors import (
    SensorConfig,
    SimulatedSensorGenerator,
)


def quiet_simulation(**kwargs: object) -> NavigationSimulation:
    """Create an explicitly zero-noise engine unless a test overrides it."""
    kwargs.setdefault(
        "sensor_config",
        SensorConfig(
            seed=6042,
            encoder_noise_std_m=0.0,
            encoder_bias_fraction=0.0,
            imu_yaw_noise_std_rad=0.0,
            imu_yaw_bias_rad_per_sample=0.0,
        ),
    )
    return NavigationSimulation(**kwargs)


def run_until(
    simulation: NavigationSimulation,
    expected_status: str,
    max_steps: int = 2000,
) -> None:
    """Advance one fixed sample at a time until the requested engine state."""
    for _ in range(max_steps):
        if simulation.status == expected_status:
            return
        if simulation._reroute_failed:
            return
        simulation.step()
    raise AssertionError(f"Simulation did not reach {expected_status!r}")


class NavigationSimulationTests(unittest.TestCase):
    """Verify physical-time movement and existing Component 3 algorithms."""

    def test_initial_route_reuses_held_karp(self) -> None:
        """Use the actual route optimizer for the deterministic default stops."""
        simulation = quiet_simulation()
        expected = held_karp_route(
            simulation.graph, "ENT", ("B1", "B3", "B5"), "CHK"
        )
        self.assertEqual(
            simulation.route_manager.current_planned_route,
            expected.route_node_ids,
        )
        self.assertAlmostEqual(
            simulation.route_manager.current_route_distance_m,
            expected.total_distance_m,
        )

    def test_fixed_step_motion_stays_on_mapped_graph_edges(self) -> None:
        """Move only through actual graph segments by a deterministic bounded step."""
        simulation = quiet_simulation()
        simulation.start()
        initial = simulation.snapshot()["ground_truth"]
        result = simulation.step()
        truth = result["ground_truth"]
        self.assertEqual(result["simulation_time_s"], FIXED_TIMESTEP_S)
        self.assertLessEqual(
            math.hypot(truth["x_m"] - initial["x_m"], truth["y_m"] - initial["y_m"]),
            simulation.speed_m_s * FIXED_TIMESTEP_S + 1e-9,
        )
        self.assertEqual(result["current_location"], "ENT → B4")

    def test_synthetic_sensors_are_seeded_and_truth_is_not_estimator_input(self) -> None:
        """Only generated MotionMeasurement values reach the dead reckoner."""
        first = SimulatedSensorGenerator(SensorConfig(seed=33))
        second = SimulatedSensorGenerator(SensorConfig(seed=33))
        one = first.measurement(0.25, 0.1, 0.02)
        two = second.measurement(0.25, 0.1, 0.02)
        self.assertEqual(one, two)
        simulation = quiet_simulation()
        simulation.start()
        result = simulation.step()
        self.assertNotEqual(
            (result["ground_truth"]["x_m"], result["ground_truth"]["y_m"]),
            (result["estimate"]["x_m"], result["estimate"]["y_m"]),
        )
        self.assertIsInstance(simulation.estimator.pose, PositionEstimate)
        self.assertIsInstance(one, MotionMeasurement)

    def test_simulated_mapped_checkpoint_corrects_estimate(self) -> None:
        """Emit a clearly labelled simulated checkpoint and apply existing correction."""
        simulation = quiet_simulation()
        simulation.start()
        run_until(simulation, "navigating", max_steps=1)
        for _ in range(40):
            simulation.step()
            if simulation.snapshot()["checkpoint_events"]:
                break
        corrections = simulation.snapshot()["checkpoint_events"]
        self.assertTrue(corrections)
        self.assertTrue(corrections[0]["simulated_detection"])
        self.assertIn(corrections[0]["tag_id"], simulation.layout.tag_ids)

    def test_passed_node_is_not_visited_without_confirmation(self) -> None:
        """Passing B4 on the planned path leaves all selected stops outstanding."""
        simulation = quiet_simulation()
        simulation.start()
        run_until(simulation, "awaiting_stop_confirmation")
        self.assertEqual(simulation.route_manager.visited_destinations, [])
        self.assertEqual(
            simulation.route_manager.remaining_destinations, ("B1", "B3", "B5")
        )
        confirmation = simulation.confirm_current_stop()
        self.assertEqual(confirmation["visited_destinations"], ["B3"])
        self.assertEqual(
            confirmation["remaining_destinations"], ["B1", "B5"]
        )

    def test_empty_selection_reaches_checkout_without_stops(self) -> None:
        """An empty valid session still follows graph edges to checkout."""
        simulation = quiet_simulation(destinations=())
        self.assertEqual(simulation.route_manager.current_planned_route[0], "ENT")
        self.assertEqual(simulation.route_manager.current_planned_route[-1], "CHK")
        simulation.start()
        run_until(simulation, "complete")
        self.assertEqual(simulation.current_node_id, "CHK")

    def test_brief_detector_deviation_does_not_confirm_reroute(self) -> None:
        """Two off-route estimates followed by recovery stay below confirmation."""
        simulation = quiet_simulation()
        monitor = RouteDeviationMonitor(
            simulation.graph,
            simulation.route_manager.current_planned_route,
            enter_confirmations=3,
        )
        samples = (
            PositionEstimate(14.3, 1.0, 0.0, 0.25),
            PositionEstimate(14.3, 1.0, 0.0, 0.50),
            PositionEstimate(13.8, 1.0, 0.0, 0.75),
        )
        states = [monitor.update(sample) for sample in samples]
        self.assertFalse(any(state.entered_deviation for state in states))
        self.assertFalse(states[-1].is_deviated)
        self.assertEqual(simulation.snapshot()["reroute_count"], 0)

    def test_guided_wrong_turn_is_graph_valid_and_reroutes_once(self) -> None:
        """The guided M4 detour confirms and replans while preserving all stops."""
        simulation = quiet_simulation()
        simulation.guided_start()
        run_until(simulation, "rerouting")
        wrong_turn = next(event for event in simulation.events if event.event_type == "wrong_turn")
        reroute = next(event for event in simulation.events if event.event_type == "reroute_success")
        source, target = wrong_turn.details["from_node"], wrong_turn.details["to_node"]
        self.assertIn((target, simulation.graph.edge_weight(source, target)),
                      simulation.graph.neighbors(source))
        self.assertEqual(reroute.details["remaining_destinations"], ["B1", "B3", "B5"])
        self.assertEqual(reroute.details["new_route"][-1], "CHK")
        self.assertFalse(reroute.details["partial_edge_cost_included"])
        self.assertEqual(simulation.snapshot()["reroute_count"], 1)

    def test_guided_demo_completes_stops_and_checkout(self) -> None:
        """Automatic panel mode confirms simulated visits and ends at checkout."""
        simulation = quiet_simulation()
        simulation.guided_start()
        run_until(simulation, "complete", max_steps=1000)
        self.assertEqual(set(simulation.route_manager.visited_destinations), {"B1", "B3", "B5"})
        self.assertEqual(simulation.route_manager.remaining_destinations, ())
        self.assertEqual(simulation.current_node_id, "CHK")
        self.assertEqual(simulation.snapshot()["reroute_count"], 1)

    def test_failed_reroute_preserves_route_and_stops_safely(self) -> None:
        """A too-strict localization limit cannot partially replace session route."""
        simulation = NavigationSimulation(max_snapping_distance_m=0.001)
        original_route = simulation.route_manager.current_planned_route
        simulation.guided_start()
        run_until(simulation, "deviation_confirmed", max_steps=100)
        failure = next(event for event in simulation.events if event.event_type == "reroute_failed")
        self.assertIn("snapping", failure.details["reason"])
        self.assertEqual(simulation.route_manager.current_planned_route, original_route)
        self.assertEqual(simulation.route_manager.remaining_destinations, ("B1", "B3", "B5"))
        self.assertFalse(simulation.running)
        self.assertTrue(simulation._reroute_failed)

    def test_pause_resume_step_reset_and_validation(self) -> None:
        """Keep clock deterministic across pause, resume, step, and reset."""
        simulation = quiet_simulation()
        simulation.start()
        simulation.pause()
        paused_at = simulation.simulation_time_s
        self.assertEqual(simulation.status, "paused")
        stepped = simulation.step()
        self.assertEqual(stepped["simulation_time_s"], paused_at + FIXED_TIMESTEP_S)
        resumed = simulation.resume()
        self.assertTrue(resumed["running"])
        reset = simulation.reset()
        self.assertEqual(reset["simulation_time_s"], 0.0)
        self.assertEqual(reset["status"], "ready")
        with self.assertRaises(ValueError):
            simulation.configure(speed_m_s=0.0)
        with self.assertRaises(ValueError):
            simulation.set_destinations(("NOT_A_NODE",))

    def test_replay_is_deterministic(self) -> None:
        """Identical seed and actions reproduce metrics, events, and trajectories."""
        outputs = []
        for _ in range(2):
            simulation = quiet_simulation()
            simulation.guided_start()
            run_until(simulation, "complete", max_steps=1000)
            outputs.append(simulation.snapshot())
        self.assertEqual(outputs[0]["metrics"], outputs[1]["metrics"])
        self.assertEqual(outputs[0]["events"], outputs[1]["events"])
        self.assertEqual(
            outputs[0]["trajectory_ground_truth"],
            outputs[1]["trajectory_ground_truth"],
        )
        self.assertEqual(
            outputs[0]["trajectory_estimated"],
            outputs[1]["trajectory_estimated"],
        )

    def test_csv_export_contains_truth_estimate_and_events(self) -> None:
        """Export samples and algorithm events without conflating their fields."""
        simulation = quiet_simulation()
        simulation.start()
        simulation.step()
        exported = simulation.export_csv()
        self.assertIn("x_true_m,y_true_m,x_estimated_m,y_estimated_m", exported)
        self.assertIn("event,0.0", exported)


class NavigationSimulationApiTests(unittest.TestCase):
    """Exercise the loopback dashboard's simulation API over real HTTP."""

    def setUp(self) -> None:
        """Start one isolated local dashboard and deterministic engine per test."""
        self.simulation = quiet_simulation()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.simulation)
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        """Stop the isolated local HTTP listener after every API test."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(
        self,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        """Send one request and decode the API response or expected HTTP error."""
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
            content_type = response.headers.get("Content-Type", "")
            body = response.read()
            if "application/json" in content_type:
                decoded: object = json.loads(body)
            else:
                decoded = body.decode("utf-8")
            return response.status, decoded
        finally:
            response.close()

    def test_start_step_and_state_api(self) -> None:
        """Expose physical-time step results from the local simulation API."""
        status, _ = self.request(
            "/api/simulation/control", payload={"action": "start"}
        )
        self.assertEqual(status, 200)
        status, response = self.request(
            "/api/simulation/control",
            payload={"action": "step", "count": 1},
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["simulation_time_s"], FIXED_TIMESTEP_S)
        status, response = self.request("/api/simulation")
        self.assertEqual(status, 200)
        self.assertEqual(response["current_location"], "ENT → B4")

    def test_invalid_control_is_reported_and_export_endpoints_work(self) -> None:
        """Return explicit client errors and provide JSON/CSV telemetry exports."""
        status, body = self.request(
            "/api/simulation/control",
            payload={"action": "step", "count": -1},
        )
        self.assertEqual(status, 400)
        self.assertIn("step count", body["error"])
        status, body = self.request("/api/simulation/export.csv")
        self.assertEqual(status, 200)
        self.assertIn("x_true_m", body)
        status, body = self.request("/api/simulation/export.json")
        self.assertEqual(status, 200)
        self.assertIn("metrics", body)
