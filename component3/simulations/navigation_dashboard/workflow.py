"""Public, event-driven workflow contract for trolley navigation clients."""

from __future__ import annotations

from enum import StrEnum


class NavigationState(StrEnum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    NAVIGATING = "NAVIGATING"
    WAITING_FOR_LOCALIZATION = "WAITING_FOR_LOCALIZATION"
    ARRIVED_AT_PRODUCT = "ARRIVED_AT_PRODUCT"
    AWAITING_CUSTOMER_DECISION = "AWAITING_CUSTOMER_DECISION"
    REPLANNING = "REPLANNING"
    CHECKOUT_READY = "CHECKOUT_READY"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


ALLOWED_TRANSITIONS = {
    NavigationState.IDLE: {NavigationState.PLANNING, NavigationState.NAVIGATING},
    NavigationState.PLANNING: {NavigationState.NAVIGATING, NavigationState.ERROR},
    NavigationState.NAVIGATING: {
        NavigationState.WAITING_FOR_LOCALIZATION,
        NavigationState.ARRIVED_AT_PRODUCT,
        NavigationState.CHECKOUT_READY,
        NavigationState.PAUSED,
        NavigationState.REPLANNING,
        NavigationState.COMPLETED,
        NavigationState.ERROR,
    },
    NavigationState.WAITING_FOR_LOCALIZATION: {
        NavigationState.NAVIGATING, NavigationState.PAUSED, NavigationState.ERROR
    },
    NavigationState.ARRIVED_AT_PRODUCT: {NavigationState.AWAITING_CUSTOMER_DECISION},
    NavigationState.AWAITING_CUSTOMER_DECISION: {
        NavigationState.REPLANNING, NavigationState.NAVIGATING,
        NavigationState.CHECKOUT_READY, NavigationState.ERROR,
    },
    NavigationState.REPLANNING: {
        NavigationState.NAVIGATING, NavigationState.CHECKOUT_READY, NavigationState.ERROR
    },
    NavigationState.CHECKOUT_READY: {
        NavigationState.NAVIGATING, NavigationState.COMPLETED, NavigationState.PAUSED
    },
    NavigationState.PAUSED: {
        NavigationState.NAVIGATING, NavigationState.WAITING_FOR_LOCALIZATION,
        NavigationState.IDLE,
    },
    NavigationState.ERROR: {NavigationState.IDLE, NavigationState.PLANNING},
    NavigationState.COMPLETED: {NavigationState.IDLE, NavigationState.PLANNING},
}


def public_state(status: str, *, has_remaining_products: bool) -> NavigationState:
    """Translate legacy engine status into the stable client-facing state machine."""
    if status == "ready":
        return NavigationState.IDLE
    if status in {"awaiting_checkpoint", "camera_stopped", "localization_uncertain"}:
        return NavigationState.WAITING_FOR_LOCALIZATION
    if status == "awaiting_product_confirmation":
        return NavigationState.AWAITING_CUSTOMER_DECISION
    if status in {"paused", "free_walk_stopped"}:
        return NavigationState.PAUSED
    if status in {"navigation_error", "reroute_failed", "location_unavailable"}:
        return NavigationState.ERROR
    if status == "complete":
        return NavigationState.COMPLETED
    if status in {"navigating", "free_walking"} and not has_remaining_products:
        return NavigationState.CHECKOUT_READY
    return NavigationState.NAVIGATING


def contract() -> dict[str, object]:
    return {
        "version": "1.0",
        "states": [state.value for state in NavigationState],
        "allowed_transitions": {
            state.value: sorted(target.value for target in targets)
            for state, targets in ALLOWED_TRANSITIONS.items()
        },
    }
