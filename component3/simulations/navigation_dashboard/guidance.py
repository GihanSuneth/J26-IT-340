"""Structured, geometry-derived guidance and shelf-arrival support."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping, Sequence

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    normalize_heading,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import StoreGraph


STRAIGHT_TOLERANCE_DEG = 35.0
U_TURN_TOLERANCE_DEG = 145.0
TURN_NOTICE_DISTANCE_M = 1.25
CHECKPOINT_NOTICE_DISTANCE_M = 1.5
PRODUCT_NOTICE_DISTANCE_M = 2.0
SHELF_SIDE_AMBIGUITY_DEG = 10.0
PRODUCT_ARRIVAL_RADIUS_M = 1.0
PRODUCT_ARRIVAL_CONFIRMATIONS = 2
MAX_ARRIVAL_UNCERTAINTY_M = 0.75

INSTRUCTION_TYPES = frozenset(
    {
        "START",
        "STRAIGHT",
        "TURN_LEFT",
        "TURN_RIGHT",
        "U_TURN",
        "APPROACH_CHECKPOINT",
        "CHECKPOINT_CONFIRMED",
        "APPROACH_PRODUCT",
        "PRODUCT_REACHED",
        "WAIT_FOR_PICKUP",
        "PICKUP_CONFIRMED",
        "REROUTING",
        "LOCALIZATION_UNCERTAIN",
        "PROCEED_TO_CHECKOUT",
        "ARRIVED_CHECKOUT",
    }
)


@dataclass(frozen=True, slots=True)
class ProductLocation:
    """Validated synthetic product-to-shelf location exposed to guidance."""

    available: bool
    product_id: str
    display_name: str
    category: str | None = None
    shelf_id: str | None = None
    shelf_section: str | None = None
    shelf_level: int | None = None
    shelf_bay: int | None = None
    pickup_node: str | None = None
    pickup_coordinate_m: tuple[float, float] | None = None
    shelf_facing_point_m: tuple[float, float] | None = None
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        result = asdict(self)
        for key in ("pickup_coordinate_m", "shelf_facing_point_m"):
            if result[key] is not None:
                result[key] = list(result[key])
        return result


def resolve_product_location(
    product: Mapping[str, Any],
    shelves_by_id: Mapping[str, Mapping[str, Any]],
    graph: StoreGraph,
) -> ProductLocation:
    """Resolve one record or return an explicit unavailable-location state."""
    product_id = product.get("product_id") or product.get("demo_product_id")
    display_name = product.get("display_name") or product.get("name")
    if not isinstance(product_id, str) or not product_id:
        return ProductLocation(False, "unknown", str(display_name or "Unknown product"), unavailable_reason="missing_product_id")
    if not isinstance(display_name, str) or not display_name.strip():
        return ProductLocation(False, product_id, "Unknown product", unavailable_reason="missing_display_name")
    shelf_id = product.get("shelf_id")
    shelf = shelves_by_id.get(shelf_id) if isinstance(shelf_id, str) else None
    if shelf is None:
        return ProductLocation(False, product_id, display_name, unavailable_reason="missing_shelf")
    pickup_node = product.get("pickup_node") or product.get("pickup_node_id")
    if not isinstance(pickup_node, str) or pickup_node not in graph:
        return ProductLocation(False, product_id, display_name, unavailable_reason="unreachable_pickup")
    level = product.get("shelf_level")
    level_count = shelf.get("level_count")
    if (
        isinstance(level, bool)
        or not isinstance(level, int)
        or isinstance(level_count, bool)
        or not isinstance(level_count, int)
        or not 1 <= level <= level_count
    ):
        return ProductLocation(False, product_id, display_name, unavailable_reason="invalid_shelf_level")
    raw_facing = product.get("shelf_facing_point_m")
    if not (
        isinstance(raw_facing, list)
        and len(raw_facing) == 2
        and all(
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            for value in raw_facing
        )
    ):
        return ProductLocation(False, product_id, display_name, unavailable_reason="missing_shelf_orientation")
    pickup = graph.node(pickup_node)
    return ProductLocation(
        available=True,
        product_id=product_id,
        display_name=display_name,
        category=str(product.get("category")) if product.get("category") is not None else None,
        shelf_id=shelf_id,
        shelf_section=str(product.get("shelf_section")),
        shelf_level=level,
        shelf_bay=product.get("shelf_bay"),
        pickup_node=pickup_node,
        pickup_coordinate_m=(pickup.x_m, pickup.y_m),
        shelf_facing_point_m=(float(raw_facing[0]), float(raw_facing[1])),
    )


def classify_turn(
    incoming_heading_rad: float,
    outgoing_heading_rad: float,
    *,
    straight_tolerance_deg: float = STRAIGHT_TOLERANCE_DEG,
    u_turn_tolerance_deg: float = U_TURN_TOLERANCE_DEG,
) -> str:
    """Classify the signed angle between two real route segment headings."""
    values = (incoming_heading_rad, outgoing_heading_rad)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("turn headings must be finite numbers")
    if not 0 <= straight_tolerance_deg < u_turn_tolerance_deg <= 180:
        raise ValueError("turn angle tolerances must satisfy 0 <= straight < U-turn <= 180")
    degrees = math.degrees(normalize_heading(outgoing_heading_rad - incoming_heading_rad))
    if abs(degrees) <= straight_tolerance_deg:
        return "STRAIGHT"
    if abs(degrees) >= u_turn_tolerance_deg:
        return "U_TURN"
    return "TURN_LEFT" if degrees > 0 else "TURN_RIGHT"


def product_shelf_side(
    approach_heading_rad: float,
    pickup_coordinate_m: tuple[float, float],
    shelf_facing_point_m: tuple[float, float],
    *,
    ambiguity_deg: float = SHELF_SIDE_AMBIGUITY_DEG,
) -> str | None:
    """Return left/right from signed geometry, or None when orientation is ambiguous."""
    if (
        isinstance(approach_heading_rad, bool)
        or not isinstance(approach_heading_rad, (int, float))
        or not math.isfinite(approach_heading_rad)
        or not 0 <= ambiguity_deg < 90
    ):
        return None
    px, py = pickup_coordinate_m
    sx, sy = shelf_facing_point_m
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in (px, py, sx, sy)
    ):
        return None
    shelf_dx, shelf_dy = sx - px, sy - py
    magnitude = math.hypot(shelf_dx, shelf_dy)
    if magnitude <= 1e-9:
        return None
    heading_x, heading_y = math.cos(approach_heading_rad), math.sin(approach_heading_rad)
    normalized_cross = (heading_x * shelf_dy - heading_y * shelf_dx) / magnitude
    if abs(normalized_cross) <= math.sin(math.radians(ambiguity_deg)):
        return None
    return "left" if normalized_cross > 0 else "right"


@dataclass(frozen=True, slots=True)
class ArrivalState:
    """One stable estimate-based product-arrival decision."""

    target_product_id: str
    distance_m: float
    arrival_radius_m: float
    localization_uncertainty_m: float
    consecutive_inside_samples: int
    arrived: bool
    newly_arrived: bool
    localization_uncertain: bool


class ProductArrivalMonitor:
    """Confirm shelf arrival from estimated position without using truth coordinates."""

    def __init__(
        self,
        *,
        arrival_radius_m: float = PRODUCT_ARRIVAL_RADIUS_M,
        confirmations: int = PRODUCT_ARRIVAL_CONFIRMATIONS,
        max_uncertainty_m: float = MAX_ARRIVAL_UNCERTAINTY_M,
    ) -> None:
        if arrival_radius_m <= 0 or max_uncertainty_m <= 0 or confirmations < 1:
            raise ValueError("arrival settings must be positive")
        self.arrival_radius_m = float(arrival_radius_m)
        self.confirmations = int(confirmations)
        self.max_uncertainty_m = float(max_uncertainty_m)
        self.reset()

    def reset(self, target_product_id: str | None = None) -> None:
        """Reset confirmation state for a new destination."""
        self._target_product_id = target_product_id
        self._inside_count = 0
        self._arrived = False

    def update(
        self,
        *,
        target_product_id: str,
        estimated_position_m: tuple[float, float],
        pickup_coordinate_m: tuple[float, float],
        localization_uncertainty_m: float,
    ) -> ArrivalState:
        """Update stable arrival state using estimate, configured pickup, and uncertainty."""
        if target_product_id != self._target_product_id:
            self.reset(target_product_id)
        values = (*estimated_position_m, *pickup_coordinate_m, localization_uncertainty_m)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("arrival position and uncertainty values must be finite")
        if localization_uncertainty_m < 0:
            raise ValueError("localization uncertainty cannot be negative")
        distance = math.hypot(
            estimated_position_m[0] - pickup_coordinate_m[0],
            estimated_position_m[1] - pickup_coordinate_m[1],
        )
        uncertain = localization_uncertainty_m > self.max_uncertainty_m
        newly_arrived = False
        if uncertain:
            self._inside_count = 0
        elif distance <= self.arrival_radius_m:
            self._inside_count += 1
            if not self._arrived and self._inside_count >= self.confirmations:
                self._arrived = True
                newly_arrived = True
        else:
            self._inside_count = 0
        return ArrivalState(
            target_product_id=target_product_id,
            distance_m=distance,
            arrival_radius_m=self.arrival_radius_m,
            localization_uncertainty_m=localization_uncertainty_m,
            consecutive_inside_samples=self._inside_count,
            arrived=self._arrived,
            newly_arrived=newly_arrived,
            localization_uncertain=uncertain,
        )


@dataclass(frozen=True, slots=True)
class GuidanceEvent:
    """Structured customer-facing instruction derived from current state."""

    instruction_type: str
    instruction_text: str
    distance_to_maneuver_m: float
    target_node: str | None
    target_product_id: str | None
    target_shelf_id: str | None
    timestamp: float
    event_id: str
    route_revision: int
    shelf_side: str | None = None
    shelf_section: str | None = None
    shelf_level: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe event plus backward-compatible display aliases."""
        result = asdict(self)
        result["instruction"] = self.instruction_text
        result["maneuver"] = self.instruction_type.replace("_", " ").title()
        return result


class GuidanceEngine:
    """Generate current guidance and publish only meaningful event transitions."""

    def __init__(self, graph: StoreGraph) -> None:
        self.graph = graph
        self.reset()

    def reset(self) -> None:
        """Reset deterministic event IDs and route revision."""
        self.route_revision = 0
        self._sequence = 0
        self._last_identity: tuple[Any, ...] | None = None
        self.current_event: GuidanceEvent | None = None
        self.events: list[GuidanceEvent] = []

    def route_changed(self) -> None:
        """Invalidate prior maneuver identity after a replacement route."""
        self.route_revision += 1
        self._last_identity = None

    def publish(
        self,
        instruction_type: str,
        instruction_text: str,
        *,
        timestamp: float,
        distance_to_maneuver_m: float = 0.0,
        target_node: str | None = None,
        product: ProductLocation | None = None,
        shelf_side: str | None = None,
        identity_detail: str | None = None,
    ) -> tuple[GuidanceEvent, bool]:
        """Publish a structured transition once while refreshing live distance."""
        if instruction_type not in INSTRUCTION_TYPES:
            raise ValueError(f"Unsupported guidance instruction type: {instruction_type}")
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("guidance timestamp must be a finite nonnegative number")
        if not math.isfinite(distance_to_maneuver_m) or distance_to_maneuver_m < 0:
            raise ValueError("guidance distance must be a finite nonnegative number")
        identity = (
            self.route_revision,
            instruction_type,
            target_node,
            product.product_id if product else None,
            identity_detail,
        )
        is_new = identity != self._last_identity
        if is_new:
            self._sequence += 1
            self._last_identity = identity
        event_id = f"GUIDE-{self.route_revision:02d}-{self._sequence:04d}"
        event = GuidanceEvent(
            instruction_type=instruction_type,
            instruction_text=instruction_text,
            distance_to_maneuver_m=distance_to_maneuver_m,
            target_node=target_node,
            target_product_id=product.product_id if product else None,
            target_shelf_id=product.shelf_id if product else None,
            timestamp=timestamp,
            event_id=event_id,
            route_revision=self.route_revision,
            shelf_side=shelf_side,
            shelf_section=product.shelf_section if product else None,
            shelf_level=product.shelf_level if product else None,
        )
        self.current_event = event
        if is_new:
            self.events.append(event)
        return event, is_new

    def navigation_instruction(
        self,
        *,
        timestamp: float,
        estimated_heading_rad: float,
        remaining_route: Sequence[str],
        distance_to_route_start_m: float,
        active_product: ProductLocation | None,
        distance_to_product_m: float | None,
        next_checkpoint: Mapping[str, Any] | None,
        distance_to_checkpoint_m: float | None,
        localization_uncertain: bool,
    ) -> tuple[GuidanceEvent, bool]:
        """Derive live route guidance from segment vectors and current distances."""
        target_node = active_product.pickup_node if active_product else None
        if localization_uncertain:
            return self.publish(
                "LOCALIZATION_UNCERTAIN",
                "Localization is uncertain. Confirm your position before continuing.",
                timestamp=timestamp,
                target_node=target_node,
                product=active_product,
            )
        route = list(remaining_route)
        incoming = estimated_heading_rad
        cumulative = max(0.0, distance_to_route_start_m)
        maneuver_type: str | None = None
        maneuver_node: str | None = None
        for index in range(len(route) - 1):
            start = self.graph.node(route[index])
            end = self.graph.node(route[index + 1])
            outgoing = math.atan2(end.y_m - start.y_m, end.x_m - start.x_m)
            candidate = classify_turn(incoming, outgoing)
            if candidate != "STRAIGHT":
                maneuver_type = candidate
                maneuver_node = route[index]
                break
            cumulative += self.graph.edge_weight(route[index], route[index + 1])
            incoming = outgoing
        if maneuver_type and cumulative <= TURN_NOTICE_DISTANCE_M:
            text = {
                "TURN_LEFT": "Turn left",
                "TURN_RIGHT": "Turn right",
                "U_TURN": "Make a U-turn",
            }[maneuver_type]
            return self.publish(
                maneuver_type,
                f"{text} at {maneuver_node}.",
                timestamp=timestamp,
                distance_to_maneuver_m=cumulative,
                target_node=maneuver_node,
                product=active_product,
            )
        if (
            next_checkpoint is not None
            and distance_to_checkpoint_m is not None
            and distance_to_checkpoint_m <= CHECKPOINT_NOTICE_DISTANCE_M
        ):
            checkpoint_id = next_checkpoint.get("checkpoint_id")
            return self.publish(
                "APPROACH_CHECKPOINT",
                f"Approaching checkpoint CP{checkpoint_id}.",
                timestamp=timestamp,
                distance_to_maneuver_m=distance_to_checkpoint_m,
                target_node=next_checkpoint.get("node_id"),
                product=active_product,
                identity_detail=str(checkpoint_id),
            )
        if (
            active_product is not None
            and distance_to_product_m is not None
            and distance_to_product_m <= PRODUCT_NOTICE_DISTANCE_M
        ):
            return self.publish(
                "APPROACH_PRODUCT",
                f"Approach {active_product.display_name} at {active_product.shelf_id}.",
                timestamp=timestamp,
                distance_to_maneuver_m=distance_to_product_m,
                target_node=active_product.pickup_node,
                product=active_product,
            )
        if maneuver_type:
            next_word = {
                "TURN_LEFT": "a left turn",
                "TURN_RIGHT": "a right turn",
                "U_TURN": "a U-turn",
            }[maneuver_type]
            return self.publish(
                "STRAIGHT",
                f"Continue straight for {cumulative:.1f} m, then make {next_word}.",
                timestamp=timestamp,
                distance_to_maneuver_m=cumulative,
                target_node=maneuver_node,
                product=active_product,
            )
        if active_product is not None:
            distance = max(0.0, distance_to_product_m or 0.0)
            return self.publish(
                "STRAIGHT",
                f"Continue straight toward {active_product.display_name} at {active_product.shelf_id}.",
                timestamp=timestamp,
                distance_to_maneuver_m=distance,
                target_node=active_product.pickup_node,
                product=active_product,
            )
        return self.publish(
            "PROCEED_TO_CHECKOUT",
            "Proceed to checkout.",
            timestamp=timestamp,
            distance_to_maneuver_m=max(0.0, distance_to_route_start_m),
            target_node=route[-1] if route else None,
        )
