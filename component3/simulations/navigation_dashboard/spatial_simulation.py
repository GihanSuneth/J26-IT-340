"""Run a deterministic aisle-and-shelf demo over validated synthetic geometry."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    DeadReckoner,
    MotionMeasurement,
    PositionEstimate,
    SimulatedCheckpointObservation,
    correct_to_checkpoint,
    normalize_heading,
)
from component3.backend.comp3_reco_navigation.navigation.deviation import (
    RouteDeviationMonitor,
)
from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.route_manager import (
    RouteManager,
)

from .demo_store import DemoStore, load_demo_store
from .engine import FIXED_TIMESTEP_S
from .sensors import SensorConfig, SimulatedSensorGenerator

REROUTE_RECOVERY_CONFIRMATIONS = 2
DEVIATION_CONFIRMATIONS = 3
GUIDED_DEMO_SEED = 6042
GUIDED_PRODUCT_IDS = ("SIM-P-001", "SIM-P-006")
GUIDED_PICKUP_NOTICE_STEPS = 4
GUIDED_INITIAL_ROUTE_STEPS = 3
GUIDED_STAGES = {
    0: "Manual navigation",
    1: "Initial route calculated",
    2: "Leaving the entrance",
    3: "Navigating to Bananas",
    4: "Bananas pickup",
    5: "Wrong turn and deviation confirmation",
    6: "Replacement route active",
    7: "Frozen peas pickup",
    8: "Navigating to checkout",
    9: "Demonstration complete",
}


def heading_between(start: tuple[float, float], end: tuple[float, float]) -> float:
    """Calculate a normalized east-zero, counter-clockwise heading."""
    return normalize_heading(math.atan2(end[1] - start[1], end[0] - start[0]))


def turn_instruction(incoming_heading_rad: float, outgoing_heading_rad: float) -> str:
    """Classify a relative heading change as straight, left, right, or U-turn."""
    delta = normalize_heading(outgoing_heading_rad - incoming_heading_rad)
    degrees = math.degrees(delta)
    if abs(degrees) <= 35.0:
        return "Continue straight"
    if abs(degrees) >= 145.0:
        return "Make a U-turn"
    return "Turn left" if degrees > 0 else "Turn right"


class SpatialNavigationSimulation:
    """Navigate selected synthetic products through actual walkable graph edges."""

    def __init__(
        self,
        *,
        store: DemoStore | None = None,
        sensor_config: SensorConfig = SensorConfig(),
        speed_m_s: float = 0.8,
        max_snapping_distance_m: float = 1.0,
    ) -> None:
        """Load the separately versioned synthetic map and initialize state."""
        self.store = store or load_demo_store()
        self.graph = self.store.graph
        self.data = self.store.data
        self.sensor_config = sensor_config
        self.speed_m_s = self._finite_positive(speed_m_s, "speed_m_s")
        self.max_snapping_distance_m = self._finite_positive(
            max_snapping_distance_m, "max_snapping_distance_m"
        )
        self.entrance_node_id = self.data["terminals"]["entrance_node_id"]
        self.checkout_node_id = self.data["terminals"]["checkout_node_id"]
        self.products_by_id = {
            product["demo_product_id"]: product for product in self.data["products"]
        }
        self.products_by_node = {
            product["pickup_node_id"]: product for product in self.data["products"]
        }
        self.checkpoints_by_node = {
            checkpoint["node_id"]: checkpoint for checkpoint in self.data["checkpoints"]
        }
        self._requested_products = tuple(self.products_by_id)
        self._selected_products = self._requested_products
        self._initialize()

    @staticmethod
    def _finite_positive(value: float, label: str) -> float:
        """Validate a finite positive simulation setting."""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{label} must be a finite positive number")
        return float(value)

    def _product_nodes(self, product_ids: Sequence[str]) -> tuple[str, ...]:
        """Resolve unique synthetic product IDs to their walkable pickup nodes."""
        if isinstance(product_ids, (str, bytes)) or not isinstance(product_ids, Sequence):
            raise ValueError("product_ids must be a sequence of demo product IDs")
        result: list[str] = []
        seen: set[str] = set()
        for product_id in product_ids:
            if not isinstance(product_id, str) or product_id not in self.products_by_id:
                raise ValueError(f"Unknown synthetic demo product: {product_id!r}")
            node_id = self.products_by_id[product_id]["pickup_node_id"]
            if node_id not in seen:
                result.append(node_id)
                seen.add(node_id)
        return tuple(result)

    def set_products(self, product_ids: Sequence[str]) -> dict[str, Any]:
        """Replan a not-yet-started session for selected synthetic products."""
        if self.status not in {"ready", "complete"}:
            raise ValueError("Products can only be changed before navigation starts or after reset")
        selected_products = tuple(dict.fromkeys(product_ids))
        self._product_nodes(selected_products)
        self._requested_products = selected_products
        self._selected_products = selected_products
        self._initialize()
        return self.snapshot()

    def _initialize(self) -> None:
        """Reset navigation, estimator, collection, and event state atomically."""
        self.simulation_time_s = 0.0
        self.status = "ready"
        self.running = False
        self.current_node_id = self.entrance_node_id
        entrance = self.graph.node(self.entrance_node_id)
        self.true_x_m, self.true_y_m = entrance.x_m, entrance.y_m
        self.true_heading_rad = 0.0
        self.estimator = DeadReckoner(PositionEstimate(entrance.x_m, entrance.y_m, 0.0, 0.0))
        self.sensor_generator = SimulatedSensorGenerator(self.sensor_config)
        self._edge_start: str | None = None
        self._edge_target: str | None = None
        self._edge_progress_m = 0.0
        self._edge_distance_m = 0.0
        self._previous_node_id: str | None = None
        self._rejoin_node: str | None = None
        self._wrong_turn_requested = False
        self._defer_wrong_turn = False
        self._wrong_turn_used = False
        self._route_cursor = 0
        self._detected_checkpoint_ids: list[int] = []
        self._last_checkpoint_event: dict[str, Any] | None = None
        self._events: list[dict[str, Any]] = []
        self._truth_path: list[dict[str, float]] = []
        self._estimated_path: list[dict[str, float]] = []
        self._reroute_count = 0
        self._previous_route: tuple[str, ...] = ()
        self._reroute_episode_active = False
        self._reroute_recovery_samples = 0
        self._last_deviation: dict[str, Any] | None = None
        self._guided_mode = False
        self._guided_stage = 0
        self._guided_pickup_notice_steps = 0
        self._guided_initial_route_steps = 0
        self._guided_wrong_turn_queued = False
        self._guided_completion_summary: dict[str, Any] | None = None
        self._paused_status: str | None = None
        pickup_nodes = self._product_nodes(self._selected_products)
        self.route_manager = RouteManager(
            self.graph,
            self.entrance_node_id,
            pickup_nodes,
            self.checkout_node_id,
            max_snapping_distance_m=self.max_snapping_distance_m,
        )
        self._active_route = tuple(self.route_manager.current_planned_route)
        self.deviation_monitor = self._new_deviation_monitor(self._active_route)
        self._record_event(
            "route_planned",
            "Route calculated over synthetic walkable lanes using Held-Karp and Dijkstra.",
            {"route_node_ids": list(self._active_route)},
        )
        self._detect_checkpoint(self.current_node_id)
        self._record_sample()

    def _new_deviation_monitor(
        self, route: Sequence[str], *, initially_deviated: bool = False
    ) -> RouteDeviationMonitor:
        """Use the existing confirmed-deviation monitor on the demo graph."""
        return RouteDeviationMonitor(
            self.graph,
            route,
            base_threshold_m=0.3,
            threshold_slope_per_m=0.02,
            hysteresis_m=0.15,
            enter_confirmations=DEVIATION_CONFIRMATIONS,
            recovery_confirmations=REROUTE_RECOVERY_CONFIRMATIONS,
            initially_deviated=initially_deviated,
        )

    def _record_event(
        self, event_type: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        """Append a timestamped synthetic event to the event log."""
        self._events.append(
            {
                "timestamp_s": round(self.simulation_time_s, 3),
                "event_type": event_type,
                "message": message,
                "details": details or {},
            }
        )

    def _record_sample(self) -> None:
        """Record separate map-truth and dead-reckoned positions."""
        self._truth_path.append(
            {
                "timestamp_s": self.simulation_time_s,
                "x_m": self.true_x_m,
                "y_m": self.true_y_m,
            }
        )
        estimate = self.estimator.pose
        self._estimated_path.append(
            {
                "timestamp_s": self.simulation_time_s,
                "x_m": estimate.x_m,
                "y_m": estimate.y_m,
            }
        )

    def _detect_checkpoint(self, node_id: str) -> None:
        """Apply one existing checkpoint correction at a mapped demo tag node."""
        checkpoint = self.checkpoints_by_node.get(node_id)
        if checkpoint is None or checkpoint["checkpoint_id"] in self._detected_checkpoint_ids:
            return
        before = self.estimator.pose
        observation = SimulatedCheckpointObservation(
            checkpoint["checkpoint_id"], self.simulation_time_s, node_id
        )
        corrected = correct_to_checkpoint(
            before, self.store.checkpoint_layout, observation.tag_id
        )
        self.estimator = DeadReckoner(corrected)
        correction_m = math.hypot(corrected.x_m - before.x_m, corrected.y_m - before.y_m)
        self._detected_checkpoint_ids.append(observation.tag_id)
        self._last_checkpoint_event = {
            "checkpoint_id": observation.tag_id,
            "node_id": node_id,
            "correction_m": correction_m,
            "simulated_detection": True,
        }
        self._record_event(
            "checkpoint_detected",
            f"Simulated checkpoint {observation.tag_id} detected at {node_id}; estimate corrected by {correction_m:.3f} m.",
            dict(self._last_checkpoint_event),
        )

    def start(self) -> dict[str, Any]:
        """Start a planned synthetic shopping route."""
        if self.status != "ready":
            raise ValueError("Only a ready spatial simulation can be started")
        self.running = True
        self.status = "navigating"
        self._record_event("started", "Spatial navigation started.")
        return self.snapshot()

    def start_guided_demo(self) -> dict[str, Any]:
        """Reset and start the deterministic two-product guided scenario."""
        if self.sensor_config.seed != GUIDED_DEMO_SEED:
            raise ValueError(
                f"Guided demo requires deterministic sensor seed {GUIDED_DEMO_SEED}"
            )
        self._requested_products = GUIDED_PRODUCT_IDS
        self._selected_products = GUIDED_PRODUCT_IDS
        self._initialize()
        self._guided_mode = True
        self._guided_initial_route_steps = GUIDED_INITIAL_ROUTE_STEPS
        self._set_guided_stage(1)
        self._record_event(
            "guided_demo_started",
            "One-click guided demo started with Bananas and Frozen peas.",
            {
                "seed": GUIDED_DEMO_SEED,
                "product_ids": list(GUIDED_PRODUCT_IDS),
                "automatic_simulated_pickups": True,
            },
        )
        self.running = True
        self.status = "navigating"
        self._record_event("started", "Spatial navigation started at the entrance.")
        return self.snapshot()

    def _set_guided_stage(self, stage: int) -> None:
        """Advance the guided state machine without allowing reverse transitions."""
        if not self._guided_mode:
            return
        if stage < self._guided_stage or stage not in GUIDED_STAGES:
            raise RuntimeError(f"Invalid guided-demo stage transition to {stage}")
        if stage == self._guided_stage:
            return
        self._guided_stage = stage
        self._record_event(
            "guided_stage_changed",
            f"Stage {stage}/9 — {GUIDED_STAGES[stage]}.",
            {"stage": stage, "stage_count": 9, "title": GUIDED_STAGES[stage]},
        )

    def reset(self) -> dict[str, Any]:
        """Reset the simulation while retaining its selected demo products."""
        self._selected_products = self._requested_products
        self._initialize()
        return self.snapshot()

    def pause(self) -> dict[str, Any]:
        """Pause movement without changing the current graph-edge position."""
        if self.status != "navigating" and not (
            self._guided_mode and self.status == "awaiting_product_confirmation"
        ):
            raise ValueError("Only active spatial navigation can be paused")
        self._paused_status = self.status
        self.running = False
        self.status = "paused"
        self._record_event("paused", "Spatial navigation paused.")
        return self.snapshot()

    def resume(self) -> dict[str, Any]:
        """Resume movement from the current edge and fixed-step clock."""
        if self.status != "paused":
            raise ValueError("Only paused spatial navigation can be resumed")
        self.running = True
        self.status = self._paused_status or "navigating"
        self._paused_status = None
        self._record_event("resumed", "Spatial navigation resumed.")
        return self.snapshot()

    def configure_speed(self, speed_m_s: float) -> dict[str, Any]:
        """Update simulated trolley speed without changing route or pose."""
        self.speed_m_s = self._finite_positive(speed_m_s, "speed_m_s")
        self._record_event("speed_changed", f"Simulated trolley speed set to {self.speed_m_s:.1f} m/s.")
        return self.snapshot()

    def wrong_turn(self) -> dict[str, Any]:
        """Request one wrong turn at the next mapped lane intersection."""
        if self.status != "navigating" or self._wrong_turn_used:
            raise ValueError("A wrong turn is only available once while navigating")
        self._wrong_turn_requested = True
        self._defer_wrong_turn = (
            self._edge_target is None
            and self.current_node_id == self.entrance_node_id
        )
        self._record_event(
            "wrong_turn_requested",
            "Wrong turn queued for the next mapped lane intersection.",
        )
        return self.snapshot()

    def confirm_product(self, *, automated: bool = False) -> dict[str, Any]:
        """Collect a product only after reaching and confirming its pickup node."""
        if self.status != "awaiting_product_confirmation":
            raise ValueError("No product is currently waiting for pickup confirmation")
        node_id = self.current_node_id
        product = self.products_by_node.get(node_id)
        if product is None or product["demo_product_id"] not in self._selected_products:
            raise ValueError("Current location is not a selected product pickup point")
        confirmation = self.route_manager.confirm_destination_visit(
            node_id, self.simulation_time_s
        )
        if not confirmation.confirmed:
            raise ValueError(confirmation.failure_reason or "Product collection could not be confirmed")
        product_id = product["demo_product_id"]
        self._selected_products = tuple(
            item for item in self._selected_products if item != product_id
        )
        self._active_route = tuple(self.route_manager.current_planned_route)
        self._route_cursor = 0
        self.deviation_monitor = self._new_deviation_monitor(self._active_route)
        self._record_event(
            "product_collected",
            (
                f"Automated simulated pickup confirmation: {product['name']} at "
                f"{product['shelf_id']}."
                if automated
                else f"Explicitly confirmed simulated pickup: {product['name']} at {product['shelf_id']}."
            ),
            {
                "demo_product_id": product_id,
                "shelf_id": product["shelf_id"],
                "confirmation_mode": (
                    "guided_demo_automated_simulated" if automated else "manual_simulated"
                ),
            },
        )
        if not self._selected_products:
            self._record_event("checkout_next", "All selected products collected; proceed to checkout.")
        self.status = "navigating"
        self.running = True
        if self._guided_mode and automated:
            if product_id == GUIDED_PRODUCT_IDS[0]:
                self._set_guided_stage(5)
                if not self._guided_wrong_turn_queued and not self._wrong_turn_used:
                    self.wrong_turn()
                    self._guided_wrong_turn_queued = True
            elif product_id == GUIDED_PRODUCT_IDS[1]:
                self._set_guided_stage(8)
        return self.snapshot()

    def _next_route_node(self) -> str | None:
        """Return the next node after the current graph location."""
        route = self.route_manager.current_planned_route
        for index in range(self._route_cursor, len(route) - 1):
            if route[index] == self.current_node_id:
                self._route_cursor = index
                return route[index + 1]
        return None

    def _select_wrong_edge(self, planned_next: str | None) -> str | None:
        """Choose an actual adjacent lane edge differing from the planned leg."""
        neighbors = [
            node_id
            for node_id, _ in self.graph.neighbors(self.current_node_id)
            if node_id != planned_next and node_id != self._previous_node_id
        ]
        return neighbors[0] if neighbors else None

    def _begin_edge(self, target_node_id: str, *, wrong_turn: bool = False) -> None:
        """Begin physical movement on one validated graph edge."""
        self._edge_start = self.current_node_id
        self._edge_target = target_node_id
        self._edge_progress_m = 0.0
        self._edge_distance_m = self.graph.edge_weight(self._edge_start, target_node_id)
        start = self.graph.node(self._edge_start)
        target = self.graph.node(target_node_id)
        self.true_heading_rad = heading_between(
            (start.x_m, start.y_m), (target.x_m, target.y_m)
        )
        if wrong_turn:
            self._wrong_turn_requested = False
            self._wrong_turn_used = True
            self._record_event(
                "wrong_turn",
                f"Simulated trolley takes valid lane edge {self._edge_start} → {target_node_id}.",
                {"from_node": self._edge_start, "to_node": target_node_id},
            )

    def _route_manager_update(self) -> None:
        """Feed only estimator output to the established deviation and reroute logic."""
        state = self.deviation_monitor.update(self.estimator.pose)
        self._last_deviation = {
            "distance_m": state.measurement.distance_m,
            "threshold_m": state.measurement.threshold_m,
            "is_deviated": state.is_deviated,
            "entered_deviation": state.entered_deviation,
            "consecutive_enter_samples": state.consecutive_enter_samples,
        }
        if self._reroute_episode_active:
            recovered_to_route = self._rejoin_node is None and (
                state.recovered
                or state.measurement.distance_m <= state.exit_threshold_m
            )
            if recovered_to_route:
                self._reroute_recovery_samples += 1
                if self._reroute_recovery_samples >= REROUTE_RECOVERY_CONFIRMATIONS:
                    self._reroute_episode_active = False
                    self._reroute_recovery_samples = 0
                    self._record_event(
                        "deviation_recovered",
                        "Estimated position recovered on the updated route after graph rejoin.",
                        {
                            "distance_m": state.measurement.distance_m,
                            "exit_threshold_m": state.exit_threshold_m,
                        },
                    )
            else:
                self._reroute_recovery_samples = 0
            return
        if state.entered_deviation:
            self._record_event(
                "deviation_confirmed",
                "Existing deviation monitor confirmed the trolley is outside the planned route.",
                {
                    "distance_m": state.measurement.distance_m,
                    "threshold_m": state.measurement.threshold_m,
                    "confirmation_samples": DEVIATION_CONFIRMATIONS,
                },
            )
        record = self.route_manager.process_position(self.estimator.pose, state)
        if record is None:
            return
        if not record.successful:
            self._record_event(
                "reroute_failed",
                f"Deviation confirmed, but route replacement failed safely: {record.failure_reason}.",
                {"failure_reason": record.failure_reason},
            )
            self.status = "reroute_failed"
            self.running = False
            return
        self._reroute_count += 1
        self._reroute_episode_active = True
        self._reroute_recovery_samples = 0
        self._previous_route = self._active_route
        self._active_route = tuple(record.new_route)
        self._route_cursor = 0
        self.deviation_monitor = self._new_deviation_monitor(
            self._active_route, initially_deviated=True
        )
        if self._edge_start and self._edge_target:
            start = self.graph.node(self._edge_start)
            target = self.graph.node(self._edge_target)
            start_distance = math.hypot(self.true_x_m - start.x_m, self.true_y_m - start.y_m)
            end_distance = math.hypot(self.true_x_m - target.x_m, self.true_y_m - target.y_m)
            self._rejoin_node = (
                self._edge_start if start_distance <= end_distance else self._edge_target
            )
            if self._rejoin_node == self._edge_start:
                old_start, old_target = self._edge_start, self._edge_target
                self._edge_start, self._edge_target = old_target, old_start
                self._edge_progress_m = self._edge_distance_m - self._edge_progress_m
        self._record_event(
            "reroute_success",
            "Confirmed deviation; existing route manager replanned remaining pickups and checkout.",
            {
                "previous_route_node_ids": list(self._previous_route),
                "route_node_ids": list(record.new_route),
                "remaining_destinations": list(record.remaining_destinations),
                "partial_edge_cost_included": False,
            },
        )
        if self._guided_mode:
            self._set_guided_stage(6)

    def step(self, count: int = 1) -> dict[str, Any]:
        """Advance graph-constrained movement by deterministic fixed timesteps."""
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 40:
            raise ValueError("step count must be an integer from 1 to 40")
        if (
            self._guided_mode
            and self.status == "navigating"
            and self._guided_stage == 1
            and self._guided_initial_route_steps > 0
        ):
            self._guided_initial_route_steps -= 1
            return self.snapshot()
        if (
            self.status == "paused"
            and self._paused_status == "awaiting_product_confirmation"
        ):
            return self.snapshot()
        if (
            self._guided_mode
            and self.status == "awaiting_product_confirmation"
            and self._guided_pickup_notice_steps > 0
        ):
            self._guided_pickup_notice_steps -= 1
            if self._guided_pickup_notice_steps == 0:
                return self.confirm_product(automated=True)
            return self.snapshot()
        if self.status not in {"navigating", "paused"}:
            raise ValueError("Spatial simulation is not currently navigating")
        was_paused = self.status == "paused"
        for _ in range(count):
            if self.status not in {"navigating", "paused"}:
                break
            self.simulation_time_s = round(
                self.simulation_time_s + FIXED_TIMESTEP_S, 9
            )
            if self._guided_mode and self._guided_stage == 1:
                self._set_guided_stage(2)
            if self._edge_start is None:
                if self.current_node_id == self.checkout_node_id:
                    self.status = "complete"
                    self.running = False
                    self._record_event("checkout_complete", "Trolley reached checkout.")
                    self._complete_guided_demo()
                    break
                target = self._rejoin_node or self._next_route_node()
                if target is None:
                    self.status = "reroute_failed"
                    self.running = False
                    self._record_event("navigation_error", "No next graph edge is available.")
                    break
                planned_next = self._next_route_node()
                taking_wrong_turn = False
                if (
                    self._wrong_turn_requested
                    and not self._defer_wrong_turn
                    and self._rejoin_node is None
                ):
                    alternate = self._select_wrong_edge(planned_next)
                    if alternate is not None:
                        target = alternate
                        taking_wrong_turn = True
                self._begin_edge(target, wrong_turn=taking_wrong_turn)

            assert self._edge_start is not None and self._edge_target is not None
            movement_m = min(
                self.speed_m_s * FIXED_TIMESTEP_S,
                self._edge_distance_m - self._edge_progress_m,
            )
            self._edge_progress_m += movement_m
            fraction = self._edge_progress_m / self._edge_distance_m
            start = self.graph.node(self._edge_start)
            target_node = self.graph.node(self._edge_target)
            old_heading = self.estimator.pose.heading_rad
            new_heading = heading_between(
                (start.x_m, start.y_m), (target_node.x_m, target_node.y_m)
            )
            yaw_delta = normalize_heading(new_heading - old_heading)
            self.true_x_m = start.x_m + (target_node.x_m - start.x_m) * fraction
            self.true_y_m = start.y_m + (target_node.y_m - start.y_m) * fraction
            measurement = self.sensor_generator.measurement(
                self.simulation_time_s, movement_m, yaw_delta
            )
            self.estimator.update(measurement)
            self._route_manager_update()
            self._record_sample()

            if self._edge_progress_m + 1e-9 >= self._edge_distance_m:
                arrived = self._edge_target
                self._previous_node_id = self._edge_start
                self.current_node_id = arrived
                self._edge_start = None
                self._edge_target = None
                self._edge_progress_m = 0.0
                self._edge_distance_m = 0.0
                if self._rejoin_node == arrived:
                    self._rejoin_node = None
                    self._route_cursor = 0
                elif self._rejoin_node is None and self._route_cursor < len(
                    self.route_manager.current_planned_route
                ) - 1:
                    route = self.route_manager.current_planned_route
                    if self._route_cursor + 1 < len(route) and route[self._route_cursor + 1] == arrived:
                        self._route_cursor += 1
                if self._defer_wrong_turn and arrived != self.entrance_node_id:
                    self._defer_wrong_turn = False
                if self._guided_mode and self._guided_stage == 2:
                    self._set_guided_stage(3)
                self._detect_checkpoint(arrived)
                if arrived == self.checkout_node_id:
                    self.status = "complete"
                    self.running = False
                    self._record_event("checkout_complete", "Trolley reached checkout.")
                    self._complete_guided_demo()
                    break
                if arrived in self.route_manager.remaining_destinations:
                    self.status = "awaiting_product_confirmation"
                    self.running = False
                    product = self.products_by_node.get(arrived, {})
                    self._record_event(
                        "pickup_reached",
                        (
                            f"Reached pickup point for {product.get('name', arrived)}; "
                            "guided demo will record an automated simulated confirmation."
                            if self._guided_mode
                            else f"Reached pickup point for {product.get('name', arrived)}; confirm collection explicitly."
                        ),
                        {
                            "pickup_node_id": arrived,
                            "shelf_id": product.get("shelf_id"),
                            "automatic_simulated_confirmation": self._guided_mode,
                        },
                    )
                    if self._guided_mode:
                        self.running = True
                        self._guided_pickup_notice_steps = GUIDED_PICKUP_NOTICE_STEPS
                        self._set_guided_stage(
                            4 if product.get("demo_product_id") == GUIDED_PRODUCT_IDS[0] else 7
                        )
                    break
            if was_paused and self.status == "navigating":
                self.status = "paused"
        return self.snapshot()

    def _complete_guided_demo(self) -> None:
        """Record one genuine completion summary after checkout is reached."""
        if not self._guided_mode or self._guided_completion_summary is not None:
            return
        self._set_guided_stage(9)
        self._guided_completion_summary = {
            "seed": GUIDED_DEMO_SEED,
            "products_collected": list(GUIDED_PRODUCT_IDS),
            "checkpoint_sequence": list(self._detected_checkpoint_ids),
            "reroute_count": self._reroute_count,
            "simulation_time_s": self.simulation_time_s,
            "checkout_node_id": self.checkout_node_id,
        }
        self._record_event(
            "guided_demo_complete",
            "Guided demonstration complete: both products collected and checkout reached.",
            dict(self._guided_completion_summary),
        )

    def _remaining_route(self) -> list[str]:
        """Return the current route from the trolley's active route position."""
        route = list(self.route_manager.current_planned_route)
        if self._route_cursor < len(route) and route[self._route_cursor] == self.current_node_id:
            return route[self._route_cursor :]
        for index in range(self._route_cursor, len(route)):
            if route[index] == self.current_node_id:
                self._route_cursor = index
                return route[index:]
        if self._edge_target:
            for index in range(self._route_cursor, len(route)):
                if route[index] == self._edge_target:
                    return route[index:]
        return route

    def _distance_to_route_node(self, node_id: str) -> float:
        """Measure the distance to a node along the planned route when possible."""
        route = self._remaining_route()
        if not route:
            return 0.0
        if self._edge_target and self._edge_target in route:
            start_index = route.index(self._edge_target)
            try:
                target_index = route.index(node_id, start_index)
            except ValueError:
                target_index = -1
            if target_index >= 0:
                return max(0.0, self._edge_distance_m - self._edge_progress_m) + sum(
                    self.graph.edge_weight(route[index], route[index + 1])
                    for index in range(start_index, target_index)
                )
        start_node = self.current_node_id or self.entrance_node_id
        try:
            start_index = route.index(start_node)
            target_index = route.index(node_id, start_index)
        except ValueError:
            start_index = -1
            target_index = -1
        if start_index >= 0 and target_index >= 0:
            return sum(
                self.graph.edge_weight(route[index], route[index + 1])
                for index in range(start_index, target_index)
            )
        route_distance = dijkstra_shortest_path(
            self.graph, self._edge_target or start_node, node_id
        ).total_distance_m
        if self._edge_target:
            route_distance += max(0.0, self._edge_distance_m - self._edge_progress_m)
        return route_distance

    def _active_product(self) -> dict[str, str] | None:
        """Resolve the first remaining planned pickup to its synthetic product."""
        remaining_nodes = set(self.route_manager.remaining_destinations)
        for node_id in self._remaining_route():
            if node_id in remaining_nodes:
                product = self.products_by_node.get(node_id)
                if product:
                    return {
                        "demo_product_id": product["demo_product_id"],
                        "name": product["name"],
                        "shelf_id": product["shelf_id"],
                        "shelf_section": product["shelf_section"],
                        "pickup_node_id": node_id,
                    }
        return None

    def _guidance(self) -> dict[str, Any]:
        """Generate the next instruction and distance from current route geometry."""
        route = self._remaining_route()
        active = self._active_product()
        if self.status == "awaiting_product_confirmation" and active:
            return {
                "instruction": (
                    f"Product pickup reached: automated simulated confirmation pending for "
                    f"{active['name']} at {active['shelf_id']}."
                    if self._guided_mode
                    else f"Product pickup reached: confirm {active['name']} at {active['shelf_id']}."
                ),
                "distance_to_maneuver_m": 0.0,
                "maneuver": "Product pickup reached",
            }
        if self.status == "complete":
            return {
                "instruction": "Proceed to checkout — checkout reached.",
                "distance_to_maneuver_m": 0.0,
                "maneuver": "Checkout reached",
            }
        if not route or len(route) < 2:
            return {
                "instruction": "Proceed to checkout.",
                "distance_to_maneuver_m": 0.0,
                "maneuver": "Proceed to checkout",
            }
        if not self._edge_target and self.current_node_id == route[0]:
            current = self.graph.node(route[0])
            following = self.graph.node(route[1])
            first_leg_heading = heading_between(
                (current.x_m, current.y_m), (following.x_m, following.y_m)
            )
            initial_turn = turn_instruction(
                self.estimator.pose.heading_rad, first_leg_heading
            )
            if initial_turn != "Continue straight":
                active_target = (
                    f"{active['name']} at {active['shelf_id']}"
                    if active
                    else "checkout"
                )
                return {
                    "instruction": f"{initial_turn} at {self.current_node_id} toward {active_target}.",
                    "distance_to_maneuver_m": 0.0,
                    "maneuver": initial_turn,
                    "maneuver_node_id": self.current_node_id,
                }
        start_index = 0
        next_node_id = self._edge_target or route[1]
        if next_node_id not in route:
            next_node_id = route[1]
        start_index = route.index(next_node_id)
        first = self.graph.node(route[start_index - 1] if start_index else route[0])
        second = self.graph.node(next_node_id)
        heading = self.estimator.pose.heading_rad
        distance_to_next = (
            self._edge_distance_m - self._edge_progress_m
            if self._edge_target
            else math.hypot(second.x_m - first.x_m, second.y_m - first.y_m)
        )
        cumulative = distance_to_next
        maneuver = "Continue straight"
        maneuver_node = next_node_id
        for index in range(start_index, len(route) - 1):
            before = self.graph.node(route[index])
            after = self.graph.node(route[index + 1])
            outgoing = heading_between(
                (before.x_m, before.y_m), (after.x_m, after.y_m)
            )
            candidate = turn_instruction(heading, outgoing)
            if candidate != "Continue straight":
                maneuver = candidate
                maneuver_node = route[index]
                break
            cumulative += math.hypot(after.x_m - before.x_m, after.y_m - before.y_m)
        if active:
            target = active["pickup_node_id"]
            if target == maneuver_node and maneuver == "Continue straight":
                instruction = f"Approach {active['shelf_id']} for {active['name']}."
                maneuver = "Approach selected shelf"
            else:
                instruction = f"{maneuver} toward {active['name']} at {active['shelf_id']}."
        else:
            if maneuver_node == self.checkout_node_id and maneuver == "Continue straight":
                instruction = "Proceed to checkout."
                maneuver = "Proceed to checkout"
            else:
                instruction = f"{maneuver} toward checkout."
        return {
            "instruction": instruction,
            "distance_to_maneuver_m": max(0.0, cumulative),
            "maneuver": maneuver,
            "maneuver_node_id": maneuver_node,
        }

    def snapshot(self) -> dict[str, Any]:
        """Return complete browser-safe spatial, product, checkpoint, and route state."""
        remaining_ids = set(self._selected_products)
        selected_products = [
            self.products_by_id[product_id]
            for product_id in self._selected_products
            if product_id in self.products_by_id
        ]
        collected_ids = [
            product_id
            for product_id in self._requested_products
            if product_id not in remaining_ids
        ]
        route = list(self.route_manager.current_planned_route)
        checkpoint_sequence = [
            checkpoint
            for node_id in route
            if (checkpoint := self.checkpoints_by_node.get(node_id))
            and checkpoint["checkpoint_id"] not in self._detected_checkpoint_ids
        ]
        estimate = self.estimator.pose
        position_error = math.hypot(
            estimate.x_m - self.true_x_m, estimate.y_m - self.true_y_m
        )
        guidance = self._guidance()
        next_checkpoint = checkpoint_sequence[0] if checkpoint_sequence else None
        checkpoint_distance = 0.0
        if next_checkpoint:
            checkpoint_distance = self._distance_to_route_node(
                next_checkpoint["node_id"]
            )
        return {
            "map_id": self.data["map_id"],
            "data_classification": self.data["data_classification"],
            "status": self.status,
            "running": self.running,
            "simulation_time_s": self.simulation_time_s,
            "fixed_timestep_s": FIXED_TIMESTEP_S,
            "speed_m_s": self.speed_m_s,
            "current_node_id": self.current_node_id,
            "current_location": (
                f"{self._edge_start} → {self._edge_target}"
                if self._edge_target
                else self.current_node_id
            ),
            "ground_truth": {"x_m": self.true_x_m, "y_m": self.true_y_m},
            "estimate": asdict(estimate),
            "position_error_m": position_error,
            "heading_rad": estimate.heading_rad,
            "current_aisle": (
                (self._active_product() or {}).get("shelf_section")
            ),
            "active_product": self._active_product(),
            "remaining_products": selected_products,
            "collected_product_ids": collected_ids,
            "selected_product_ids": list(self._requested_products),
            "planned_route": route,
            "previous_planned_route": list(self._previous_route),
            "remaining_route": self._remaining_route(),
            "route_distance_m": self.route_manager.current_route_distance_m,
            "remaining_distance_m": self._distance_to_route_node(
                self.checkout_node_id
            ),
            "travelled_ground_truth": self._truth_path,
            "travelled_estimate": self._estimated_path,
            "guidance": guidance,
            "next_checkpoint": next_checkpoint,
            "current_checkpoint": (
                self.checkpoints_by_node.get(self.current_node_id)
                if self.current_node_id else None
            ),
            "last_confirmed_checkpoint": self._last_checkpoint_event,
            "distance_to_checkpoint_m": checkpoint_distance,
            "detected_checkpoint_ids": list(self._detected_checkpoint_ids),
            "deviation": self._last_deviation,
            "reroute_count": self._reroute_count,
            "guided_demo": {
                "active": self._guided_mode,
                "seed": GUIDED_DEMO_SEED,
                "stage": self._guided_stage,
                "stage_count": 9,
                "stage_title": GUIDED_STAGES[self._guided_stage],
                "wrong_turn_injected": self._wrong_turn_used,
                "automatic_pickups": self._guided_mode,
                "completion_summary": self._guided_completion_summary,
            },
            "events": self._events[-100:],
        }
