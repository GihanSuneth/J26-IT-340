"""Run a deterministic aisle-and-shelf demo over validated synthetic geometry."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    DeadReckoner,
    MotionMeasurement,
    PositionEstimate,
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
from .checkpoint_observations import (
    CheckpointObservation,
    CheckpointObservationProcessor,
)
from .guidance import (
    GuidanceEngine,
    MAX_ARRIVAL_UNCERTAINTY_M,
    ProductArrivalMonitor,
    ProductLocation,
    classify_turn,
    product_shelf_side,
    resolve_product_location,
)
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
    3: "Navigating to first product shelf",
    4: "First product pickup",
    5: "Wrong turn and deviation confirmation",
    6: "Replacement route active",
    7: "Second product pickup",
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
        self.shelves_by_id = {
            shelf["shelf_id"]: shelf for shelf in self.data["shelves"]
        }
        self.product_locations = {
            product_id: resolve_product_location(product, self.shelves_by_id, self.graph)
            for product_id, product in self.products_by_id.items()
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
        self._last_observed_checkpoint: dict[str, Any] | None = None
        self._last_localization_correction: dict[str, Any] | None = None
        self._events: list[dict[str, Any]] = []
        self._truth_path: list[dict[str, float]] = []
        self._estimated_path: list[dict[str, float]] = []
        self._reroute_count = 0
        self._previous_route: tuple[str, ...] = ()
        self._reroute_episode_active = False
        self._reroute_recovery_samples = 0
        self._last_deviation: dict[str, Any] | None = None
        self._localization_uncertainty_m = 0.05
        self._localization_variance_m2 = 0.0
        self._distance_since_checkpoint_m = 0.0
        self._arrival_state: dict[str, Any] | None = None
        self._arrived_product_id: str | None = None
        self._arrival_heading_rad: float | None = None
        self._announced_edge_turns: set[tuple[int, str, str]] = set()
        self._guided_mode = False
        self._guided_stage = 0
        self._guided_pickup_notice_steps = 0
        self._guided_initial_route_steps = 0
        self._guided_wrong_turn_queued = False
        self._guided_completion_summary: dict[str, Any] | None = None
        self._paused_status: str | None = None
        self.checkpoint_processor = CheckpointObservationProcessor(
            self.store.checkpoint_layout, self.data["map_id"]
        )
        self.arrival_monitor = ProductArrivalMonitor()
        self.guidance_engine = GuidanceEngine(self.graph)
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
        self._refresh_guidance()

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

    def _publish_guidance(
        self,
        instruction_type: str,
        instruction_text: str,
        *,
        distance_to_maneuver_m: float = 0.0,
        target_node: str | None = None,
        product: ProductLocation | None = None,
        shelf_side: str | None = None,
        identity_detail: str | None = None,
    ) -> dict[str, Any]:
        """Publish one structured instruction transition and mirror it in events."""
        event, is_new = self.guidance_engine.publish(
            instruction_type,
            instruction_text,
            timestamp=self.simulation_time_s,
            distance_to_maneuver_m=distance_to_maneuver_m,
            target_node=target_node,
            product=product,
            shelf_side=shelf_side,
            identity_detail=identity_detail,
        )
        if is_new:
            self._record_event(
                "guidance_instruction",
                instruction_text,
                event.to_dict(),
            )
        return event.to_dict()

    def _active_product_location(self) -> ProductLocation | None:
        """Return the next route-ordered product location, including unavailable state."""
        remaining_nodes = set(self.route_manager.remaining_destinations)
        for node_id in self._remaining_route():
            if node_id in remaining_nodes:
                product = self.products_by_node.get(node_id)
                if product:
                    return self.product_locations[product["demo_product_id"]]
        return None

    def _refresh_guidance(self) -> None:
        """Refresh live distance while emitting only meaningful instruction changes."""
        product = self._active_product_location()
        if self.status == "ready":
            target = product.display_name if product else "checkout"
            self._publish_guidance(
                "START",
                f"Route ready at the entrance. Start navigation toward {target}.",
                target_node=product.pickup_node if product else self.checkout_node_id,
                product=product,
            )
            return
        if self.status == "complete":
            self._publish_guidance(
                "ARRIVED_CHECKOUT",
                "Checkout reached. Navigation complete.",
                target_node=self.checkout_node_id,
            )
            return
        if self.status == "awaiting_product_confirmation" and product:
            side = None
            if (
                product.pickup_coordinate_m is not None
                and product.shelf_facing_point_m is not None
                and self._arrival_heading_rad is not None
            ):
                side = product_shelf_side(
                    self._arrival_heading_rad,
                    product.pickup_coordinate_m,
                    product.shelf_facing_point_m,
                )
            text = self._product_arrival_text(product, side, waiting=True)
            self._publish_guidance(
                "WAIT_FOR_PICKUP",
                text,
                target_node=product.pickup_node,
                product=product,
                shelf_side=side,
            )
            return
        route = self._remaining_route()
        next_checkpoint = self._expected_checkpoint()
        checkpoint_distance = (
            self._distance_to_route_node(next_checkpoint["node_id"])
            if next_checkpoint
            else None
        )
        product_distance = (
            self._distance_to_route_node(product.pickup_node)
            if product and product.pickup_node
            else None
        )
        route_start_distance = (
            max(0.0, self._edge_distance_m - self._edge_progress_m)
            if self._edge_target
            else 0.0
        )
        event, is_new = self.guidance_engine.navigation_instruction(
            timestamp=self.simulation_time_s,
            estimated_heading_rad=self.estimator.pose.heading_rad,
            remaining_route=route,
            distance_to_route_start_m=route_start_distance,
            active_product=product,
            distance_to_product_m=product_distance,
            next_checkpoint=next_checkpoint,
            distance_to_checkpoint_m=checkpoint_distance,
            localization_uncertain=(
                self._localization_uncertainty_m > MAX_ARRIVAL_UNCERTAINTY_M
                or self.status in {"localization_uncertain", "reroute_failed"}
            ),
        )
        if is_new:
            self._record_event(
                "guidance_instruction", event.instruction_text, event.to_dict()
            )

    @staticmethod
    def _product_arrival_text(
        product: ProductLocation, side: str | None, *, waiting: bool
    ) -> str:
        """Build shelf guidance only from resolved location metadata."""
        if not product.available:
            return "Product location is unavailable. Ask store staff for assistance."
        if side is None:
            text = "Product shelf reached. Check the highlighted shelf."
        else:
            text = (
                f"You have reached {product.display_name}. It is on your {side}, "
                f"Shelf {product.shelf_id}, Section {product.shelf_section}, "
                f"Level {product.shelf_level}."
            )
        return f"{text} Confirm the product when collected." if waiting else text

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

    def _checkpoint_sequence(self) -> list[dict[str, Any]]:
        """Return undetected checkpoints in their active-route order."""
        return [
            checkpoint
            for node_id in self.route_manager.current_planned_route
            if (checkpoint := self.checkpoints_by_node.get(node_id))
            and checkpoint["checkpoint_id"] not in self._detected_checkpoint_ids
        ]

    def _expected_checkpoint(self) -> dict[str, Any] | None:
        """Return the next route-specific checkpoint expected by localization."""
        sequence = self._checkpoint_sequence()
        return sequence[0] if sequence else None

    def _detect_checkpoint(self, node_id: str) -> None:
        """Submit one clearly labeled synthetic observation at a mapped node."""
        checkpoint = self.checkpoints_by_node.get(node_id)
        if checkpoint is None:
            return
        observation = CheckpointObservation(
            tag_id=checkpoint["checkpoint_id"],
            timestamp_s=self.simulation_time_s,
            detection_source="synthetic_spatial_simulator",
            map_id=self.data["map_id"],
            confidence=1.0,
        )
        self._process_checkpoint_observation(observation)

    def observe_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate an API-supplied observation without claiming camera support."""
        if not isinstance(payload, dict):
            raise ValueError("checkpoint observation must be a JSON object")
        observation = CheckpointObservation(
            tag_id=payload.get("tag_id"),
            timestamp_s=payload.get("timestamp_s"),
            detection_source=payload.get("detection_source", "external_simulated_input"),
            map_id=payload.get("map_id", self.data["map_id"]),
            confidence=payload.get("confidence"),
            observed_x_m=payload.get("observed_x_m"),
            observed_y_m=payload.get("observed_y_m"),
        )
        self._process_checkpoint_observation(observation)
        return self.snapshot()

    def _process_checkpoint_observation(self, observation: CheckpointObservation) -> None:
        """Apply an accepted observation through the existing correction function."""
        expected = self._expected_checkpoint()
        result = self.checkpoint_processor.process(
            observation,
            self.estimator.pose,
            expected_tag_id=expected["checkpoint_id"] if expected else None,
        )
        self._last_observed_checkpoint = {
            **observation.to_dict(),
            "accepted": result.accepted,
            "reason": result.reason,
        }
        if not result.accepted:
            self._record_event(
                "checkpoint_observation_rejected",
                f"Checkpoint observation {observation.tag_id} rejected: {result.reason}.",
                result.to_dict(),
            )
            return
        assert result.corrected_pose is not None
        self.estimator = DeadReckoner(result.corrected_pose)
        self._detected_checkpoint_ids.append(observation.tag_id)
        self._localization_uncertainty_m = 0.05
        self._localization_variance_m2 = 0.0
        self._distance_since_checkpoint_m = 0.0
        correction = {
            "checkpoint_id": observation.tag_id,
            "node_id": result.checkpoint_node_id,
            "correction_m": result.correction_m,
            "detection_source": observation.detection_source,
            "confidence": observation.confidence,
            "simulated_detection": observation.detection_source.startswith("synthetic"),
        }
        self._last_checkpoint_event = dict(correction)
        self._last_localization_correction = dict(correction)
        self._record_event(
            "checkpoint_detected",
            f"Simulated checkpoint {observation.tag_id} detected at {result.checkpoint_node_id}; estimate corrected by {result.correction_m:.3f} m.",
            correction,
        )
        self._publish_guidance(
            "CHECKPOINT_CONFIRMED",
            f"Checkpoint CP{observation.tag_id} confirmed; localization updated.",
            target_node=result.checkpoint_node_id,
            identity_detail=str(observation.tag_id),
        )

    def _update_arrival_monitor(self) -> None:
        """Update estimate-only stable arrival state for the active product."""
        edge_product = (
            self.products_by_node.get(self._edge_target)
            if self._edge_target in self.route_manager.remaining_destinations
            else None
        )
        product = (
            self.product_locations[edge_product["demo_product_id"]]
            if edge_product is not None
            else self._active_product_location()
        )
        if (
            product is None
            or not product.available
            or product.pickup_coordinate_m is None
        ):
            self._arrival_state = None
            return
        estimate = self.estimator.pose
        state = self.arrival_monitor.update(
            target_product_id=product.product_id,
            estimated_position_m=(estimate.x_m, estimate.y_m),
            pickup_coordinate_m=product.pickup_coordinate_m,
            localization_uncertainty_m=self._localization_uncertainty_m,
        )
        self._arrival_state = asdict(state)

    def _stationary_arrival_confirmation(self, product: ProductLocation) -> None:
        """Take one explicit stationary estimate sample to stabilize shelf arrival."""
        if (
            self._arrival_state is None
            or self._arrival_state["arrived"]
            or self._arrival_state["localization_uncertain"]
            or self._arrival_state["consecutive_inside_samples"] < 1
            or product.pickup_coordinate_m is None
        ):
            return
        self.simulation_time_s = round(
            self.simulation_time_s + FIXED_TIMESTEP_S, 9
        )
        measurement = self.sensor_generator.measurement(
            self.simulation_time_s, 0.0, 0.0
        )
        self.estimator.update(measurement)
        self._localization_variance_m2 += self.sensor_config.encoder_noise_std_m ** 2
        self._localization_uncertainty_m = (
            0.05
            + math.sqrt(self._localization_variance_m2)
            + abs(self.sensor_config.encoder_bias_fraction)
            * self._distance_since_checkpoint_m
        )
        estimate = self.estimator.pose
        state = self.arrival_monitor.update(
            target_product_id=product.product_id,
            estimated_position_m=(estimate.x_m, estimate.y_m),
            pickup_coordinate_m=product.pickup_coordinate_m,
            localization_uncertainty_m=self._localization_uncertainty_m,
        )
        self._arrival_state = asdict(state)
        self._record_sample()

    def start(self) -> dict[str, Any]:
        """Start a planned synthetic shopping route."""
        if self.status != "ready":
            raise ValueError("Only a ready spatial simulation can be started")
        self.running = True
        self.status = "navigating"
        self._record_event("started", "Spatial navigation started.")
        product = self._active_product_location()
        self._publish_guidance(
            "START",
            "Navigation started. Follow the highlighted walkable route.",
            target_node=product.pickup_node if product else self.checkout_node_id,
            product=product,
        )
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
            "One-click guided demo started with the configured two-product scenario.",
            {
                "seed": GUIDED_DEMO_SEED,
                "product_ids": list(GUIDED_PRODUCT_IDS),
                "product_names": [
                    self.products_by_id[product_id]["display_name"]
                    for product_id in GUIDED_PRODUCT_IDS
                ],
                "automatic_simulated_pickups": True,
            },
        )
        self.running = True
        self.status = "navigating"
        self._record_event("started", "Spatial navigation started at the entrance.")
        product = self._active_product_location()
        self._publish_guidance(
            "START",
            "Guided navigation started. Follow the highlighted walkable route.",
            target_node=product.pickup_node if product else self.checkout_node_id,
            product=product,
        )
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
        product_id = self._arrived_product_id
        product = self.products_by_id.get(product_id) if product_id else None
        if product is None or product["demo_product_id"] not in self._selected_products:
            raise ValueError("Current location is not a selected product pickup point")
        node_id = product["pickup_node_id"]
        confirmation = self.route_manager.confirm_destination_visit(
            node_id, self.simulation_time_s
        )
        if not confirmation.confirmed:
            raise ValueError(confirmation.failure_reason or "Product collection could not be confirmed")
        product_id = product["demo_product_id"]
        product_location = self.product_locations[product_id]
        self._selected_products = tuple(
            item for item in self._selected_products if item != product_id
        )
        self._active_route = tuple(self.route_manager.current_planned_route)
        self._route_cursor = 0
        self.deviation_monitor = self._new_deviation_monitor(self._active_route)
        self.guidance_engine.route_changed()
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
        self._publish_guidance(
            "PICKUP_CONFIRMED",
            f"{product_location.display_name} pickup confirmed. Continue to the next destination.",
            target_node=node_id,
            product=product_location,
            identity_detail=("automated_simulated" if automated else "manual"),
        )
        if not self._selected_products:
            self._record_event("checkout_next", "All selected products collected; proceed to checkout.")
        self.status = "navigating"
        self.running = True
        self._arrived_product_id = None
        self._arrival_heading_rad = None
        self._arrival_state = None
        self.arrival_monitor.reset()
        if self._guided_mode and automated:
            if product_id == GUIDED_PRODUCT_IDS[0]:
                self._set_guided_stage(5)
                if not self._guided_wrong_turn_queued and not self._wrong_turn_used:
                    self.wrong_turn()
                    self._guided_wrong_turn_queued = True
            elif product_id == GUIDED_PRODUCT_IDS[1]:
                self._set_guided_stage(8)
        self._refresh_guidance()
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

    def _announce_edge_turn(self, target_node_id: str) -> bool:
        """Hold one timestep for a new non-straight graph maneuver instruction."""
        start = self.graph.node(self.current_node_id)
        target = self.graph.node(target_node_id)
        outgoing = heading_between((start.x_m, start.y_m), (target.x_m, target.y_m))
        maneuver = classify_turn(self.estimator.pose.heading_rad, outgoing)
        if maneuver == "STRAIGHT":
            return False
        key = (self.guidance_engine.route_revision, self.current_node_id, target_node_id)
        if key in self._announced_edge_turns:
            return False
        self._announced_edge_turns.add(key)
        verb = {
            "TURN_LEFT": "Turn left",
            "TURN_RIGHT": "Turn right",
            "U_TURN": "Make a U-turn",
        }[maneuver]
        self._publish_guidance(
            maneuver,
            f"{verb} toward {target_node_id}.",
            target_node=target_node_id,
            product=self._active_product_location(),
            identity_detail=f"edge:{self.current_node_id}:{target_node_id}",
        )
        return True

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
            self._publish_guidance(
                "REROUTING",
                "Wrong turn confirmed. Recalculating the remaining route.",
                target_node=self._edge_target,
                identity_detail="deviation_confirmed",
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
            self._publish_guidance(
                "LOCALIZATION_UNCERTAIN",
                "Route replacement failed safely. Confirm your position before continuing.",
                identity_detail="reroute_failed",
            )
            return
        self._reroute_count += 1
        self._reroute_episode_active = True
        self._reroute_recovery_samples = 0
        self._previous_route = self._active_route
        self._active_route = tuple(record.new_route)
        self.guidance_engine.route_changed()
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
        self._publish_guidance(
            "REROUTING",
            "Rerouting complete. Follow the updated highlighted route.",
            target_node=record.new_route[0] if record.new_route else None,
            product=self._active_product_location(),
            identity_detail="replacement_route_active",
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
        preserve_transition = False
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
                    if self._selected_products:
                        self.status = "navigation_error"
                        self.running = False
                        self._record_event(
                            "premature_checkout_blocked",
                            "Checkout arrival was blocked because products remain unconfirmed.",
                            {"remaining_product_ids": list(self._selected_products)},
                        )
                        break
                    self.status = "complete"
                    self.running = False
                    self._record_event("checkout_complete", "Trolley reached checkout.")
                    self._publish_guidance(
                        "ARRIVED_CHECKOUT",
                        "Checkout reached after all selected products were confirmed.",
                        target_node=self.checkout_node_id,
                    )
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
                if self._announce_edge_turn(target):
                    preserve_transition = True
                    break
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
            self._distance_since_checkpoint_m += abs(measurement.wheel_displacement_m)
            self._localization_variance_m2 += self.sensor_config.encoder_noise_std_m ** 2
            self._localization_uncertainty_m = (
                0.05
                + math.sqrt(self._localization_variance_m2)
                + abs(self.sensor_config.encoder_bias_fraction)
                * self._distance_since_checkpoint_m
            )
            self._route_manager_update()
            self._update_arrival_monitor()
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
                    if self._selected_products:
                        self.status = "navigation_error"
                        self.running = False
                        self._record_event(
                            "premature_checkout_blocked",
                            "Checkout arrival was blocked because products remain unconfirmed.",
                            {"remaining_product_ids": list(self._selected_products)},
                        )
                        break
                    self.status = "complete"
                    self.running = False
                    self._record_event("checkout_complete", "Trolley reached checkout.")
                    self._publish_guidance(
                        "ARRIVED_CHECKOUT",
                        "Checkout reached after all selected products were confirmed.",
                        target_node=self.checkout_node_id,
                    )
                    self._complete_guided_demo()
                    break
                if arrived in self.route_manager.remaining_destinations:
                    product = self.products_by_node.get(arrived, {})
                    product_id = product.get("demo_product_id")
                    location = self.product_locations.get(product_id)
                    if location is None or not location.available:
                        self.status = "location_unavailable"
                        self.running = False
                        self._record_event(
                            "product_location_unavailable",
                            "Product pickup location is unavailable; navigation stopped safely.",
                            {
                                "demo_product_id": product_id,
                                "reason": location.unavailable_reason if location else "missing_metadata",
                            },
                        )
                        break
                    self._stationary_arrival_confirmation(location)
                    if (
                        self._arrival_state is None
                        or self._arrival_state["localization_uncertain"]
                        or not self._arrival_state["arrived"]
                    ):
                        self.status = "localization_uncertain"
                        self.running = False
                        self._publish_guidance(
                            "LOCALIZATION_UNCERTAIN",
                            "Product area reached, but localization is uncertain. Confirm your position.",
                            target_node=arrived,
                            product=location,
                            identity_detail="product_arrival_guard",
                        )
                        self._record_event(
                            "product_arrival_rejected",
                            "Estimated-position arrival confirmation did not pass its stability and uncertainty guard.",
                            dict(self._arrival_state or {}),
                        )
                        break
                    self.status = "awaiting_product_confirmation"
                    self.running = False
                    self._arrived_product_id = product_id
                    self._arrival_heading_rad = self.estimator.pose.heading_rad
                    side = product_shelf_side(
                        self._arrival_heading_rad,
                        location.pickup_coordinate_m,
                        location.shelf_facing_point_m,
                    )
                    arrival_text = self._product_arrival_text(location, side, waiting=False)
                    self._record_event(
                        "pickup_reached",
                        (
                            f"{arrival_text} Guided demo will record an automated simulated confirmation."
                            if self._guided_mode
                            else f"{arrival_text} Confirm collection explicitly."
                        ),
                        {
                            "pickup_node_id": arrived,
                            "product_id": product_id,
                            "shelf_id": location.shelf_id,
                            "shelf_section": location.shelf_section,
                            "shelf_level": location.shelf_level,
                            "shelf_bay": location.shelf_bay,
                            "shelf_side": side,
                            "arrival": dict(self._arrival_state),
                            "automatic_simulated_confirmation": self._guided_mode,
                        },
                    )
                    self._publish_guidance(
                        "PRODUCT_REACHED",
                        arrival_text,
                        target_node=arrived,
                        product=location,
                        shelf_side=side,
                    )
                    self._publish_guidance(
                        "WAIT_FOR_PICKUP",
                        self._product_arrival_text(location, side, waiting=True),
                        target_node=arrived,
                        product=location,
                        shelf_side=side,
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
        if not preserve_transition:
            self._refresh_guidance()
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

    def _active_product(self) -> dict[str, Any] | None:
        """Expose the next product and its resolved shelf-level location."""
        location = self._active_product_location()
        if location is None:
            return None
        result = location.to_dict()
        result["demo_product_id"] = location.product_id
        result["name"] = location.display_name
        result["pickup_node_id"] = location.pickup_node
        if (
            location.available
            and location.pickup_coordinate_m is not None
            and location.shelf_facing_point_m is not None
        ):
            result["shelf_side"] = product_shelf_side(
                self._arrival_heading_rad
                if self._arrival_heading_rad is not None
                else self.estimator.pose.heading_rad,
                location.pickup_coordinate_m,
                location.shelf_facing_point_m,
            )
        else:
            result["shelf_side"] = None
        return result

    def _current_lane(self) -> str:
        """Describe the actual mapped lane segment without inventing an aisle name."""
        if self._edge_start and self._edge_target:
            start = self.graph.node(self._edge_start)
            target = self.graph.node(self._edge_target)
            if math.isclose(start.y_m, target.y_m):
                return f"Horizontal lane y={start.y_m:.1f} m"
            if math.isclose(start.x_m, target.x_m):
                return f"Cross-aisle x={start.x_m:.1f} m"
        return f"Mapped intersection {self.current_node_id}"

    def _guidance(self) -> dict[str, Any]:
        """Return the latest structured instruction generated by the engine."""
        if self.guidance_engine.current_event is None:
            self._refresh_guidance()
        assert self.guidance_engine.current_event is not None
        return self.guidance_engine.current_event.to_dict()

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
        checkpoint_sequence = self._checkpoint_sequence()
        estimate = self.estimator.pose
        position_error = math.hypot(
            estimate.x_m - self.true_x_m, estimate.y_m - self.true_y_m
        )
        guidance = self._guidance()
        active_product = self._active_product()
        next_checkpoint = checkpoint_sequence[0] if checkpoint_sequence else None
        checkpoint_distance = 0.0
        if next_checkpoint:
            checkpoint_distance = self._distance_to_route_node(
                next_checkpoint["node_id"]
            )
        product_distance = 0.0
        if active_product and active_product.get("pickup_node_id"):
            product_distance = self._distance_to_route_node(
                active_product["pickup_node_id"]
            )
        total_products = len(self._requested_products)
        collected_count = len(collected_ids)
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
            "heading_deg": math.degrees(estimate.heading_rad),
            "current_aisle": self._current_lane(),
            "active_product": active_product,
            "product_locations": {
                product_id: location.to_dict()
                for product_id, location in self.product_locations.items()
            },
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
            "distance_to_active_product_m": product_distance,
            "navigation_progress": {
                "collected_products": collected_count,
                "total_products": total_products,
                "percent": (
                    100.0
                    if total_products == 0 and self.status == "complete"
                    else 0.0
                    if total_products == 0
                    else 100.0 * collected_count / total_products
                ),
            },
            "travelled_ground_truth": self._truth_path,
            "travelled_estimate": self._estimated_path,
            "guidance": guidance,
            "next_checkpoint": next_checkpoint,
            "current_checkpoint": (
                self.checkpoints_by_node.get(self.current_node_id)
                if self.current_node_id else None
            ),
            "last_confirmed_checkpoint": self._last_checkpoint_event,
            "observed_checkpoint": self._last_observed_checkpoint,
            "localization_correction_event": self._last_localization_correction,
            "distance_to_checkpoint_m": checkpoint_distance,
            "detected_checkpoint_ids": list(self._detected_checkpoint_ids),
            "localization": {
                "status": (
                    "uncertain"
                    if self._localization_uncertainty_m > MAX_ARRIVAL_UNCERTAINTY_M
                    or self.status in {"localization_uncertain", "reroute_failed"}
                    else "checkpoint_confirmed"
                    if self._last_checkpoint_event
                    and self._last_checkpoint_event["checkpoint_id"]
                    == (self._detected_checkpoint_ids[-1] if self._detected_checkpoint_ids else None)
                    else "dead_reckoning"
                ),
                "uncertainty_m": self._localization_uncertainty_m,
                "maximum_arrival_uncertainty_m": MAX_ARRIVAL_UNCERTAINTY_M,
                "source": "synthetic_sensor_model_and_checkpoint_observations",
            },
            "product_arrival": self._arrival_state,
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
            "guidance_events": [
                event.to_dict() for event in self.guidance_engine.events[-100:]
            ],
            "reroute_cost_limitation": (
                "Endpoint-anchored node routing excludes partial-edge travel cost."
            ),
            "events": self._events[-100:],
        }
