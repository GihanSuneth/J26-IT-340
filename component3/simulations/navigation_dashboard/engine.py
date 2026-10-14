"""Deterministic software-in-the-loop navigation simulation engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Any, Sequence

from component3.backend.comp3_reco_navigation.navigation.apriltag import (
    AprilTagLayout,
    DEFAULT_APRILTAG_LAYOUT_PATH,
)
from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    DeadReckoner,
    PositionEstimate,
    SimulatedCheckpointObservation,
    correct_to_checkpoint,
    normalize_heading,
)
from component3.backend.comp3_reco_navigation.navigation.deviation import (
    DeviationState,
    RouteDeviationMonitor,
)
from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.route_manager import (
    RouteManager,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    load_store_graph,
)

from .adapter import load_dashboard_data
from .config import DEFAULT_DESTINATION_IDS
from .sensors import SensorConfig, SimulatedSensorGenerator


FIXED_TIMESTEP_S = 0.25
DEFAULT_SPEED_M_S = 0.8
DEFAULT_MAX_SNAPPING_DISTANCE_M = 1.5


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """Timestamped and classified event shown in telemetry and exports."""

    timestamp_s: float
    event_type: str
    message: str
    details: dict[str, Any]


class NavigationSimulation:
    """Maintain separate truth, sensor estimate, detector, and route states."""

    def __init__(
        self,
        *,
        destinations: Sequence[str] = DEFAULT_DESTINATION_IDS,
        sensor_config: SensorConfig = SensorConfig(),
        speed_m_s: float = DEFAULT_SPEED_M_S,
        max_snapping_distance_m: float = DEFAULT_MAX_SNAPPING_DISTANCE_M,
    ) -> None:
        """Build a session using the actual map and existing navigation code."""
        self.graph = load_store_graph()
        self.map_data = load_dashboard_data()
        raw_layout = json.loads(
            DEFAULT_APRILTAG_LAYOUT_PATH.read_text(encoding="utf-8")
        )
        self.layout = AprilTagLayout.from_dict(raw_layout, self.graph)
        self.entrance_node_id = self.map_data["entrance_node_id"]
        self.checkout_node_id = self.map_data["checkout_node_id"]
        self.destinations = self._validate_destinations(destinations)
        self.speed_m_s = self._positive_number(speed_m_s, "speed_m_s")
        self.max_snapping_distance_m = self._positive_number(
            max_snapping_distance_m, "max_snapping_distance_m"
        )
        self.sensor_config = sensor_config
        self._initialize_state()

    @staticmethod
    def _positive_number(value: float, name: str) -> float:
        """Validate one finite positive simulation parameter."""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a finite positive number")
        return float(value)

    def _validate_destinations(self, destinations: Sequence[str]) -> tuple[str, ...]:
        """Accept unique graph-backed mapped destination IDs only."""
        allowed = {item["node_id"] for item in self.map_data["destinations"]}
        if isinstance(destinations, (str, bytes)):
            raise ValueError("destinations must be a sequence of mapped node IDs")
        unique: list[str] = []
        for node_id in destinations:
            if not isinstance(node_id, str) or node_id not in allowed:
                raise ValueError(f"Unknown or unmapped shopping destination: {node_id!r}")
            if node_id not in unique:
                unique.append(node_id)
        return tuple(unique)

    def _initialize_state(self) -> None:
        """Reset all simulation state from the immutable scenario configuration."""
        entrance = self.graph.node(self.entrance_node_id)
        self.simulation_time_s = 0.0
        self.status = "ready"
        self.running = False
        self.guided_demo = False
        self.guided_wrong_turn_queued = False
        self.current_node_id: str | None = self.entrance_node_id
        self.edge_start_node_id: str | None = None
        self.edge_end_node_id: str | None = None
        self.edge_progress_m = 0.0
        self.edge_weight_m = 0.0
        self._true_x_m = entrance.x_m
        self._true_y_m = entrance.y_m
        self._true_heading_rad = 0.0
        self._previous_heading_rad = 0.0
        self._step_index = 0
        self._route_cursor = 0
        self._pending_wrong_turn = False
        self._wrong_turn_hold_samples = 0
        self._trajectory: list[dict[str, float]] = []
        self._truth_trajectory: list[dict[str, float]] = []
        self._checkpoint_events: list[dict[str, Any]] = []
        self._reroute_count = 0
        self._last_checkpoint_correction: dict[str, Any] | None = None
        self._last_deviation: DeviationState | None = None
        self._last_checkpoint_node_id: str | None = None
        self._wrong_turn_active = False
        self._recovery_path: tuple[str, ...] = ()
        self._reroute_failed = False
        self.events: list[SimulationEvent] = []

        self.route_manager = RouteManager(
            self.graph,
            self.entrance_node_id,
            self.destinations,
            self.checkout_node_id,
            max_snapping_distance_m=self.max_snapping_distance_m,
        )
        self._active_route = tuple(self.route_manager.current_planned_route)
        self.deviation_monitor = self._make_deviation_monitor(self._active_route)
        self.estimator = DeadReckoner(
            PositionEstimate(entrance.x_m, entrance.y_m, 0.0, 0.0)
        )
        self.sensor_generator = SimulatedSensorGenerator(self.sensor_config)
        self._append_trajectory()
        self._record_event(
            "route_planned",
            "Initial shopping route calculated with Held-Karp and Dijkstra.",
            {"route_node_ids": list(self._active_route),
             "distance_m": self.route_manager.current_route_distance_m},
        )

    def _make_deviation_monitor(
        self, route: Sequence[str]
    ) -> RouteDeviationMonitor:
        """Create the existing hysteresis detector over the current route."""
        return RouteDeviationMonitor(
            self.graph,
            route,
            base_threshold_m=0.3,
            threshold_slope_per_m=0.02,
            hysteresis_m=0.15,
            enter_confirmations=3,
            recovery_confirmations=2,
        )

    @property
    def current_estimate(self) -> PositionEstimate:
        """Return the current sensor-only dead-reckoning pose."""
        return self.estimator.pose

    def _append_trajectory(self) -> None:
        """Record separate estimator and simulation-truth trajectories."""
        estimate = self.estimator.pose
        error = math.hypot(estimate.x_m - self._true_x_m, estimate.y_m - self._true_y_m)
        self._trajectory.append(
            {
                "timestamp_s": self.simulation_time_s,
                "x_m": estimate.x_m,
                "y_m": estimate.y_m,
                "error_m": error,
            }
        )
        self._truth_trajectory.append(
            {
                "timestamp_s": self.simulation_time_s,
                "x_m": self._true_x_m,
                "y_m": self._true_y_m,
            }
        )

    def _record_event(
        self, event_type: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        """Append a chronological event with a detached JSON-safe payload."""
        self.events.append(
            SimulationEvent(
                self.simulation_time_s,
                event_type,
                message,
                details or {},
            )
        )

    def start(self) -> dict[str, Any]:
        """Start a ready simulation."""
        if self.status != "ready":
            raise ValueError("Only a ready simulation can be started")
        self.running = True
        self.status = "navigating"
        self._record_event("started", "Simulation started.")
        return self.snapshot()

    def pause(self) -> dict[str, Any]:
        """Pause movement without advancing simulated physical time."""
        if not self.running:
            raise ValueError("Simulation is not running")
        self.running = False
        self.status = "paused"
        self._record_event("paused", "Simulation paused.")
        return self.snapshot()

    def resume(self) -> dict[str, Any]:
        """Resume a paused simulation."""
        if self.status != "paused":
            raise ValueError("Only a paused simulation can be resumed")
        self.running = True
        self.status = "navigating"
        self._record_event("resumed", "Simulation resumed.")
        return self.snapshot()

    def configure(
        self,
        *,
        speed_m_s: float | None = None,
        encoder_noise_std_m: float | None = None,
        imu_yaw_noise_std_rad: float | None = None,
    ) -> dict[str, Any]:
        """Update validated playback speed or deterministic sensor-noise scale."""
        if speed_m_s is not None:
            self.speed_m_s = self._positive_number(speed_m_s, "speed_m_s")
        noise_encoder = (
            self.sensor_config.encoder_noise_std_m
            if encoder_noise_std_m is None
            else encoder_noise_std_m
        )
        noise_imu = (
            self.sensor_config.imu_yaw_noise_std_rad
            if imu_yaw_noise_std_rad is None
            else imu_yaw_noise_std_rad
        )
        updated = SensorConfig(
            seed=self.sensor_config.seed,
            encoder_noise_std_m=noise_encoder,
            encoder_bias_fraction=self.sensor_config.encoder_bias_fraction,
            imu_yaw_noise_std_rad=noise_imu,
            imu_yaw_bias_rad_per_sample=self.sensor_config.imu_yaw_bias_rad_per_sample,
        )
        self.sensor_config = updated
        self.sensor_generator = SimulatedSensorGenerator(updated)
        self._record_event(
            "configuration_changed",
            "Simulation speed or synthetic sensor noise updated.",
            {
                "speed_m_s": self.speed_m_s,
                "encoder_noise_std_m": updated.encoder_noise_std_m,
                "imu_yaw_noise_std_rad": updated.imu_yaw_noise_std_rad,
            },
        )
        return self.snapshot()

    def set_destinations(self, destinations: Sequence[str]) -> dict[str, Any]:
        """Replace the shopping selection before simulation starts."""
        if self.status != "ready":
            raise ValueError("Reset the simulation before changing destinations")
        self.destinations = self._validate_destinations(destinations)
        self._initialize_state()
        return self.snapshot()

    def trigger_wrong_turn(self) -> dict[str, Any]:
        """Queue a valid alternative graph-edge turn at the next junction."""
        if self.status in {"complete", "ready"}:
            raise ValueError("Start the simulation before triggering a wrong turn")
        if self._pending_wrong_turn or self._wrong_turn_hold_samples:
            raise ValueError("A wrong turn is already active")
        self._pending_wrong_turn = True
        self._record_event(
            "wrong_turn_queued",
            "Wrong turn queued for the next valid graph junction; no teleportation.",
        )
        return self.snapshot()

    def guided_start(self) -> dict[str, Any]:
        """Start the reproducible panel scenario with its wrong turn at B4."""
        if self.status != "ready":
            raise ValueError("Guided demonstration can only start from a reset session")
        self.guided_demo = True
        self.guided_wrong_turn_queued = True
        self._record_event(
            "guided_demo_started",
            "Guided demo seed 6042: default route, drift, checkpoint corrections, "
            "wrong turn at the B4 junction, confirmed deviation, reroute, and checkout.",
            {
                "seed": self.sensor_config.seed,
                "sample_interval_s": FIXED_TIMESTEP_S,
                "speed_m_s": self.speed_m_s,
                "destinations": list(self.destinations),
            },
        )
        self.running = True
        self.status = "navigating"
        self._record_event("started", "Guided navigation started.")
        return self.snapshot()

    def step(self, count: int = 1) -> dict[str, Any]:
        """Advance a fixed number of deterministic physical-time samples."""
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100:
            raise ValueError("step count must be an integer from 1 to 100")
        if self.status == "ready":
            raise ValueError("Start the simulation before stepping")
        if self.status in {"complete", "awaiting_stop_confirmation"}:
            return self.snapshot()
        if self._reroute_failed:
            return self.snapshot()
        previous_running = self.running
        self.running = False
        for _ in range(count):
            if self.status in {"complete", "awaiting_stop_confirmation"} or self._reroute_failed:
                break
            self._advance_one_sample()
        special_states = {
            "deviation_suspected", "deviation_confirmed", "rerouting"
        }
        if previous_running and self.status not in {
            "complete", "awaiting_stop_confirmation", "paused"
        } and not self._reroute_failed:
            self.running = True
            if self.status not in special_states:
                self.status = "navigating"
        elif not previous_running and self.status not in {
            "complete", "awaiting_stop_confirmation"
        } and not self._reroute_failed:
            self.running = False
            if self.status not in special_states:
                self.status = "paused"
        return self.snapshot()

    def _advance_one_sample(self) -> None:
        """Move on one graph edge segment and feed only sensors to estimator."""
        self.simulation_time_s += FIXED_TIMESTEP_S
        self._step_index += 1
        distance = self.speed_m_s * FIXED_TIMESTEP_S
        old_x, old_y = self._true_x_m, self._true_y_m
        true_yaw_delta = 0.0

        if self._wrong_turn_hold_samples:
            self._wrong_turn_hold_samples -= 1
        elif self.edge_start_node_id is None:
            self._begin_next_edge()
        if self.edge_start_node_id is not None and not self._wrong_turn_hold_samples:
            self._move_on_current_edge(distance)
            new_direction = self._true_heading_rad
            true_yaw_delta = normalize_heading(new_direction - self._previous_heading_rad)
            self._previous_heading_rad = new_direction

        true_displacement = math.hypot(self._true_x_m - old_x, self._true_y_m - old_y)
        measurement = self.sensor_generator.measurement(
            self.simulation_time_s,
            true_displacement,
            true_yaw_delta,
        )
        estimate = self.estimator.update(measurement)
        checkpoint_event = self._checkpoint_if_arrived()
        if checkpoint_event is not None:
            corrected = correct_to_checkpoint(
                estimate, self.layout, checkpoint_event.tag_id
            )
            correction_m = math.hypot(
                corrected.x_m - estimate.x_m, corrected.y_m - estimate.y_m
            )
            self.estimator = DeadReckoner(corrected)
            estimate = corrected
            event_payload = {
                "tag_id": checkpoint_event.tag_id,
                "node_id": checkpoint_event.node_id,
                "correction_m": correction_m,
                "simulated_detection": True,
            }
            self._last_checkpoint_correction = {
                **event_payload,
                "timestamp_s": self.simulation_time_s,
            }
            self._checkpoint_events.append(self._last_checkpoint_correction)
            self._record_event(
                "checkpoint_correction",
                f"Simulated AprilTag {checkpoint_event.tag_id} corrected position "
                f"at {checkpoint_event.node_id} by {correction_m:.3f} m.",
                event_payload,
            )

        self._append_trajectory()
        self._process_deviation(estimate)
        self._handle_arrival()

    def _begin_next_edge(self) -> None:
        """Choose the next planned or explicitly wrong-turn graph edge."""
        if self.current_node_id is None:
            return
        route = tuple(self.route_manager.current_planned_route)
        if self.current_node_id == self.checkout_node_id:
            self._complete_navigation()
            return
        if not route:
            self._stop_route_failure("Active route is empty before checkout.")
            return
        if self._recovery_path:
            try:
                recovery_cursor = self._recovery_path.index(self.current_node_id)
            except ValueError:
                self._recovery_path = ()
            else:
                if recovery_cursor < len(self._recovery_path) - 1:
                    planned_next = self._recovery_path[recovery_cursor + 1]
                    edge_weight = self.graph.edge_weight(
                        self.current_node_id, planned_next
                    )
                    self.edge_start_node_id = self.current_node_id
                    self.edge_end_node_id = planned_next
                    self.edge_progress_m = 0.0
                    self.edge_weight_m = edge_weight
                    self._last_checkpoint_node_id = None
                    return
                self._recovery_path = ()
        try:
            cursor = route.index(self.current_node_id)
        except ValueError:
            self._stop_route_failure(
                f"Current graph node {self.current_node_id} is not in the active route."
            )
            return
        candidates = {neighbor for neighbor, _ in self.graph.neighbors(self.current_node_id)}
        if cursor + 1 < len(route):
            planned_next = route[cursor + 1]
            previous = route[cursor - 1] if cursor else None
            planned_edges = {
                frozenset((route[index], route[index + 1]))
                for index in range(len(route) - 1)
            }
            alternative_nodes = sorted(
                node_id
                for node_id in candidates
                if node_id not in {planned_next, previous, self.checkout_node_id}
                and frozenset((self.current_node_id, node_id)) not in planned_edges
            )
            if (self._pending_wrong_turn or self.guided_wrong_turn_queued) and alternative_nodes:
                self._pending_wrong_turn = False
                self.guided_wrong_turn_queued = False
                planned_next = alternative_nodes[0]
                self._wrong_turn_active = True
                self._record_event(
                    "wrong_turn",
                    f"Simulated trolley takes valid graph edge {self.current_node_id} → "
                    f"{planned_next} instead of the planned route.",
                    {"from_node": self.current_node_id, "to_node": planned_next},
                )
            elif self._pending_wrong_turn:
                self._pending_wrong_turn = False
                self._record_event(
                    "wrong_turn_unavailable",
                    "No unused alternative edge exists at this junction; route unchanged.",
                )
        else:
            self._stop_route_failure(
                f"Active route ended before checkout at {self.current_node_id}."
            )
            return
        edge_weight = self.graph.edge_weight(self.current_node_id, planned_next)
        self.edge_start_node_id = self.current_node_id
        self.edge_end_node_id = planned_next
        self.edge_progress_m = 0.0
        self.edge_weight_m = edge_weight
        self._last_checkpoint_node_id = None

    def _move_on_current_edge(self, max_edge_distance_m: float) -> None:
        """Interpolate truth along a mapped edge; never take a geometric shortcut."""
        if self.edge_start_node_id is None or self.edge_end_node_id is None:
            return
        start = self.graph.node(self.edge_start_node_id)
        end = self.graph.node(self.edge_end_node_id)
        dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
        geometric_length = math.hypot(dx, dy)
        if geometric_length == 0:
            raise ValueError("Mapped graph edge has zero geometric length")
        self._true_heading_rad = math.atan2(dy, dx)
        self.edge_progress_m = min(
            self.edge_weight_m, self.edge_progress_m + max_edge_distance_m
        )
        fraction = self.edge_progress_m / self.edge_weight_m
        self._true_x_m = start.x_m + fraction * dx
        self._true_y_m = start.y_m + fraction * dy
        if self.edge_progress_m >= self.edge_weight_m:
            arrived_node = self.edge_end_node_id
            self.current_node_id = arrived_node
            self.edge_start_node_id = None
            self.edge_end_node_id = None
            self.edge_progress_m = 0.0
            self.edge_weight_m = 0.0
            if self.guided_demo and self.current_node_id == "B4" and not self._reroute_count:
                self.guided_wrong_turn_queued = True
            if self._wrong_turn_active and arrived_node == "M4":
                self._wrong_turn_hold_samples = 5

    def _checkpoint_if_arrived(self) -> SimulatedCheckpointObservation | None:
        """Emit only a simulated known-tag event at a newly reached mapped node."""
        if self.current_node_id is None or self.edge_start_node_id is not None:
            return None
        tag_by_node = {
            checkpoint.node_id: tag_id
            for tag_id, checkpoint in self.layout.checkpoints.items()
        }
        tag_id = tag_by_node.get(self.current_node_id)
        if tag_id is None:
            return None
        if self.current_node_id == self._last_checkpoint_node_id:
            return None
        self._last_checkpoint_node_id = self.current_node_id
        return SimulatedCheckpointObservation(
            tag_id, self.simulation_time_s, self.current_node_id
        )

    def _process_deviation(self, estimate: PositionEstimate) -> None:
        """Feed sensor estimate only into existing detector and route manager."""
        state: DeviationState = self.deviation_monitor.update(estimate)
        previous_state = self._last_deviation
        if state.measurement.is_deviating and not state.is_deviated:
            self.status = "deviation_suspected"
        elif state.is_deviated:
            self.status = "deviation_confirmed"
        else:
            self.status = "navigating"
        self._last_deviation = state
        if (
            state.measurement.is_deviating
            and previous_state is not None
            and not previous_state.measurement.is_deviating
        ):
            self._record_event(
                "deviation_suspected",
                "Estimated position exceeded the active-route deviation threshold.",
                {
                    "distance_m": state.measurement.distance_m,
                    "threshold_m": state.measurement.threshold_m,
                    "confirmation_sample": 1,
                    "required_samples": 3,
                },
            )
        if state.entered_deviation:
            self._record_event(
                "deviation_confirmed",
                "Existing route-deviation detector confirmed an off-route episode.",
                {
                    "distance_m": state.measurement.distance_m,
                    "threshold_m": state.measurement.threshold_m,
                    "confirmation_samples": 3,
                },
            )
        if state.recovered:
            self._record_event(
                "deviation_recovered",
                "Existing route-deviation detector confirmed return to the route.",
                {
                    "distance_m": state.measurement.distance_m,
                    "recovery_samples": 2,
                },
            )
        if not state.entered_deviation:
            return
        record = self.route_manager.process_position(estimate, state)
        if record is None:
            return
        self._reroute_count += 1
        if record.successful:
            self._active_route = record.new_route
            self._route_cursor = 0
            anchor = record.localization.start_node_id
            if anchor is not None:
                if self.edge_start_node_id is not None:
                    endpoint_path = dijkstra_shortest_path(
                        self.graph, self.edge_end_node_id or anchor, anchor
                    ).node_ids
                    self._recovery_path = endpoint_path
                elif self.current_node_id != anchor:
                    self._recovery_path = dijkstra_shortest_path(
                        self.graph, self.current_node_id or anchor, anchor
                    ).node_ids
                else:
                    self._recovery_path = ()
            self.deviation_monitor = self._make_deviation_monitor(self._active_route)
            self._record_event(
                "reroute_success",
                "Confirmed deviation; Held-Karp/Dijkstra planned a route from the "
                "localized graph node. Partial-edge distance is not included.",
                {
                    "previous_route": list(record.previous_route),
                    "new_route": list(record.new_route),
                    "start_node_id": record.localization.start_node_id,
                    "remaining_destinations": list(record.remaining_destinations),
                    "previous_distance_m": record.previous_route_distance_m,
                    "new_distance_m": record.new_route_distance_m,
                    "partial_edge_cost_included": False,
                    "confirmation_samples": 3,
                    "deviation_distance_m": state.measurement.distance_m,
                },
            )
            self.status = "rerouting"
            self.running = True
            self._wrong_turn_active = False
            self._wrong_turn_hold_samples = 0
        else:
            self._record_event(
                "reroute_failed",
                f"Confirmed deviation; safe reroute failure: {record.failure_reason}.",
                {
                    "reason": record.failure_reason,
                    "previous_route_preserved": True,
                    "remaining_destinations": list(record.remaining_destinations),
                },
            )
            self._reroute_failed = True
            self.running = False
            self.status = "deviation_confirmed"

    def _handle_arrival(self) -> None:
        """Apply checkpoint handling, stop confirmation, and terminal completion."""
        if self.current_node_id == self.checkout_node_id and self.edge_start_node_id is None:
            self._complete_navigation()
            return
        if (
            self.current_node_id in self.route_manager.remaining_destinations
            and self.edge_start_node_id is None
        ):
            if self.guided_demo:
                self._confirm_stop(self.current_node_id, automatic=True)
            else:
                self.running = False
                self.status = "awaiting_stop_confirmation"
                self._record_event(
                    "shopping_stop_arrival",
                    f"Arrived at {self.current_node_id}; explicit confirmation is required.",
                    {"node_id": self.current_node_id},
                )

    def _confirm_stop(self, node_id: str, *, automatic: bool) -> dict[str, Any]:
        """Update route only after an explicit user or guided-demo event."""
        result = self.route_manager.confirm_destination_visit(
            node_id, self.simulation_time_s
        )
        if not result.confirmed:
            raise ValueError(result.failure_reason or "Shopping stop confirmation failed")
        self._active_route = tuple(self.route_manager.current_planned_route)
        self._route_cursor = 0
        self._record_event(
            "shopping_stop_confirmed",
            f"{'Guided demo' if automatic else 'User'} confirmed visit to {node_id}.",
            {
                "node_id": node_id,
                "automatic_guided_event": automatic,
                "remaining_destinations": list(result.remaining_destinations),
            },
        )
        if self.current_node_id == self.checkout_node_id and not result.remaining_destinations:
            self._complete_navigation()
        else:
            self.running = self.guided_demo
            self.status = "navigating" if self.running else "paused"
        return self.snapshot()

    def confirm_current_stop(self) -> dict[str, Any]:
        """Confirm the current selected destination after stopping at it."""
        if self.status != "awaiting_stop_confirmation" or self.current_node_id is None:
            raise ValueError("Trolley is not waiting at a shopping destination")
        return self._confirm_stop(self.current_node_id, automatic=False)

    def _complete_navigation(self) -> None:
        """Mark the simulation complete only at checkout with no remaining stops."""
        if self.route_manager.remaining_destinations:
            self.running = False
            self._reroute_failed = True
            self.status = "deviation_confirmed"
            self._record_event(
                "checkout_with_remaining_stops",
                "Checkout reached while shopping destinations remain; navigation stopped safely.",
                {"remaining_destinations": list(self.route_manager.remaining_destinations)},
            )
            return
        if self.status != "complete":
            self.running = False
            self.status = "complete"
            self.current_node_id = self.checkout_node_id
            self._record_event("navigation_complete", "Trolley reached checkout.")

    def _stop_route_failure(self, reason: str) -> None:
        """Stop safely when physical graph location cannot follow the active route."""
        self.running = False
        self._reroute_failed = True
        self.status = "deviation_confirmed"
        self._record_event(
            "navigation_stopped",
            reason,
            {
                "current_node_id": self.current_node_id,
                "remaining_destinations": list(
                    self.route_manager.remaining_destinations
                ),
                "active_route_preserved": list(
                    self.route_manager.current_planned_route
                ),
            },
        )

    def _remaining_route_distance(self) -> float:
        """Sum remaining actual graph weights from the current route position."""
        route = tuple(self.route_manager.current_planned_route)
        if not route:
            return 0.0
        if self.edge_start_node_id and self.edge_end_node_id:
            try:
                start_index = route.index(self.edge_start_node_id)
            except ValueError:
                return self.route_manager.current_route_distance_m
            if (
                start_index + 1 >= len(route)
                or route[start_index + 1] != self.edge_end_node_id
            ):
                return self.route_manager.current_route_distance_m
            remainder = self.edge_weight_m - self.edge_progress_m
            for index in range(start_index + 1, len(route) - 1):
                remainder += self.graph.edge_weight(route[index], route[index + 1])
            return max(0.0, remainder)
        if self.current_node_id in route:
            index = route.index(self.current_node_id)
            return sum(
                self.graph.edge_weight(route[offset], route[offset + 1])
                for offset in range(index, len(route) - 1)
            )
        return self.route_manager.current_route_distance_m

    def metrics(self) -> dict[str, Any]:
        """Calculate aggregate position and route outcomes from real samples."""
        errors = [sample["error_m"] for sample in self._trajectory]
        return {
            "sample_count": len(self._trajectory),
            "simulation_duration_s": self.simulation_time_s,
            "mean_position_error_m": (
                sum(errors) / len(errors) if errors else 0.0
            ),
            "rmse_position_error_m": (
                math.sqrt(sum(error * error for error in errors) / len(errors))
                if errors
                else 0.0
            ),
            "max_position_error_m": max(errors, default=0.0),
            "checkpoint_corrections": len(self._checkpoint_events),
            "reroute_count": self._reroute_count,
            "visited_destinations": list(self.route_manager.visited_destinations),
            "remaining_destinations": list(self.route_manager.remaining_destinations),
            "completed": self.status == "complete",
        }

    def reset(self) -> dict[str, Any]:
        """Restore route, truth, estimator, detector, sensors, and event history."""
        self._initialize_state()
        self._record_event("reset", "Simulation reset to the deterministic initial state.")
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-safe state snapshot for API and UI consumers."""
        estimate = self.estimator.pose
        error = math.hypot(estimate.x_m - self._true_x_m, estimate.y_m - self._true_y_m)
        deviation = getattr(self, "_last_deviation", None)
        return {
            "simulation_time_s": self.simulation_time_s,
            "fixed_timestep_s": FIXED_TIMESTEP_S,
            "status": self.status,
            "running": self.running,
            "guided_demo": self.guided_demo,
            "seed": self.sensor_config.seed,
            "speed_m_s": self.speed_m_s,
            "sensor_config": asdict(self.sensor_config),
            "current_node_id": self.current_node_id,
            "current_location": (
                f"{self.edge_start_node_id} → {self.edge_end_node_id}"
                if self.edge_start_node_id
                else self.current_node_id or "unknown"
            ),
            "planned_route": list(self._active_route),
            "planned_distance_m": self.route_manager.current_route_distance_m,
            "remaining_distance_m": self._remaining_route_distance(),
            "remaining_destinations": list(self.route_manager.remaining_destinations),
            "visited_destinations": list(self.route_manager.visited_destinations),
            "checkout_node_id": self.checkout_node_id,
            "ground_truth": {
                "x_m": self._true_x_m,
                "y_m": self._true_y_m,
                "heading_rad": self._true_heading_rad,
            },
            "estimate": {
                "x_m": estimate.x_m,
                "y_m": estimate.y_m,
                "heading_rad": estimate.heading_rad,
                "timestamp_s": estimate.timestamp_s,
            },
            "position_error_m": error,
            "deviation": (
                {
                    "distance_m": deviation.measurement.distance_m,
                    "threshold_m": deviation.measurement.threshold_m,
                    "exit_threshold_m": deviation.exit_threshold_m,
                    "is_deviated": deviation.is_deviated,
                    "instantaneous_deviation": deviation.measurement.is_deviating,
                    "entered_deviation": deviation.entered_deviation,
                    "recovered": deviation.recovered,
                    "consecutive_enter_samples": deviation.consecutive_enter_samples,
                    "consecutive_recovery_samples": deviation.consecutive_recovery_samples,
                }
                if deviation
                else None
            ),
            "last_checkpoint_correction": self._last_checkpoint_correction,
            "checkpoint_events": list(self._checkpoint_events),
            "reroute_count": self._reroute_count,
            "metrics": self.metrics(),
            "trajectory_estimated": list(self._trajectory),
            "trajectory_ground_truth": list(self._truth_trajectory),
            "events": [asdict(event) for event in self.events],
            "can_start": self.status == "ready",
            "can_pause": self.running,
            "can_step": self.status in {"paused", "ready"} and not self._reroute_failed,
            "can_confirm_stop": self.status == "awaiting_stop_confirmation",
            "can_trigger_wrong_turn": self.status in {
                "navigating", "paused", "deviation_suspected",
                "deviation_confirmed",
            },
            "available_speed_m_s": [0.4, 0.8, 1.2, 1.6],
        }

    def export_csv(self) -> str:
        """Export estimator/truth samples and algorithm events as CSV text."""
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(
            ["record_type", "simulation_time_s", "x_true_m", "y_true_m",
             "x_estimated_m", "y_estimated_m", "position_error_m",
             "event_type", "event_message"]
        )
        truth_by_time = {
            row["timestamp_s"]: row for row in self._truth_trajectory
        }
        estimate_by_time = {row["timestamp_s"]: row for row in self._trajectory}
        for timestamp, estimate in estimate_by_time.items():
            truth = truth_by_time[timestamp]
            writer.writerow(
                [
                    "sample", timestamp, truth["x_m"], truth["y_m"],
                    estimate["x_m"], estimate["y_m"], estimate["error_m"], "", "",
                ]
            )
        for event in self.events:
            writer.writerow(
                [
                    "event", event.timestamp_s, "", "", "", "", "",
                    event.event_type, event.message,
                ]
            )
        return buffer.getvalue()
