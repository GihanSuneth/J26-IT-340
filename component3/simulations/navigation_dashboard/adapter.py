"""Adapt the authoritative Component 3 graph and route algorithms for the UI."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Sequence

from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    ShortestPath,
    UnknownNodeError,
    UnreachablePathError,
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    HeldKarpRoute,
    StopLimitExceededError,
    UnreachableLocationError,
    held_karp_route,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    StoreGraph,
    load_store_graph,
)

from .config import (
    APRILTAG_LAYOUT_PATH,
    DEFAULT_DESTINATION_IDS,
    MAX_DESTINATIONS,
    STORE_GRAPH_PATH,
)


class DashboardDataError(ValueError):
    """Raised when source map documents cannot be prepared for display."""


class DashboardRouteError(ValueError):
    """Raised when user-selected destinations cannot produce a valid route."""


@dataclass(frozen=True, slots=True)
class MapProjection:
    """Pixel location using one shared metric scale for both axes."""

    x_px: float
    y_px: float
    scale_px_per_m: float
    offset_x_px: float
    offset_y_px: float


@dataclass(frozen=True, slots=True)
class RoutePlan:
    """Computed route details for the dashboard summary and map."""

    selected_destination_ids: tuple[str, ...]
    optimized_visit_order: tuple[str, ...]
    route_node_ids: tuple[str, ...]
    total_distance_m: float
    leg_paths: tuple[ShortestPath, ...]


def load_dashboard_data(
    graph_path: str | Path = STORE_GRAPH_PATH,
    tag_layout_path: str | Path = APRILTAG_LAYOUT_PATH,
) -> dict[str, Any]:
    """Load existing graph/tag documents and expose only mapped destinations."""
    try:
        with Path(graph_path).open(encoding="utf-8") as handle:
            raw_graph = json.load(handle)
        with Path(tag_layout_path).open(encoding="utf-8") as handle:
            tag_document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardDataError(f"Unable to load dashboard map data: {exc}") from exc
    if not isinstance(raw_graph, dict) or not isinstance(tag_document, dict):
        raise DashboardDataError("Map and AprilTag documents must be JSON objects")

    graph = load_store_graph(graph_path)
    dimensions = raw_graph.get("dimensions_m")
    sections = raw_graph.get("sections")
    raw_tags = tag_document.get("tags")
    if (
        not isinstance(dimensions, dict)
        or not isinstance(sections, list)
        or not isinstance(raw_tags, list)
    ):
        raise DashboardDataError("Map dimensions, sections, or tag list are invalid")
    width_m = _finite_positive(dimensions.get("width"), "store width")
    height_m = _finite_positive(dimensions.get("height"), "store height")
    entrance_ids = tuple(
        node.node_id for node in graph.nodes.values() if node.node_type == "entrance"
    )
    checkout_ids = tuple(
        node.node_id for node in graph.nodes.values() if node.node_type == "checkout"
    )
    if len(entrance_ids) != 1 or len(checkout_ids) != 1:
        raise DashboardDataError("Map must define exactly one entrance and checkout")

    aisle_destinations: list[dict[str, str]] = []
    category_labels: list[dict[str, str]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise DashboardDataError("Every map section must be an object")
        section_id = section.get("id")
        section_name = section.get("name")
        access_node_ids = section.get("access_node_ids")
        if (
            not isinstance(section_id, str)
            or not isinstance(section_name, str)
            or not isinstance(access_node_ids, list)
            or not access_node_ids
        ):
            raise DashboardDataError("Map section has invalid destination metadata")
        for node_id in access_node_ids:
            if not isinstance(node_id, str) or node_id not in graph:
                raise DashboardDataError(
                    f"Section {section_id!r} references an unknown graph node"
                )
        destination_id = access_node_ids[0]
        aisle_destinations.append(
            {
                "node_id": destination_id,
                "section_id": section_id,
                "section_name": section_name,
                "node_name": graph.node(destination_id).name,
            }
        )
        label_node_id = access_node_ids[len(access_node_ids) // 2]
        category_labels.append(
            {
                "section_id": section_id,
                "section_name": section_name,
                "node_id": label_node_id,
            }
        )

    if not aisle_destinations:
        raise DashboardDataError("Map contains no mapped aisle destinations")
    tags: list[dict[str, Any]] = []
    for tag in raw_tags:
        if not isinstance(tag, dict):
            raise DashboardDataError("Every AprilTag layout entry must be an object")
        node_id = tag.get("node_id")
        if not isinstance(node_id, str) or node_id not in graph:
            raise DashboardDataError("AprilTag layout references an unknown graph node")
        x_m = _finite_number(tag.get("x_m"), "AprilTag x coordinate")
        y_m = _finite_number(tag.get("y_m"), "AprilTag y coordinate")
        if not math.isclose(x_m, graph.node(node_id).x_m) or not math.isclose(
            y_m, graph.node(node_id).y_m
        ):
            raise DashboardDataError(
                f"AprilTag coordinates disagree with graph node {node_id!r}"
            )
        tags.append(
            {
                "tag_id": tag.get("tag_id"),
                "node_id": node_id,
                "x_m": x_m,
                "y_m": y_m,
                "location_name": tag.get("location_name", node_id),
            }
        )

    product_locations = raw_graph.get("product_locations", [])
    if not isinstance(product_locations, list):
        raise DashboardDataError("Product-location mappings must be a list")
    nodes = [
        {
            "node_id": node.node_id,
            "name": node.name,
            "node_type": node.node_type,
            "x_m": node.x_m,
            "y_m": node.y_m,
            "aisle_ref": node.aisle_ref,
        }
        for node in graph.nodes.values()
    ]
    edges = [
        {"source": edge.source, "target": edge.target}
        for edge in graph.edges
    ]
    return {
        "dimensions_m": {"width": width_m, "height": height_m},
        "coordinate_system": raw_graph.get("coordinate_system", {}),
        "nodes": nodes,
        "edges": edges,
        "sections": category_labels,
        "destinations": aisle_destinations,
        "tags": tags,
        "entrance_node_id": entrance_ids[0],
        "checkout_node_id": checkout_ids[0],
        "product_location_count": len(product_locations),
        "default_destination_ids": list(DEFAULT_DESTINATION_IDS),
        "max_destinations": MAX_DESTINATIONS,
        "prototype_notice": raw_graph.get("prototype_notice", ""),
    }


def _finite_number(value: Any, name: str) -> float:
    """Return a finite number or raise a clear map-data error."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DashboardDataError(f"{name} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise DashboardDataError(f"{name} must be finite")
    return converted


def _finite_positive(value: Any, name: str) -> float:
    """Return a finite positive map dimension."""
    converted = _finite_number(value, name)
    if converted <= 0:
        raise DashboardDataError(f"{name} must be positive")
    return converted


def project_map_coordinate(
    x_m: float,
    y_m: float,
    *,
    width_m: float,
    height_m: float,
    viewport_width_px: float,
    viewport_height_px: float,
) -> MapProjection:
    """Project metric coordinates into a letterboxed, equal-scale viewport."""
    values = (x_m, y_m, width_m, height_m, viewport_width_px, viewport_height_px)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Map coordinates and viewport dimensions must be finite")
    if min(width_m, height_m, viewport_width_px, viewport_height_px) <= 0:
        raise ValueError("Map and viewport dimensions must be positive")
    if not 0 <= x_m <= width_m or not 0 <= y_m <= height_m:
        raise ValueError("Map coordinates must lie within the store boundary")
    scale = min(viewport_width_px / width_m, viewport_height_px / height_m)
    offset_x = (viewport_width_px - width_m * scale) / 2.0
    offset_y = (viewport_height_px - height_m * scale) / 2.0
    return MapProjection(
        x_px=offset_x + x_m * scale,
        y_px=offset_y + (height_m - y_m) * scale,
        scale_px_per_m=scale,
        offset_x_px=offset_x,
        offset_y_px=offset_y,
    )


def validate_destinations(
    selected_node_ids: Sequence[str],
    map_data: dict[str, Any],
) -> tuple[str, ...]:
    """Validate aisle destinations and remove duplicates while preserving order."""
    if isinstance(selected_node_ids, (str, bytes)):
        raise DashboardRouteError("Select a list of mapped aisle destinations")
    destinations = map_data.get("destinations")
    if not isinstance(destinations, list):
        raise DashboardRouteError("Mapped aisle destinations are unavailable")
    valid_ids = {
        item["node_id"]
        for item in destinations
        if isinstance(item, dict) and isinstance(item.get("node_id"), str)
    }
    unique: list[str] = []
    for node_id in selected_node_ids:
        if not isinstance(node_id, str) or node_id not in valid_ids:
            raise DashboardRouteError(f"Unknown or unmapped aisle destination: {node_id!r}")
        if node_id not in unique:
            unique.append(node_id)
    if len(unique) > MAX_DESTINATIONS:
        raise DashboardRouteError(
            f"Select no more than {MAX_DESTINATIONS} unique destinations"
        )
    return tuple(unique)


def calculate_route(
    graph: StoreGraph,
    selected_node_ids: Sequence[str],
    *,
    valid_destination_ids: Sequence[str],
    start_node_id: str = "ENT",
    checkout_node_id: str = "CHK",
) -> RoutePlan:
    """Use Held-Karp and Dijkstra to construct the optimized graph path."""
    valid_set = set(valid_destination_ids)
    if isinstance(selected_node_ids, (str, bytes)):
        raise DashboardRouteError("Destinations must be a sequence of graph node IDs")
    selected: list[str] = []
    for node_id in selected_node_ids:
        if not isinstance(node_id, str) or node_id not in valid_set or node_id not in graph:
            raise DashboardRouteError(f"Unknown or unmapped aisle destination: {node_id!r}")
        if node_id not in selected:
            selected.append(node_id)
    if len(selected) > MAX_DESTINATIONS:
        raise DashboardRouteError(
            f"Select no more than {MAX_DESTINATIONS} unique destinations"
        )
    try:
        optimized: HeldKarpRoute = held_karp_route(
            graph, start_node_id, selected, checkout_node_id
        )
        location_order = (
            start_node_id,
            *optimized.optimized_stop_ids,
            checkout_node_id,
        )
        legs = tuple(
            dijkstra_shortest_path(graph, source, destination)
            for source, destination in zip(location_order, location_order[1:])
        )
    except (UnknownNodeError, UnreachablePathError, UnreachableLocationError,
            StopLimitExceededError) as exc:
        raise DashboardRouteError(f"Unable to calculate route: {exc}") from exc
    route_nodes: list[str] = []
    for leg in legs:
        route_nodes.extend(leg.node_ids if not route_nodes else leg.node_ids[1:])
    if not route_nodes:
        route_nodes.append(start_node_id)
    if route_nodes[-1] != checkout_node_id:
        raise DashboardRouteError("Calculated route does not end at checkout")
    leg_distance_m = sum(leg.total_distance_m for leg in legs)
    if not math.isclose(leg_distance_m, optimized.total_distance_m, abs_tol=1e-9):
        raise DashboardRouteError("Dijkstra legs disagree with Held-Karp distance")
    return RoutePlan(
        selected_destination_ids=tuple(selected),
        optimized_visit_order=optimized.optimized_stop_ids,
        route_node_ids=tuple(route_nodes),
        total_distance_m=optimized.total_distance_m,
        leg_paths=legs,
    )


def calculate_dashboard_route(
    map_data: dict[str, Any],
    selected_node_ids: Sequence[str],
    graph: StoreGraph | None = None,
) -> RoutePlan:
    """Validate dashboard choices and calculate with the loaded store graph."""
    valid_selection = validate_destinations(selected_node_ids, map_data)
    if graph is None:
        graph = load_store_graph(STORE_GRAPH_PATH)
    return calculate_route(
        graph,
        valid_selection,
        valid_destination_ids=tuple(
            item["node_id"] for item in map_data["destinations"]
        ),
        start_node_id=map_data["entrance_node_id"],
        checkout_node_id=map_data["checkout_node_id"],
    )
