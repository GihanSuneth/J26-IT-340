"""Recommendation-to-dashboard contract helpers.

Model output remains inert. The existing ``accept_recommendation`` session command is
the only operation that adds a suggestion and atomically recalculates the route.
"""

from __future__ import annotations

import math
from typing import Mapping


MAPPING_STATUSES = {
    "exact_verified_mapping", "normalized_name_mapping",
    "category_level_mapping", "unmapped_product",
}
SHELF_AVAILABILITY = {"available", "unavailable", "unknown"}


def validate_recommendation_output(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate one candidate before it is exposed to the customer dashboard."""
    required = {
        "recommendation_id", "product_id", "recommendation_source", "model_version",
        "score", "mapping_status", "shelf_availability", "navigation_eligible",
        "acceptance_status",
    }
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"missing recommendation fields: {sorted(missing)}")
    for key in ("recommendation_id", "product_id", "recommendation_source"):
        if not isinstance(payload[key], str) or not payload[key]:
            raise ValueError(f"{key} must be a non-empty string")
    score = payload["score"]
    if score is not None and (
        isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
    ):
        raise ValueError("score must be finite or null")
    if payload["mapping_status"] not in MAPPING_STATUSES:
        raise ValueError("invalid mapping_status")
    if payload["shelf_availability"] not in SHELF_AVAILABILITY:
        raise ValueError("invalid shelf_availability")
    if not isinstance(payload["navigation_eligible"], bool):
        raise ValueError("navigation_eligible must be boolean")
    if payload["acceptance_status"] not in {"pending", "accepted", "rejected"}:
        raise ValueError("invalid acceptance_status")
    if payload["navigation_eligible"]:
        if payload["mapping_status"] not in {"exact_verified_mapping", "normalized_name_mapping"}:
            raise ValueError("category-level or unmapped products cannot be navigable")
        if payload["shelf_availability"] != "available":
            raise ValueError("navigable recommendations require an available shelf")
        if not payload.get("shelf_id") or not payload.get("pickup_node_id"):
            raise ValueError("navigable recommendations require shelf and pickup node")
    detour = payload.get("route_detour_cost_m")
    if detour is not None and (
        isinstance(detour, bool) or not isinstance(detour, (int, float))
        or not math.isfinite(detour) or detour < 0
    ):
        raise ValueError("route_detour_cost_m must be finite and nonnegative or null")
    return dict(payload)
