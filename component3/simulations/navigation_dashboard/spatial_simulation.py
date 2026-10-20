"""Run a deterministic aisle-and-shelf demo over validated synthetic geometry."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import time
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
from component3.backend.comp3_reco_navigation.navigation.route_anchor import (
    AnchoredRoutePlan,
    RouteAnchor,
    held_karp_route_from_anchor,
    node_route_anchor,
    route_anchor_from_position,
)
from component3.backend.comp3_reco_navigation.recommendation.live_service import (
    LiveRecommendationService,
    get_live_recommendation_service,
)

from .demo_store import DemoStore, load_demo_store
from .engine import FIXED_TIMESTEP_S
from .checkpoint_observations import (
    CheckpointObservation,
    CheckpointObservationProcessor,
    CheckpointPlausibilityContext,
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
from .shopping_session import (
    Recommendation,
    ShoppingLine,
    ShoppingRevisionConflictError,
    ShoppingSession,
)

REROUTE_RECOVERY_CONFIRMATIONS = 2
DEVIATION_CONFIRMATIONS = 3
GUIDED_DEMO_SEED = 6042
GUIDED_PRODUCT_IDS = ("SIM-P-001", "SIM-P-006")
GUIDED_PICKUP_NOTICE_STEPS = 4
GUIDED_INITIAL_ROUTE_STEPS = 3
ADAPTIVE_CHECKPOINT_DISTANCE_TOLERANCE_M = 1.0
LOCALIZATION_SCAN_EXPECTED_DISTANCE_M = 3.0
LOCALIZATION_SCAN_OVERDUE_DISTANCE_M = 6.0
LOCALIZATION_SCAN_EXPECTED_TIME_S = 6.0
LOCALIZATION_SCAN_OVERDUE_TIME_S = 12.0
LOCALIZATION_CANDIDATE_RADIUS_M = 4.5
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
DENSE_LAYOUT_PATH = Path(__file__).resolve().parents[2] / "data/demo_store/v2/dense_apriltag_layout.json"


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
        recommendation_service: LiveRecommendationService | None = None,
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
        self._recommendation_service = (
            recommendation_service or get_live_recommendation_service()
        )
        self._dismissed_recommendation_products: set[str] = set()
        self._recommendation_events: list[dict[str, Any]] = []
        self._recommendation_diagnostics: dict[str, Any] = {}
        self._last_recommendation_signature: tuple[object, ...] | None = None
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
        self.dense_apriltag_layout = (
            json.loads(DENSE_LAYOUT_PATH.read_text(encoding="utf-8"))
            if DENSE_LAYOUT_PATH.exists() else None
        )
        self.dense_tags_by_id = {
            int(tag["tag_id"]): tag
            for tag in (self.dense_apriltag_layout or {}).get("tags", [])
        }
        self.shopping_session = ShoppingSession(
            tuple(self.products_by_id), tuple(self.products_by_id)
        )
        self._recommendations: dict[str, Recommendation] = {}
        self._sync_legacy_shopping_state()
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

    def _sync_legacy_shopping_state(self) -> None:
        """Maintain Phase 7A-D product-ID fields from quantity-aware state."""
        self._requested_products = self.shopping_session.requested_product_ids
        self._selected_products = self.shopping_session.remaining_product_ids

    def _remaining_nodes_for_lines(
        self, lines: Sequence[ShoppingLine]
    ) -> tuple[str, ...]:
        """Resolve unique remaining shelf destinations for a proposed shopping state."""
        return self._product_nodes(
            tuple(line.product_id for line in lines if line.remaining_quantity > 0)
        )

    def set_products(self, product_ids: Sequence[str]) -> dict[str, Any]:
        """Replan a not-yet-started session for selected synthetic products."""
        if self.status not in {"ready", "complete"}:
            raise ValueError("Products can only be changed before navigation starts or after reset")
        selected_products = tuple(dict.fromkeys(product_ids))
        self._product_nodes(selected_products)
        self.shopping_session = ShoppingSession(
            tuple(self.products_by_id), selected_products
        )
        self._dismissed_recommendation_products.clear()
        self._recommendation_events.clear()
        self._sync_legacy_shopping_state()
        self._initialize()
        return self.snapshot()

    def _initialize(self, *, simulate_entrance_checkpoint: bool = True) -> None:
        """Reset navigation, estimator, collection, and event state atomically."""
        self._sync_legacy_shopping_state()
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
        self._checkpoint_observation_history: list[dict[str, Any]] = []
        self._last_localization_correction: dict[str, Any] | None = None
        self._acknowledged_localization_warning: str | None = None
        self._events: list[dict[str, Any]] = []
        self._last_recommendation_signature = None
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
        self._deferred_until_leave_node: str | None = None
        self._arrival_heading_rad: float | None = None
        self._announced_edge_turns: set[tuple[int, str, str]] = set()
        self._guided_mode = False
        self._guided_stage = 0
        self._guided_pickup_notice_steps = 0
        self._guided_initial_route_steps = 0
        self._guided_wrong_turn_queued = False
        self._guided_completion_summary: dict[str, Any] | None = None
        self._camera_mode = False
        self._camera_available = False
        self._checkpoint_gate: dict[str, Any] | None = None
        self._free_walk_mode = False
        self._free_walk_target_node_id: str | None = None
        self._route_anchor: RouteAnchor | None = None
        self._last_replanning_reason: str | None = None
        self._adaptive_replan_history: list[dict[str, Any]] = []
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
        if simulate_entrance_checkpoint:
            self._detect_checkpoint(self.current_node_id)
        self._record_sample()
        self._refresh_guidance()
        self._refresh_live_recommendations()

    def _refresh_live_recommendations(self) -> None:
        """Infer from authoritative shopping state and expose one verified action."""
        started = time.perf_counter_ns()
        service = self._recommendation_service
        selected_demo = set(self.shopping_session.requested_product_ids)
        reverse_mapping = {
            row["demo_product_id"]: source
            for source, row in (service.inference.mappings.items() if service.inference else ())
            if row.get("demo_product_id") and row.get("navigation_eligible", "").lower() == "true"
        }
        observed = tuple(sorted(
            reverse_mapping[product_id] for product_id in selected_demo
            if product_id in reverse_mapping
        ))
        ranked, inference_ms = service.rank(observed)
        filter_started = time.perf_counter_ns()
        anchor = self._estimated_route_anchor()
        remaining_nodes = self._remaining_nodes_for_lines(self.shopping_session.lines)
        baseline = held_karp_route_from_anchor(
            self.graph, anchor, remaining_nodes, self.checkout_node_id,
            allow_reverse=anchor.travel_direction == "stopped",
        )
        candidate_audit: list[dict[str, Any]] = []
        actionable: list[tuple[dict[str, object], float]] = []
        for rank, candidate in enumerate(ranked, start=1):
            demo_id = candidate.get("mapped_demo_product_id")
            reasons: list[str] = []
            if not self.shopping_session.lines:
                reasons.append("empty_shopping_list")
            if demo_id in selected_demo:
                reasons.append("already_selected_or_collected")
            if demo_id in self._dismissed_recommendation_products:
                reasons.append("dismissed_for_session")
            if not candidate["navigation_eligible"] or not demo_id:
                reasons.append("no_verified_navigation_mapping")
            product = self.products_by_id.get(str(demo_id)) if demo_id else None
            shelf = self.shelves_by_id.get(str(candidate.get("shelf_id")))
            if demo_id and (
                product is None or shelf is None
                or product.get("pickup_node_id") != candidate.get("pickup_node_id")
                or shelf.get("pickup_node_id") != candidate.get("pickup_node_id")
                or candidate.get("pickup_node_id") not in self.graph
            ):
                reasons.append("invalid_active_catalog_or_graph_reference")
            detour: float | None = None
            if not reasons and product is not None:
                proposed_nodes = tuple(dict.fromkeys((*remaining_nodes, product["pickup_node_id"])))
                proposed = held_karp_route_from_anchor(
                    self.graph, anchor, proposed_nodes, self.checkout_node_id,
                    allow_reverse=anchor.travel_direction == "stopped",
                )
                detour = max(0.0, proposed.total_distance_m - baseline.total_distance_m)
                actionable.append((candidate, detour))
            candidate_audit.append({
                "rank": rank, "normalized_product": candidate["product_id"],
                "mapped_demo_product_id": demo_id, "model_score": candidate["score"],
                "eligible": not reasons, "filter_reasons": reasons,
                "route_detour_cost_m": detour,
            })
        filter_ms = (time.perf_counter_ns() - filter_started) / 1_000_000.0
        self._recommendations = {}
        if actionable:
            candidate, detour = actionable[0]
            demo_id = str(candidate["mapped_demo_product_id"])
            product = self.products_by_id[demo_id]
            recommendation_id = service.recommendation_id(
                self.shopping_session.revision, demo_id
            )
            self._recommendations[recommendation_id] = Recommendation(
                recommendation_id=recommendation_id,
                product_id=demo_id,
                recommendation_source=str(candidate["candidate_source"]),
                model_version=str(candidate["model_version"]),
                score=float(candidate["score"]),
                display_explanation=str(candidate["explanation"] or "Ranked by the frozen basket model."),
                mapping_status=str(candidate["mapping_status"]),
                shelf_availability="available",
                shelf_id=str(candidate["shelf_id"]),
                pickup_node_id=str(candidate["pickup_node_id"]),
                navigation_eligible=True,
                route_detour_cost_m=detour,
                shopping_revision=self.shopping_session.revision,
                model_artifact_sha256=service.artifact_sha256,
            )
        fallback = (
            "model_unavailable" if not service.ready else
            "empty_shopping_list" if not self.shopping_session.lines else
            "no_mapped_basket_input" if not observed else
            "no_eligible_candidate" if not actionable else None
        )
        total_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        self._recommendation_diagnostics = {
            **service.status(),
            "shopping_revision": self.shopping_session.revision,
            "normalized_basket_input": list(observed),
            "authoritative_basket_quantities": [
                {
                    "demo_product_id": line.product_id,
                    "normalized_product": reverse_mapping.get(line.product_id),
                    "requested_quantity": line.requested_quantity,
                    "remaining_quantity": line.remaining_quantity,
                    "collected_quantity": line.collected_quantity,
                }
                for line in self.shopping_session.lines
            ],
            "selected_demo_product_ids": sorted(selected_demo),
            "collected_demo_product_ids": sorted(self.shopping_session.collected_product_ids),
            "unmapped_demo_product_ids": sorted(selected_demo - set(reverse_mapping)),
            "candidate_count": len(ranked),
            "eligible_candidate_count": len(actionable),
            "filtered_candidate_count": len(ranked) - len(actionable),
            "candidate_ranking": candidate_audit,
            "inference_latency_ms": inference_ms,
            "eligibility_filtering_latency_ms": filter_ms,
            "end_to_end_latency_ms": total_ms,
            "fallback_state": fallback,
            "customer_message": (
                "No eligible experimental recommendation is available right now."
                if not actionable else None
            ),
        }
        signature = (self.shopping_session.revision, tuple(self._recommendations), fallback)
        if signature != self._last_recommendation_signature:
            self._record_event(
                "recommendation_inference",
                "Frozen Phase 8B inference completed for the current shopping list.",
                {"candidate_count": len(ranked), "eligible_count": len(actionable),
                 "fallback_state": fallback},
            )
            self._last_recommendation_signature = signature

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
                for product_id in self.shopping_session.remaining_product_ids:
                    product = self.products_by_id[product_id]
                    if product["pickup_node_id"] == node_id:
                        return self.product_locations[product_id]
        return None

    def _refresh_guidance(self) -> None:
        """Refresh live distance while emitting only meaningful instruction changes."""
        product = self._active_product_location()
        if self._free_walk_mode:
            if self.status == "free_walking" and self._edge_target:
                text = f"Free walk active toward {self._edge_target}."
                target = self._edge_target
            else:
                text = "Free walk stopped. Choose a connected lane or request navigation."
                target = None
            self._publish_guidance(
                "FREE_WALK", text, target_node=target,
                identity_detail=f"{self.status}:{target}",
            )
            return
        if self.status == "awaiting_checkpoint" and self._checkpoint_gate:
            checkpoint_id = self._checkpoint_gate["checkpoint_id"]
            self._publish_guidance(
                "SCAN_CHECKPOINT",
                f"Scanning for AprilTag CP{checkpoint_id}...",
                target_node=self._checkpoint_gate["node_id"],
                identity_detail=str(checkpoint_id),
            )
            return
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
        self._process_checkpoint_observation(
            observation, adaptive=self._free_walk_mode
        )

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
        if self._camera_mode:
            pose = asdict(self.estimator.pose)
            expected = self._expected_checkpoint()
            self._last_observed_checkpoint = {
                **observation.to_dict(),
                "accepted": False,
                "reason": "camera_mode_requires_camera_source",
                "expected_checkpoint_id": expected["checkpoint_id"] if expected else None,
                "position_before": pose,
                "position_after": pose,
            }
            self._checkpoint_observation_history.append(
                dict(self._last_observed_checkpoint)
            )
            self._record_event(
                "checkpoint_observation_rejected",
                "Non-camera observation rejected while Mac Camera Evaluation is active.",
                dict(self._last_observed_checkpoint),
            )
            return self.snapshot()
        self._process_checkpoint_observation(
            observation, adaptive=self._free_walk_mode
        )
        return self.snapshot()

    def _estimated_route_anchor(self) -> RouteAnchor:
        """Build a route anchor from the estimate and commanded graph topology."""
        revision = self.guidance_engine.route_revision
        if self._edge_start and self._edge_target:
            direction = "toward_end" if self.running else "stopped"
            return route_anchor_from_position(
                self.graph,
                self.estimator.pose,
                max_snap_distance_m=self.max_snapping_distance_m,
                route_revision=revision,
                travel_direction=direction,
                preferred_edge=(self._edge_start, self._edge_target),
            )
        return node_route_anchor(
            self.graph,
            self.current_node_id,
            route_revision=revision,
            travel_direction="stopped",
        )

    def _checkpoint_plausibility(self) -> CheckpointPlausibilityContext:
        """Return online state only; simulated truth is deliberately excluded."""
        return CheckpointPlausibilityContext(
            graph=self.graph,
            estimated_anchor=self._estimated_route_anchor(),
            position_uncertainty_m=self._localization_uncertainty_m,
            maximum_speed_m_s=self.speed_m_s,
            distance_tolerance_m=ADAPTIVE_CHECKPOINT_DISTANCE_TOLERANCE_M,
            last_verified_checkpoint_node_id=(
                self._last_checkpoint_event.get("node_id")
                if self._last_checkpoint_event else None
            ),
            camera_available=self._camera_available,
        )

    def _process_checkpoint_observation(
        self, observation: CheckpointObservation, *, adaptive: bool = False
    ) -> bool:
        """Apply an accepted observation through the existing correction function."""
        expected = self._expected_checkpoint()
        position_before = asdict(self.estimator.pose)
        result = self.checkpoint_processor.process(
            observation,
            self.estimator.pose,
            expected_tag_id=expected["checkpoint_id"] if expected else None,
            allow_unexpected_mapped=adaptive,
            plausibility=self._checkpoint_plausibility() if adaptive else None,
        )
        self._last_observed_checkpoint = {
            **observation.to_dict(),
            "accepted": result.accepted,
            "reason": result.reason,
            "expected_checkpoint_id": expected["checkpoint_id"] if expected else None,
            "position_before": position_before,
            "position_after": (
                asdict(result.corrected_pose) if result.corrected_pose is not None else position_before
            ),
            "classification": result.classification,
            "graph_distance_from_last_checkpoint_m": result.graph_distance_from_last_checkpoint_m,
            "graph_distance_from_estimate_m": result.graph_distance_from_estimate_m,
            "reachable_distance_limit_m": result.reachable_distance_limit_m,
        }
        self._checkpoint_observation_history.append(
            dict(self._last_observed_checkpoint)
        )
        if not result.accepted:
            self._record_event(
                "checkpoint_observation_rejected",
                f"Checkpoint observation {observation.tag_id} rejected: {result.reason}.",
                result.to_dict(),
            )
            return False
        assert result.corrected_pose is not None
        self.estimator = DeadReckoner(result.corrected_pose)
        self._detected_checkpoint_ids.append(observation.tag_id)
        self._localization_uncertainty_m = 0.05
        self._localization_variance_m2 = 0.0
        self._distance_since_checkpoint_m = 0.0
        correction = {
            "checkpoint_id": observation.tag_id,
            "node_id": result.checkpoint_node_id,
            "timestamp_s": observation.timestamp_s,
            "correction_m": result.correction_m,
            "detection_source": observation.detection_source,
            "confidence": observation.confidence,
            "simulated_detection": observation.detection_source != "mac_camera_opencv",
        }
        self._last_checkpoint_event = dict(correction)
        self._last_localization_correction = dict(correction)
        self._record_event(
            "checkpoint_detected",
            (
                f"Camera checkpoint {observation.tag_id} detected at {result.checkpoint_node_id}; "
                if observation.detection_source == "mac_camera_opencv"
                else f"Simulated checkpoint {observation.tag_id} detected at {result.checkpoint_node_id}; "
            ) + f"estimate corrected by {result.correction_m:.3f} m.",
            correction,
        )
        self._publish_guidance(
            "CHECKPOINT_CONFIRMED",
            f"Checkpoint CP{observation.tag_id} confirmed; localization updated.",
            target_node=result.checkpoint_node_id,
            identity_detail=str(observation.tag_id),
        )
        if adaptive and result.reason == "accepted_unexpected_plausible":
            assert result.checkpoint_node_id is not None
            self._replan_from_anchor(
                node_route_anchor(
                    self.graph,
                    result.checkpoint_node_id,
                    route_revision=self.guidance_engine.route_revision,
                ),
                reason="accepted_unexpected_mapped_checkpoint",
            )
        return True

    def _replan_from_anchor(
        self, anchor: RouteAnchor, *, reason: str
    ) -> AnchoredRoutePlan:
        """Atomically publish an exact anchored route over remaining destinations."""
        started = time.perf_counter()
        plan = held_karp_route_from_anchor(
            self.graph,
            anchor,
            self.route_manager.remaining_destinations,
            self.checkout_node_id,
            allow_reverse=anchor.travel_direction == "stopped",
        )
        computation_ms = (time.perf_counter() - started) * 1000.0
        return self._activate_anchored_plan(
            anchor,
            plan,
            reason=reason,
            computation_ms=computation_ms,
            remaining_destinations=self.route_manager.remaining_destinations,
        )

    def _activate_anchored_plan(
        self,
        anchor: RouteAnchor,
        plan: AnchoredRoutePlan,
        *,
        reason: str,
        computation_ms: float,
        remaining_destinations: Sequence[str],
        event_details: dict[str, Any] | None = None,
        count_reroute: bool = True,
        emit_replan_event: bool = True,
        publish_replan_guidance: bool = True,
    ) -> AnchoredRoutePlan:
        """Install one already validated anchored plan without another failure point."""
        previous_route = tuple(self.route_manager.current_planned_route)
        previous_cost = self.route_manager.current_route_distance_m
        self._previous_route = previous_route
        self.route_manager.remaining_destinations = tuple(remaining_destinations)
        self.route_manager.current_planned_route = plan.route_node_ids
        self.route_manager.current_route_distance_m = plan.total_distance_m
        self.route_manager.current_start_node_id = plan.chosen_endpoint_node_id
        self._active_route = plan.route_node_ids
        self._route_cursor = 0
        if count_reroute:
            self._reroute_count += 1
        self._last_replanning_reason = reason
        self.guidance_engine.route_changed()
        self.deviation_monitor = self._new_deviation_monitor(self._active_route)
        self._route_anchor = anchor
        record = {
            "timestamp_s": self.simulation_time_s,
            "reason": reason,
            "route_revision": self.guidance_engine.route_revision,
            "previous_route_node_ids": list(previous_route),
            "route_node_ids": list(plan.route_node_ids),
            "previous_route_cost_m": previous_cost,
            "new_route_cost_m": plan.total_distance_m,
            "partial_edge_distance_m": plan.partial_edge_distance_m,
            "chosen_endpoint_node_id": plan.chosen_endpoint_node_id,
            "replanning_computation_ms": computation_ms,
            "remaining_destinations": list(self.route_manager.remaining_destinations),
            "anchor": anchor.to_dict(),
        }
        if event_details:
            record.update(event_details)
        self._adaptive_replan_history.append(record)
        if emit_replan_event:
            self._record_event(
                "adaptive_route_replanned",
                f"Route recalculated from the verified or estimated position: {reason}.",
                record,
            )
        if publish_replan_guidance:
            self._publish_guidance(
                "REROUTING",
                "Location confirmed. Route recalculated from your current position.",
                target_node=(plan.route_node_ids[0] if plan.route_node_ids else None),
                product=self._active_product_location(),
                identity_detail=reason,
            )
        return plan

    def mutate_shopping_list(
        self,
        action: str,
        product_id: object,
        quantity: object,
        expected_shopping_revision: object,
        *,
        source: str = "customer_selection",
        recommendation_id: str | None = None,
        refresh_recommendations: bool = True,
    ) -> dict[str, Any]:
        """Validate, route-check and atomically commit one live shopping mutation."""
        if self._guided_mode:
            raise ValueError("Dynamic shopping edits are unavailable in the scripted guided demo")
        mutation = self.shopping_session.propose(
            action, product_id, quantity, expected_shopping_revision, source=source
        )
        remaining_nodes = self._remaining_nodes_for_lines(mutation.proposed_lines)
        anchor = self._estimated_route_anchor()
        started = time.perf_counter()
        try:
            plan = held_karp_route_from_anchor(
                self.graph,
                anchor,
                remaining_nodes,
                self.checkout_node_id,
                allow_reverse=anchor.travel_direction == "stopped",
            )
        except (ValueError, KeyError) as exc:
            raise ValueError(f"shopping mutation route is unreachable: {exc}") from exc
        computation_ms = (time.perf_counter() - started) * 1000.0
        was_complete = self.status == "complete"
        self.shopping_session.commit(mutation, self.simulation_time_s)
        self._sync_legacy_shopping_state()
        reason = f"shopping_{action}"
        self._activate_anchored_plan(
            anchor,
            plan,
            reason=reason,
            computation_ms=computation_ms,
            remaining_destinations=remaining_nodes,
            event_details={
                "shopping_revision": self.shopping_session.revision,
                "product_id": mutation.product_id,
                "quantity": mutation.quantity,
                "product_source": mutation.source,
                "recommendation_id": recommendation_id,
            },
        )
        self._record_event(
            "shopping_list_mutated",
            f"Shopping list {action}: {mutation.product_id} × {mutation.quantity}.",
            self.shopping_session.events[-1],
        )
        if was_complete and self._selected_products:
            self.status = "ready"
            self.running = False
            self._record_event(
                "completed_session_reopened",
                "A product was added after checkout; navigation is ready from checkout.",
            )
        if (
            self.status == "awaiting_product_confirmation"
            and self._arrived_product_id not in self._selected_products
        ):
            self._arrived_product_id = None
            self._arrival_state = None
            self.status = "free_walk_stopped" if self._free_walk_mode else "navigating"
            self.running = not self._free_walk_mode
        self._offer_current_shelf_pickup()
        self._refresh_guidance()
        if refresh_recommendations:
            self._refresh_live_recommendations()
        return self.snapshot()

    def accept_recommendation(
        self, recommendation_id: object, expected_shopping_revision: object
    ) -> dict[str, Any]:
        """Accept one revision-bound model suggestion through the atomic mutation path."""
        if not isinstance(recommendation_id, str) or recommendation_id not in self._recommendations:
            raise ValueError("Unknown recommendation ID")
        recommendation = self._recommendations[recommendation_id]
        if recommendation.acceptance_status != "pending":
            raise ValueError("Recommendation has already been resolved")
        if expected_shopping_revision != recommendation.shopping_revision:
            raise ShoppingRevisionConflictError(
                f"Stale shopping-list revision {expected_shopping_revision}; recommendation was generated for revision {recommendation.shopping_revision}"
            )
        if not recommendation.navigation_eligible or recommendation.product_id in self.shopping_session.requested_product_ids:
            raise ValueError("Recommendation is no longer eligible")
        previous_route_revision = self.guidance_engine.route_revision
        previous_route_cost = self.route_manager.current_route_distance_m
        started = time.perf_counter_ns()
        self.mutate_shopping_list(
            "add",
            recommendation.product_id,
            1,
            expected_shopping_revision,
            source="accepted_recommendation",
            recommendation_id=recommendation_id,
            refresh_recommendations=False,
        )
        event = {
            "event_type": "accepted", "recommendation_id": recommendation_id,
            "product_id": recommendation.product_id,
            "model_version": recommendation.model_version,
            "model_artifact_sha256": recommendation.model_artifact_sha256,
            "shopping_revision_before": recommendation.shopping_revision,
            "shopping_revision_after": self.shopping_session.revision,
            "previous_route_revision": previous_route_revision,
            "new_route_revision": self.guidance_engine.route_revision,
            "previous_remaining_route_cost_m": previous_route_cost,
            "new_remaining_route_cost_m": self.route_manager.current_route_distance_m,
            "reroute_latency_ms": (time.perf_counter_ns() - started) / 1_000_000.0,
        }
        self._recommendation_events.append(event)
        self._record_event("recommendation_accepted", "Experimental recommendation accepted.", event)
        self._refresh_live_recommendations()
        return self.snapshot()

    def reject_recommendation(
        self, recommendation_id: object, expected_shopping_revision: object | None = None
    ) -> dict[str, Any]:
        """Record a transparent customer rejection without changing the route."""
        if not isinstance(recommendation_id, str) or recommendation_id not in self._recommendations:
            raise ValueError("Unknown recommendation ID")
        recommendation = self._recommendations[recommendation_id]
        if recommendation.acceptance_status != "pending":
            raise ValueError("Recommendation has already been resolved")
        if expected_shopping_revision is not None and expected_shopping_revision != recommendation.shopping_revision:
            raise ShoppingRevisionConflictError(
                f"Stale shopping-list revision {expected_shopping_revision}; recommendation was generated for revision {recommendation.shopping_revision}"
            )
        self._dismissed_recommendation_products.add(recommendation.product_id)
        event = {
            "event_type": "dismissed", "recommendation_id": recommendation_id,
            "product_id": recommendation.product_id,
            "model_version": recommendation.model_version,
            "shopping_revision": self.shopping_session.revision,
        }
        self._recommendation_events.append(event)
        self._record_event(
            "recommendation_rejected",
            f"Customer dismissed experimental recommendation {recommendation_id}.", event,
        )
        self._refresh_live_recommendations()
        return self.snapshot()

    def start_camera_evaluation(self) -> dict[str, Any]:
        """Start virtual navigation gated by genuine external camera observations."""
        self.shopping_session = self.shopping_session.clone_for_new_run(
            self.simulation_time_s
        )
        self._sync_legacy_shopping_state()
        self._initialize(simulate_entrance_checkpoint=False)
        self._camera_mode = True
        entrance_checkpoint = self.checkpoints_by_node.get(self.entrance_node_id)
        if entrance_checkpoint is None:
            raise ValueError("Camera evaluation requires a mapped entrance checkpoint")
        self._checkpoint_gate = dict(entrance_checkpoint)
        self.status = "awaiting_checkpoint"
        self.running = False
        self._record_event(
            "camera_evaluation_started",
            "Mac Camera Evaluation started; virtual travel is waiting for CP200.",
            {"camera_frames_are_local": True, "physical_hardware": False},
        )
        self._refresh_guidance()
        return self.snapshot()

    def observe_camera_detection(self, tag_id: int, timestamp_s: float) -> dict[str, Any]:
        """Submit one stable camera ID only while the matching route gate is active."""
        observation = CheckpointObservation(
            tag_id=tag_id,
            timestamp_s=timestamp_s,
            detection_source="mac_camera_opencv",
            map_id=self.data["map_id"],
            confidence=None,
        )
        if self._free_walk_mode:
            if tag_id in self.dense_tags_by_id and tag_id not in {200, 201, 202}:
                self._process_dense_camera_observation(observation)
            else:
                self._process_checkpoint_observation(observation, adaptive=True)
            return self.snapshot()
        if self._camera_mode and tag_id in self.dense_tags_by_id and tag_id not in {200, 201, 202}:
            accepted = self._process_dense_camera_observation(observation)
            if accepted and self.status == "awaiting_checkpoint":
                self._checkpoint_gate = None
                self.status = "navigating"
                self.running = True
                self._record_event(
                    "camera_checkpoint_gate_released",
                    f"Mapped dense tag {tag_id} accepted; virtual navigation may continue.",
                )
            self._refresh_guidance()
            return self.snapshot()
        if not self._camera_mode or self.status != "awaiting_checkpoint" or not self._checkpoint_gate:
            self._last_observed_checkpoint = {
                **observation.to_dict(),
                "accepted": False,
                "reason": "checkpoint_gate_not_active",
                "expected_checkpoint_id": (
                    self._checkpoint_gate["checkpoint_id"] if self._checkpoint_gate else None
                ),
                "position_before": asdict(self.estimator.pose),
                "position_after": asdict(self.estimator.pose),
            }
            self._checkpoint_observation_history.append(
                dict(self._last_observed_checkpoint)
            )
            self._record_event(
                "checkpoint_observation_rejected",
                f"Camera tag {tag_id} rejected: checkpoint_gate_not_active.",
                dict(self._last_observed_checkpoint),
            )
            return self.snapshot()
        accepted = self._process_checkpoint_observation(observation)
        if accepted:
            confirmed = self._checkpoint_gate["checkpoint_id"]
            self._checkpoint_gate = None
            self.status = "navigating"
            self.running = True
            self._record_event(
                "camera_checkpoint_gate_released",
                f"CP{confirmed} accepted; virtual navigation may continue.",
            )
            self._refresh_guidance()
        return self.snapshot()

    def _process_dense_camera_observation(self, observation: CheckpointObservation) -> bool:
        """Correct from any active-layout marker while rejecting implausible jumps."""
        tag = self.dense_tags_by_id.get(observation.tag_id)
        before = self.estimator.pose
        reason = "accepted_mapped_dense_marker"
        accepted = True
        if tag is None:
            accepted, reason = False, "unknown_active_layout_tag"
        elif not self._camera_available:
            accepted, reason = False, "camera_unavailable"
        elif observation.tag_id in self._detected_checkpoint_ids:
            accepted, reason = False, "duplicate_observation"
        elif self._checkpoint_observation_history and observation.timestamp_s <= float(
            self._checkpoint_observation_history[-1].get("timestamp_s", -1)
        ):
            accepted, reason = False, "non_monotonic_timestamp"
        correction = math.hypot(float(tag["x_m"]) - before.x_m, float(tag["y_m"]) - before.y_m) if tag else 0.0
        reachable_limit = max(2.0, self._localization_uncertainty_m + 1.0)
        if accepted and correction > reachable_limit + 1e-9:
            accepted, reason = False, "implausible_position_jump"
        after = before
        if accepted:
            after = PositionEstimate(
                float(tag["x_m"]), float(tag["y_m"]), before.heading_rad,
                before.timestamp_s,
            )
            self.estimator = DeadReckoner(after)
            self._detected_checkpoint_ids.append(observation.tag_id)
            self._localization_uncertainty_m = 0.05
            self._localization_variance_m2 = 0.0
            self._distance_since_checkpoint_m = 0.0
        record = {
            **observation.to_dict(), "accepted": accepted, "reason": reason,
            "classification": "dense_mapped_marker", "active_layout_id": (
                self.dense_apriltag_layout or {}
            ).get("layout_id"),
            "anchor": tag.get("anchor") if tag else None,
            "position_before": asdict(before), "position_after": asdict(after),
            "correction_m": correction, "reachable_distance_limit_m": reachable_limit,
            "expected_checkpoint_id": self._checkpoint_gate.get("checkpoint_id") if self._checkpoint_gate else None,
        }
        self._last_observed_checkpoint = record
        self._checkpoint_observation_history.append(dict(record))
        self._record_event(
            "checkpoint_detected" if accepted else "checkpoint_observation_rejected",
            (f"Dense layout tag {observation.tag_id} corrected localization by {correction:.3f} m."
             if accepted else f"Dense layout tag {observation.tag_id} rejected: {reason}."),
            record,
        )
        if accepted:
            self._last_checkpoint_event = {
                "checkpoint_id": observation.tag_id, "node_id": tag["anchor"].get("node_id"),
                "timestamp_s": observation.timestamp_s,
                "correction_m": correction, "detection_source": observation.detection_source,
                "confidence": observation.confidence, "simulated_detection": False,
            }
            self._last_localization_correction = dict(self._last_checkpoint_event)
            if correction > 0.05 and self.status not in {"ready", "complete"}:
                anchor = route_anchor_from_position(
                    self.graph, after, max_snap_distance_m=self.max_snapping_distance_m,
                    route_revision=self.guidance_engine.route_revision,
                    travel_direction="stopped",
                )
                self._replan_from_anchor(anchor, reason="accepted_dense_checkpoint_correction")
        return accepted

    def _graph_distance_to_dense_tag(self, tag: dict[str, Any]) -> float:
        """Return graph-path distance from the estimate anchor to one layout tag."""
        current = self._estimated_route_anchor()
        target = tag["anchor"]
        if target["type"] == "node":
            target_costs = ((str(target["node_id"]), 0.0),)
        else:
            source, end = str(target["source"]), str(target["target"])
            length = self.graph.edge_weight(source, end)
            offset = float(target["offset_m"])
            target_costs = ((source, offset), (end, length - offset))
        best = math.inf
        for source_node, source_cost in current.endpoint_costs(allow_reverse=True):
            for target_node, target_cost in target_costs:
                path = dijkstra_shortest_path(self.graph, source_node, target_node)
                best = min(best, source_cost + path.total_distance_m + target_cost)
        if current.anchor_type == "edge" and target["type"] == "edge":
            current_nodes = {current.edge_start_node_id, current.edge_end_node_id}
            if current_nodes == {target["source"], target["target"]}:
                target_offset = float(target["offset_m"])
                if current.edge_start_node_id == target["source"]:
                    best = min(best, abs(current.distance_to_start_m - target_offset))
                else:
                    best = min(best, abs(current.distance_to_end_m - target_offset))
        return best

    def _candidate_checkpoint_tags(self) -> list[dict[str, Any]]:
        """Select nearby active-layout tags from graph distance, never visibility claims."""
        candidates = []
        last_id = self._last_checkpoint_event.get("checkpoint_id") if self._last_checkpoint_event else None
        for tag in self.dense_tags_by_id.values():
            if int(tag["tag_id"]) == last_id:
                continue
            distance = self._graph_distance_to_dense_tag(tag)
            if distance <= LOCALIZATION_CANDIDATE_RADIUS_M + self._localization_uncertainty_m:
                candidates.append({
                    "checkpoint_id": int(tag["tag_id"]),
                    "graph_distance_m": round(distance, 3),
                    "anchor": dict(tag["anchor"]),
                    "purpose": tag.get("purpose"),
                })
        return sorted(candidates, key=lambda item: (item["graph_distance_m"], item["checkpoint_id"]))[:6]

    def localization_health(self, camera_status: dict[str, Any] | None = None) -> dict[str, Any]:
        """Derive operator localization health from authoritative online state."""
        camera = camera_status or {}
        accepted = next(
            (item for item in reversed(self._checkpoint_observation_history) if item.get("accepted")),
            None,
        )
        last_time = float(accepted["timestamp_s"]) if accepted else None
        elapsed = self.simulation_time_s - last_time if last_time is not None else self.simulation_time_s
        observed = self._last_observed_checkpoint
        camera_unavailable = self._camera_mode and not bool(camera.get("scanning", self._camera_available))
        if camera_unavailable:
            status = "CAMERA_UNAVAILABLE"
            explanation = "Camera frames are not arriving while camera-assisted localization is active."
            action = "Reconnect or select a verified camera, then continue scanning."
        elif observed and not observed.get("accepted") and observed.get("reason") not in {"duplicate_observation", "checkpoint_gate_not_active"}:
            status = "OBSERVATION_REJECTED"
            explanation = f"Latest tag was rejected: {str(observed.get('reason')).replace('_', ' ')}."
            action = "Keep the trolley within the mapped aisle and scan a nearby candidate tag."
        elif (self._distance_since_checkpoint_m >= LOCALIZATION_SCAN_OVERDUE_DISTANCE_M or elapsed >= LOCALIZATION_SCAN_OVERDUE_TIME_S) and self.running:
            status = "SCAN_OVERDUE"
            explanation = "Localization is stale relative to travelled graph distance or simulation time."
            action = "Continue scanning while moving within the mapped aisle."
        elif (self._distance_since_checkpoint_m >= LOCALIZATION_SCAN_EXPECTED_DISTANCE_M or elapsed >= LOCALIZATION_SCAN_EXPECTED_TIME_S) and self.running:
            status = "SCAN_EXPECTED"
            explanation = "A new localization observation is recommended soon."
            action = "Aim the camera toward a nearby mapped tag while continuing safely."
        elif self._last_checkpoint_event and self._distance_since_checkpoint_m <= 0.5:
            status = "CONFIRMED"
            explanation = "The estimate was recently corrected by an accepted mapped observation."
            action = "No action required."
        else:
            status = "ESTIMATED"
            explanation = "Position is currently propagated by the motion model between accepted observations."
            action = "Continue scanning at mapped localization opportunities."
        candidates = self._candidate_checkpoint_tags()
        warning = status in {"SCAN_OVERDUE", "OBSERVATION_REJECTED", "CAMERA_UNAVAILABLE"}
        correction_reroute = (
            not warning
            and self._last_replanning_reason == "accepted_dense_checkpoint_correction"
            and bool(self._adaptive_replan_history)
        )
        if correction_reroute:
            warning = True
            warning_key = f"CORRECTION_REROUTE:{self.guidance_engine.route_revision}"
            explanation = "An accepted AprilTag correction changed the authoritative route anchor and triggered rerouting."
            action = "Review the revised route and continue from the corrected position."
        else:
            warning_key = f"{status}:{observed.get('tag_id') if observed else ''}:{self._last_checkpoint_event.get('checkpoint_id') if self._last_checkpoint_event else ''}"
        return {
            "status": status,
            "warning": warning,
            "warning_key": warning_key,
            "acknowledged": warning and warning_key == self._acknowledged_localization_warning,
            "last_accepted_checkpoint_id": self._last_checkpoint_event.get("checkpoint_id") if self._last_checkpoint_event else None,
            "last_accepted_checkpoint_timestamp_s": last_time,
            "current_estimated_position": asdict(self.estimator.pose),
            "position_uncertainty_m": self._localization_uncertainty_m,
            "camera_state": {
                "connection": camera.get("connection", "unknown"),
                "scanning": bool(camera.get("scanning", False)),
                "frame_read": bool(camera.get("frame_read", False)),
                "error": camera.get("error"),
            },
            "candidate_checkpoints": candidates,
            "time_since_last_accepted_s": round(max(0.0, elapsed), 3),
            "distance_since_last_accepted_m": round(self._distance_since_checkpoint_m, 3),
            "explanation": explanation,
            "recommended_operator_action": action,
            "thresholds": {
                "scan_expected_time_s": LOCALIZATION_SCAN_EXPECTED_TIME_S,
                "scan_overdue_time_s": LOCALIZATION_SCAN_OVERDUE_TIME_S,
                "scan_expected_distance_m": LOCALIZATION_SCAN_EXPECTED_DISTANCE_M,
                "scan_overdue_distance_m": LOCALIZATION_SCAN_OVERDUE_DISTANCE_M,
                "candidate_graph_radius_m": LOCALIZATION_CANDIDATE_RADIUS_M,
            },
            "visibility_claimed": False,
        }

    def acknowledge_localization_warning(
        self, warning_key: object, camera_status: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Acknowledge the current warning without changing localization state."""
        health = self.localization_health(camera_status)
        if not isinstance(warning_key, str) or warning_key != health["warning_key"]:
            raise ValueError("warning_key does not match the current localization warning")
        self._acknowledged_localization_warning = warning_key
        return self.snapshot()

    def _wait_for_camera_checkpoint(self, node_id: str) -> bool:
        """Stop at a mapped node until a real camera observation validates it."""
        if not self._camera_mode:
            return False
        checkpoint = self.checkpoints_by_node.get(node_id)
        if checkpoint is None or checkpoint["checkpoint_id"] in self._detected_checkpoint_ids:
            return False
        self._checkpoint_gate = dict(checkpoint)
        self.status = "awaiting_checkpoint"
        self.running = False
        self._record_event(
            "camera_checkpoint_gate_waiting",
            f"Virtual trolley paused; scanning for AprilTag CP{checkpoint['checkpoint_id']}.",
            {"checkpoint_id": checkpoint["checkpoint_id"], "node_id": node_id},
        )
        self._refresh_guidance()
        return True

    def camera_stopped(self) -> dict[str, Any]:
        """Pause an active camera-mode run without fabricating an observation."""
        self._camera_available = False
        if self._camera_mode and self.status == "navigating":
            self.status = "camera_stopped"
            self.running = False
            self._record_event(
                "camera_stopped",
                "Camera stopped; virtual navigation paused until the camera reconnects.",
            )
        return self.snapshot()

    def camera_reconnected(self) -> dict[str, Any]:
        """Resume travel after camera reconnection, preserving any checkpoint gate."""
        self._camera_available = True
        if self._camera_mode and self.status == "camera_stopped":
            self.status = "navigating"
            self.running = True
            self._record_event("camera_reconnected", "Camera reconnected; virtual navigation resumed.")
            self._refresh_guidance()
        return self.snapshot()

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

    def _offer_current_shelf_pickup(self) -> bool:
        """Recognize a newly requested current-shelf item using estimate-only guards."""
        if self.current_node_id == self._deferred_until_leave_node:
            return False
        if self._edge_target is not None or self.status not in {
            "ready", "navigating", "paused", "free_walk_stopped"
        }:
            return False
        product_id = next(
            (
                item_id for item_id in self.shopping_session.remaining_product_ids
                if self.products_by_id[item_id]["pickup_node_id"] == self.current_node_id
            ),
            None,
        )
        if product_id is None:
            return False
        location = self.product_locations[product_id]
        self._update_arrival_monitor()
        self._stationary_arrival_confirmation(location)
        if not self._arrival_state or not self._arrival_state["arrived"]:
            return False
        self.status = "awaiting_product_confirmation"
        self.running = False
        self._arrived_product_id = product_id
        self._arrival_heading_rad = self.estimator.pose.heading_rad
        side = product_shelf_side(
            self._arrival_heading_rad,
            location.pickup_coordinate_m,
            location.shelf_facing_point_m,
        )
        self._record_event(
            "independent_shelf_pickup_ready",
            f"{location.display_name} selected at the current shelf; explicit pickup is required.",
            {
                "product_id": product_id,
                "pickup_node_id": self.current_node_id,
                "arrival": dict(self._arrival_state),
                "shelf_side": side,
            },
        )
        self._publish_guidance(
            "WAIT_FOR_PICKUP",
            self._product_arrival_text(location, side, waiting=True),
            target_node=self.current_node_id,
            product=location,
            shelf_side=side,
        )
        return True

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
        self.shopping_session = ShoppingSession(
            tuple(self.products_by_id), GUIDED_PRODUCT_IDS
        )
        self._sync_legacy_shopping_state()
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
        self.shopping_session = self.shopping_session.clone_for_new_run(
            self.simulation_time_s
        )
        self._sync_legacy_shopping_state()
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

    def enter_free_walk(self) -> dict[str, Any]:
        """Stop route following and allow explicit movement on connected edges."""
        if self._guided_mode or self._camera_mode:
            raise ValueError("Free walk is unavailable during guided or gated camera mode")
        if self.status not in {"ready", "navigating", "paused", "free_walk_stopped"}:
            raise ValueError("Free walk requires a ready or active navigation session")
        self._free_walk_mode = True
        self._free_walk_target_node_id = self._edge_target
        self.running = False
        self.status = "free_walk_stopped"
        self._record_event(
            "free_walk_entered",
            "Free-walk mode entered; movement remains constrained to graph edges.",
            {"available_edges": self.free_walk_options()},
        )
        self._refresh_guidance()
        return self.snapshot()

    def free_walk_options(self) -> list[dict[str, Any]]:
        """Return valid next endpoints without changing state or time."""
        if self._edge_start and self._edge_target:
            return [
                {
                    "node_id": self._edge_start,
                    "distance_m": self._edge_progress_m,
                    "direction": "reverse",
                },
                {
                    "node_id": self._edge_target,
                    "distance_m": self._edge_distance_m - self._edge_progress_m,
                    "direction": "forward",
                },
            ]
        return [
            {"node_id": node_id, "distance_m": distance, "direction": "outbound"}
            for node_id, distance in self.graph.neighbors(self.current_node_id)
        ]

    def choose_free_walk_edge(self, target_node_id: str) -> dict[str, Any]:
        """Select one graph-connected endpoint and start deterministic movement."""
        if not self._free_walk_mode or self.status != "free_walk_stopped":
            raise ValueError("Choose a free-walk edge only while free walk is stopped")
        if not isinstance(target_node_id, str):
            raise ValueError("target_node_id must be a graph node ID")
        if self._edge_start and self._edge_target:
            if target_node_id not in {self._edge_start, self._edge_target}:
                raise ValueError("Mid-edge free walk may continue only to an edge endpoint")
            if target_node_id == self._edge_start:
                self._edge_start, self._edge_target = self._edge_target, self._edge_start
                self._edge_progress_m = self._edge_distance_m - self._edge_progress_m
        else:
            valid_neighbors = {node_id for node_id, _ in self.graph.neighbors(self.current_node_id)}
            if target_node_id not in valid_neighbors:
                raise ValueError(
                    f"Free walk target {target_node_id!r} is not adjacent to {self.current_node_id!r}"
                )
            self._begin_edge(target_node_id)
        self._free_walk_target_node_id = target_node_id
        self.status = "free_walking"
        self.running = True
        self._record_event(
            "free_walk_edge_selected",
            f"Free walk selected connected endpoint {target_node_id}.",
            {"target_node_id": target_node_id},
        )
        self._refresh_guidance()
        return self.snapshot()

    def stop_free_walk(self) -> dict[str, Any]:
        """Stop at the current node or mid-edge position without moving."""
        if not self._free_walk_mode or self.status != "free_walking":
            raise ValueError("Free walk is not currently moving")
        self.running = False
        self.status = "free_walk_stopped"
        self._record_event("free_walk_stopped", "Free-walk movement stopped.")
        self._refresh_guidance()
        return self.snapshot()

    def resume_free_walk(self) -> dict[str, Any]:
        """Resume the previously selected edge direction without advancing time."""
        if not self._free_walk_mode or self.status != "free_walk_stopped":
            raise ValueError("Free walk is not stopped")
        if not self._edge_target or not self._free_walk_target_node_id:
            raise ValueError("Choose a connected edge before resuming free walk")
        self.running = True
        self.status = "free_walking"
        self._record_event("free_walk_resumed", "Free-walk movement resumed.")
        self._refresh_guidance()
        return self.snapshot()

    def request_navigation_from_current_location(self) -> dict[str, Any]:
        """Replan exactly from the current estimated node or mid-edge anchor."""
        if not self._free_walk_mode:
            raise ValueError("Current-location navigation requires free-walk mode")
        anchor = self._estimated_route_anchor()
        plan = self._replan_from_anchor(anchor, reason="navigation_requested_from_current_location")
        if self._edge_start and self._edge_target:
            if plan.chosen_endpoint_node_id == self._edge_start:
                self._edge_start, self._edge_target = self._edge_target, self._edge_start
                self._edge_progress_m = self._edge_distance_m - self._edge_progress_m
            if plan.chosen_endpoint_node_id != self._edge_target:
                raise RuntimeError("Anchored route endpoint is not on the active physical edge")
            self._rejoin_node = plan.chosen_endpoint_node_id
        self._free_walk_mode = False
        self._free_walk_target_node_id = None
        self.status = "navigating"
        self.running = True
        self._record_event(
            "planned_navigation_resumed",
            "Planned navigation resumed from the current route anchor.",
            plan.to_dict(),
        )
        self._refresh_guidance()
        return self.snapshot()

    def _step_free_walk(self, count: int) -> dict[str, Any]:
        """Advance only the explicitly selected graph edge."""
        if self.status != "free_walking" or not self._edge_start or not self._edge_target:
            raise ValueError("Free walk is not moving on a selected edge")
        for _ in range(count):
            self.simulation_time_s = round(self.simulation_time_s + FIXED_TIMESTEP_S, 9)
            movement_m = min(
                self.speed_m_s * FIXED_TIMESTEP_S,
                self._edge_distance_m - self._edge_progress_m,
            )
            self._edge_progress_m += movement_m
            fraction = self._edge_progress_m / self._edge_distance_m
            start = self.graph.node(self._edge_start)
            target = self.graph.node(self._edge_target)
            new_heading = heading_between((start.x_m, start.y_m), (target.x_m, target.y_m))
            yaw_delta = normalize_heading(new_heading - self.estimator.pose.heading_rad)
            self.true_x_m = start.x_m + (target.x_m - start.x_m) * fraction
            self.true_y_m = start.y_m + (target.y_m - start.y_m) * fraction
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
            self._record_sample()
            if self._edge_progress_m + 1e-9 >= self._edge_distance_m:
                arrived = self._edge_target
                self._previous_node_id = self._edge_start
                self.current_node_id = arrived
                self._edge_start = None
                self._edge_target = None
                self._edge_progress_m = 0.0
                self._edge_distance_m = 0.0
                self._free_walk_target_node_id = None
                self.running = False
                self.status = "free_walk_stopped"
                self._record_event(
                    "free_walk_node_reached",
                    f"Free walk reached junction {arrived}; choose the next connected edge.",
                    {"node_id": arrived},
                )
                break
        self._refresh_guidance()
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

    def confirm_product(
        self,
        *,
        automated: bool = False,
        expected_shopping_revision: object | None = None,
        quantity: object = 1,
    ) -> dict[str, Any]:
        """Collect a product only after reaching and confirming its pickup node."""
        if self.status != "awaiting_product_confirmation":
            raise ValueError("No product is currently waiting for pickup confirmation")
        product_id = self._arrived_product_id
        product = self.products_by_id.get(product_id) if product_id else None
        if product is None or product["demo_product_id"] not in self._selected_products:
            raise ValueError("Current location is not a selected product pickup point")
        node_id = product["pickup_node_id"]
        mutation = self.shopping_session.propose(
            "pickup",
            product_id,
            quantity,
            (
                self.shopping_session.revision
                if expected_shopping_revision is None
                else expected_shopping_revision
            ),
        )
        remaining_nodes = self._remaining_nodes_for_lines(mutation.proposed_lines)
        anchor = self._estimated_route_anchor()
        started = time.perf_counter()
        plan = held_karp_route_from_anchor(
            self.graph,
            anchor,
            remaining_nodes,
            self.checkout_node_id,
            allow_reverse=anchor.travel_direction == "stopped",
        )
        computation_ms = (time.perf_counter() - started) * 1000.0
        line = self.shopping_session.commit(mutation, self.simulation_time_s)
        self._sync_legacy_shopping_state()
        if node_id not in remaining_nodes and node_id not in self.route_manager.visited_destinations:
            self.route_manager.visited_destinations.append(node_id)
        self._activate_anchored_plan(
            anchor,
            plan,
            reason="product_pickup_confirmed",
            computation_ms=computation_ms,
            remaining_destinations=remaining_nodes,
            event_details={
                "shopping_revision": self.shopping_session.revision,
                "product_id": product_id,
                "collected_quantity": line.collected_quantity if line else None,
                "remaining_quantity": line.remaining_quantity if line else None,
            },
            count_reroute=False,
            emit_replan_event=False,
            publish_replan_guidance=False,
        )
        product_location = self.product_locations[product_id]
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
                "shopping_revision": self.shopping_session.revision,
                "collected_quantity": line.collected_quantity if line else None,
                "remaining_quantity": line.remaining_quantity if line else None,
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
        next_at_node = next(
            (
                item_id for item_id in self.shopping_session.remaining_product_ids
                if self.products_by_id[item_id]["pickup_node_id"] == node_id
            ),
            None,
        )
        if next_at_node is not None:
            self.status = "awaiting_product_confirmation"
            self.running = False
            self._arrived_product_id = next_at_node
        else:
            self.status = "free_walk_stopped" if self._free_walk_mode else "navigating"
            self.running = not self._free_walk_mode
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

    def skip_product(
        self, decision: object, expected_shopping_revision: object
    ) -> dict[str, Any]:
        """Resolve an arrival without fabricating a pickup or immediately looping."""
        if self.status != "awaiting_product_confirmation" or not self._arrived_product_id:
            raise ValueError("No product is currently waiting for a customer decision")
        if decision not in {"keep_for_later", "remove_remaining"}:
            raise ValueError("skip decision must be 'keep_for_later' or 'remove_remaining'")
        product_id = self._arrived_product_id
        line = self.shopping_session.line(product_id)
        if line is None:
            raise ValueError("Arrived product is no longer on the shopping list")
        if decision == "remove_remaining":
            result = self.mutate_shopping_list(
                "decrease_remaining", product_id, line.remaining_quantity,
                expected_shopping_revision,
            )
            self._record_event(
                "product_skipped_removed",
                f"Customer skipped {self.products_by_id[product_id]['name']} and removed its remaining quantity.",
                {"product_id": product_id, "removed_quantity": line.remaining_quantity},
            )
            return result
        if expected_shopping_revision != self.shopping_session.revision:
            raise ValueError("Shopping-list revision changed before skip decision")

        anchor = node_route_anchor(
            self.graph, self.current_node_id,
            route_revision=self.guidance_engine.route_revision,
        )
        skipped_node = self.products_by_id[product_id]["pickup_node_id"]
        other_nodes = tuple(
            node for node in self._remaining_nodes_for_lines(self.shopping_session.lines)
            if node != skipped_node
        )
        started = time.perf_counter()
        if other_nodes:
            deferred = held_karp_route_from_anchor(
                self.graph, anchor, other_nodes, skipped_node, allow_reverse=True
            )
            checkout_leg = dijkstra_shortest_path(
                self.graph, skipped_node, self.checkout_node_id
            )
            route_nodes = deferred.route_node_ids + checkout_leg.node_ids[1:]
            graph_distance = deferred.graph_route_distance_m + checkout_leg.total_distance_m
            partial_distance = deferred.partial_edge_distance_m
            chosen_endpoint = deferred.chosen_endpoint_node_id
            optimized = deferred.optimized_stop_ids + (skipped_node,)
        else:
            neighbor, edge_distance = self.graph.neighbors(self.current_node_id)[0]
            checkout_leg = dijkstra_shortest_path(
                self.graph, skipped_node, self.checkout_node_id
            )
            route_nodes = (self.current_node_id, neighbor, self.current_node_id) + checkout_leg.node_ids[1:]
            graph_distance = edge_distance * 2.0 + checkout_leg.total_distance_m
            partial_distance = 0.0
            chosen_endpoint = self.current_node_id
            optimized = (skipped_node,)
        plan = AnchoredRoutePlan(
            anchor, chosen_endpoint, partial_distance, optimized,
            route_nodes, graph_distance, graph_distance + partial_distance,
        )
        self.shopping_session.defer_to_end(product_id, self.simulation_time_s)
        self._sync_legacy_shopping_state()
        self._activate_anchored_plan(
            anchor, plan, reason="product_skipped_keep_for_later",
            computation_ms=(time.perf_counter() - started) * 1000.0,
            remaining_destinations=other_nodes + (skipped_node,),
            event_details={"product_id": product_id, "decision": decision},
        )
        self._arrived_product_id = None
        self._deferred_until_leave_node = skipped_node
        self._arrival_state = None
        self.arrival_monitor.reset()
        self.status = "navigating"
        self.running = True
        self._record_event(
            "product_skipped_deferred",
            f"Customer kept {self.products_by_id[product_id]['name']} for later; route now leaves this shelf first.",
            {"product_id": product_id, "decision": decision,
             "shopping_revision": self.shopping_session.revision},
        )
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
        if self.current_node_id == self._deferred_until_leave_node:
            self._deferred_until_leave_node = None
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
        if self._free_walk_mode:
            return self._step_free_walk(count)
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
                if self._wait_for_camera_checkpoint(arrived):
                    break
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
        shopping_line = self.shopping_session.line(location.product_id)
        if shopping_line is not None:
            result.update(
                {
                    "requested_quantity": shopping_line.requested_quantity,
                    "collected_quantity": shopping_line.collected_quantity,
                    "remaining_quantity": shopping_line.remaining_quantity,
                    "product_source": shopping_line.source,
                }
            )
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
        selected_products = [
            {
                **self.products_by_id[product_id],
                "requested_quantity": self.shopping_session.line(product_id).requested_quantity,
                "collected_quantity": self.shopping_session.line(product_id).collected_quantity,
                "remaining_quantity": self.shopping_session.line(product_id).remaining_quantity,
            }
            for product_id in self.shopping_session.remaining_product_ids
        ]
        collected_ids = list(self.shopping_session.collected_product_ids)
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
        shopping_state = self.shopping_session.snapshot(self.products_by_id)
        total_products = int(shopping_state["requested_units"])
        collected_count = int(shopping_state["collected_units"])
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
            "shopping_session": shopping_state,
            "shopping_list_revision": self.shopping_session.revision,
            "recommendations": [
                {
                    **recommendation.to_dict(),
                    "product_name": self.products_by_id[recommendation.product_id]["display_name"],
                    "shelf_section": self.products_by_id[recommendation.product_id]["shelf_section"],
                    "shelf_bay": self.products_by_id[recommendation.product_id]["shelf_bay"],
                    "shelf_level": self.products_by_id[recommendation.product_id]["shelf_level"],
                    "experimental_label": "Experimental recommendation",
                }
                for recommendation in self._recommendations.values()
            ],
            "recommendation_diagnostics": dict(self._recommendation_diagnostics),
            "recommendation_events": list(self._recommendation_events[-100:]),
            "planned_route": route,
            "active_route": route,
            "route_revision": self.guidance_engine.route_revision,
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
            "checkpoint_observation_history": list(
                self._checkpoint_observation_history[-100:]
            ),
            "localization_correction_event": self._last_localization_correction,
            "distance_to_checkpoint_m": checkpoint_distance,
            "detected_checkpoint_ids": list(self._detected_checkpoint_ids),
            "active_apriltag_layout": {
                "layout_id": (self.dense_apriltag_layout or {}).get("layout_id"),
                "schema_version": (self.dense_apriltag_layout or {}).get("schema_version"),
                "mapped_tag_count": len(self.dense_tags_by_id),
                "coverage_report": (self.dense_apriltag_layout or {}).get("coverage_report"),
                "coverage_is_not_detection": True,
            },
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
            "free_walk": {
                "active": self._free_walk_mode,
                "moving": self.status == "free_walking",
                "selected_target_node_id": self._free_walk_target_node_id,
                "available_edges": self.free_walk_options() if self._free_walk_mode else [],
            },
            "route_anchor": self._route_anchor.to_dict() if self._route_anchor else None,
            "last_replanning_reason": self._last_replanning_reason,
            "adaptive_replan_history": list(self._adaptive_replan_history[-100:]),
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
            "camera_evaluation": {
                "active": self._camera_mode,
                "waiting_for_checkpoint": self.status == "awaiting_checkpoint",
                "gate": dict(self._checkpoint_gate) if self._checkpoint_gate else None,
                "virtual_movement": True,
                "manual_pickups": True,
                "camera_frames_uploaded": False,
            },
            "guidance_events": [
                event.to_dict() for event in self.guidance_engine.events[-100:]
            ],
            "reroute_cost_limitation": (
                "Exact partial-edge cost is included; optimization is exact only over "
                "the small set of unique remaining demo pickup nodes."
            ),
            "events": self._events[-100:],
        }
