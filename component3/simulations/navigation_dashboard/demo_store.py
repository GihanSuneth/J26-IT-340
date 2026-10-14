"""Load, derive, and validate the versioned synthetic demonstration store."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping

from component3.backend.comp3_reco_navigation.navigation.apriltag import (
    AprilTagLayout,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (
    GraphValidationError,
    StoreGraph,
)


DEFAULT_DEMO_MAP_PATH = (
    Path(__file__).resolve().parents[2] / "data/demo_store/v1/demo_store.json"
)


class DemoMapValidationError(ValueError):
    """Raised when synthetic store geometry or mapping data is invalid."""


@dataclass(frozen=True, slots=True)
class DemoStore:
    """Validated navigation graph, map drawing data, and simulated tag layout."""

    graph: StoreGraph
    data: dict[str, Any]
    checkpoint_layout: AprilTagLayout


def _number(value: object, label: str) -> float:
    """Validate and return one finite, non-boolean map coordinate."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemoMapValidationError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise DemoMapValidationError(f"{label} must be a finite number")
    return result


def _inside_shelf(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    bounds: tuple[float, float, float, float],
) -> bool:
    """Return whether an axis-aligned graph segment intersects a shelf interior."""
    left, bottom, right, top = bounds
    if math.isclose(y1, y2):
        return bottom < y1 < top and max(min(x1, x2), left) < min(max(x1, x2), right)
    if math.isclose(x1, x2):
        return left < x1 < right and max(min(y1, y2), bottom) < min(max(y1, y2), top)
    return True


def build_demo_store(raw: Mapping[str, Any]) -> DemoStore:
    """Derive the synthetic graph and reject unsafe or inconsistent geometry."""
    if raw.get("schema_version") != "1.0":
        raise DemoMapValidationError("Unsupported synthetic map schema_version")
    if raw.get("data_classification") != "synthetic_demonstration_only":
        raise DemoMapValidationError("Map must be classified as synthetic demonstration data")
    boundary = raw.get("boundary_m")
    lanes = raw.get("walkable_lanes")
    if not isinstance(boundary, Mapping) or not isinstance(lanes, Mapping):
        raise DemoMapValidationError("Map must define boundary_m and walkable_lanes")
    width = _number(boundary.get("width"), "boundary width")
    height = _number(boundary.get("height"), "boundary height")
    lane_width = _number(lanes.get("width_m"), "lane width")
    raw_columns = lanes.get("columns_x_m")
    raw_rows = lanes.get("rows_y_m")
    raw_cross_columns = lanes.get("cross_aisle_columns")
    if not all(isinstance(value, list) for value in (raw_columns, raw_rows, raw_cross_columns)):
        raise DemoMapValidationError("Lane columns, rows, and cross-aisle indices must be lists")
    columns = tuple(_number(value, "lane column") for value in raw_columns)
    rows = tuple(_number(value, "lane row") for value in raw_rows)
    cross_columns = tuple(raw_cross_columns)
    if width <= 0 or height <= 0 or lane_width <= 0 or not columns or not rows:
        raise DemoMapValidationError("Boundary and lane dimensions must be positive")
    if tuple(sorted(set(columns))) != columns or tuple(sorted(set(rows))) != rows:
        raise DemoMapValidationError("Lane coordinates must be strictly increasing")
    if any(
        isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(columns)
        for index in cross_columns
    ):
        raise DemoMapValidationError("Cross-aisle columns must reference lane columns")
    if len(set(cross_columns)) != len(cross_columns):
        raise DemoMapValidationError("Cross-aisle indices must be unique")
    if any(not 0 <= x <= width for x in columns) or any(not 0 <= y <= height for y in rows):
        raise DemoMapValidationError("Lane coordinates must be inside the store boundary")
    terminals = raw.get("terminals")
    if not isinstance(terminals, Mapping):
        raise DemoMapValidationError("Map must define entrance and checkout terminals")

    nodes: list[dict[str, Any]] = []
    node_coordinates: dict[str, tuple[float, float]] = {}
    for row_index, y_m in enumerate(rows):
        for column_index, x_m in enumerate(columns):
            node_id = f"N{row_index}_{column_index}"
            node_coordinates[node_id] = (x_m, y_m)
            nodes.append(
                {
                    "id": node_id,
                    "name": node_id,
                    "type": (
                        "entrance"
                        if node_id == raw.get("terminals", {}).get("entrance_node_id")
                        else "checkout"
                        if node_id == raw.get("terminals", {}).get("checkout_node_id")
                        else "intersection"
                    ),
                    "x_m": x_m,
                    "y_m": y_m,
                }
            )

    edges: list[dict[str, Any]] = []
    for row_index, _ in enumerate(rows):
        for column_index in range(len(columns) - 1):
            source = f"N{row_index}_{column_index}"
            target = f"N{row_index}_{column_index + 1}"
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "distance_m": columns[column_index + 1] - columns[column_index],
                }
            )
    for column_index in cross_columns:
        for row_index in range(len(rows) - 1):
            source = f"N{row_index}_{column_index}"
            target = f"N{row_index + 1}_{column_index}"
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "distance_m": rows[row_index + 1] - rows[row_index],
                }
            )

    graph_data = {"nodes": nodes, "edges": edges}
    try:
        graph = StoreGraph.from_dict(graph_data)
    except (GraphValidationError, TypeError) as exc:
        raise DemoMapValidationError(f"Derived walkable graph is invalid: {exc}") from exc

    shelves = raw.get("shelves")
    checkpoints = raw.get("checkpoints")
    products = raw.get("products")
    if not all(isinstance(value, list) for value in (shelves, checkpoints, products)):
        raise DemoMapValidationError("Shelves, checkpoints, and products must be lists")

    shelf_by_id: dict[str, dict[str, Any]] = {}
    shelf_bounds: list[tuple[float, float, float, float]] = []
    for shelf in shelves:
        if not isinstance(shelf, Mapping):
            raise DemoMapValidationError("Each shelf must be an object")
        shelf_id = shelf.get("shelf_id")
        if not isinstance(shelf_id, str) or not shelf_id.strip() or shelf_id in shelf_by_id:
            raise DemoMapValidationError("Shelf IDs must be unique non-empty strings")
        raw_bounds = shelf.get("bounds_m")
        if not isinstance(raw_bounds, list) or len(raw_bounds) != 4:
            raise DemoMapValidationError(f"Shelf {shelf_id} must have four bounds")
        left, bottom, right, top = (
            _number(value, f"Shelf {shelf_id} bounds") for value in raw_bounds
        )
        if not (0 <= left < right <= width and 0 <= bottom < top <= height):
            raise DemoMapValidationError(f"Shelf {shelf_id} is outside the store boundary")
        bounds = (left, bottom, right, top)
        half_lane = lane_width / 2.0
        for y_m in rows:
            if bottom < y_m + half_lane and top > y_m - half_lane:
                raise DemoMapValidationError(f"Shelf {shelf_id} overlaps a horizontal walkable lane")
        for index in cross_columns:
            x_m = columns[index]
            if left < x_m + half_lane and right > x_m - half_lane:
                raise DemoMapValidationError(f"Shelf {shelf_id} overlaps a cross-aisle lane")
        pickup_node_id = shelf.get("pickup_node_id")
        pickup = (
            node_coordinates.get(pickup_node_id)
            if isinstance(pickup_node_id, str)
            else None
        )
        if pickup is None or _inside_shelf(
            pickup[0], pickup[1], pickup[0], pickup[1], bounds
        ):
            raise DemoMapValidationError(f"Shelf {shelf_id} has an inaccessible pickup node")
        pickup_distance = math.hypot(
            max(left - pickup[0], 0.0, pickup[0] - right),
            max(bottom - pickup[1], 0.0, pickup[1] - top),
        )
        if pickup_distance > lane_width:
            raise DemoMapValidationError(
                f"Shelf {shelf_id} pickup node is not reachable from the adjacent lane"
            )
        if any(
            left < other[2] and right > other[0]
            and bottom < other[3] and top > other[1]
            for other in shelf_bounds
        ):
            raise DemoMapValidationError(f"Shelf {shelf_id} overlaps another shelf footprint")
        shelf_by_id[shelf_id] = dict(shelf)
        shelf_bounds.append(bounds)

    for edge in graph.edges:
        start = graph.node(edge.source)
        end = graph.node(edge.target)
        if math.isclose(start.y_m, end.y_m):
            if not any(
                math.isclose(start.y_m, y_m)
                and min(start.x_m, end.x_m) >= columns[0] - 1e-9
                and max(start.x_m, end.x_m) <= columns[-1] + 1e-9
                for y_m in rows
            ):
                raise DemoMapValidationError("A horizontal route segment is outside walkable lanes")
        elif math.isclose(start.x_m, end.x_m):
            if not any(
                index in cross_columns
                and math.isclose(start.x_m, columns[index])
                for index in range(len(columns))
            ):
                raise DemoMapValidationError("A vertical route segment is outside a cross-aisle")
        else:
            raise DemoMapValidationError("Diagonal route segments are not allowed")
        if any(
            _inside_shelf(start.x_m, start.y_m, end.x_m, end.y_m, bounds)
            for bounds in shelf_bounds
        ):
            raise DemoMapValidationError(
                f"Route edge {edge.source}-{edge.target} intersects a shelf obstacle"
            )

    entrance = terminals.get("entrance_node_id")
    checkout = terminals.get("checkout_node_id")
    if entrance not in graph or checkout not in graph or entrance == checkout:
        raise DemoMapValidationError("Entrance and checkout must be distinct walkable nodes")
    reached = {entrance}
    pending = [entrance]
    while pending:
        current = pending.pop()
        for neighbor, _ in graph.neighbors(current):
            if neighbor not in reached:
                reached.add(neighbor)
                pending.append(neighbor)
    if reached != set(graph.node_ids):
        raise DemoMapValidationError("Every walkable node must connect to the entrance")

    seen_product_ids: set[str] = set()
    for product in products:
        if not isinstance(product, Mapping):
            raise DemoMapValidationError("Each demo product must be an object")
        product_id = product.get("demo_product_id")
        shelf_id = product.get("shelf_id")
        pickup_node_id = product.get("pickup_node_id")
        if (
            not isinstance(product_id, str)
            or not product_id.startswith("SIM-P-")
            or product_id in seen_product_ids
        ):
            raise DemoMapValidationError("Demo product IDs must be unique SIM-P-* IDs")
        if (
            not isinstance(shelf_id, str)
            or shelf_id not in shelf_by_id
            or not isinstance(pickup_node_id, str)
            or pickup_node_id not in graph
        ):
            raise DemoMapValidationError(f"Demo product {product_id} has an invalid shelf or pickup")
        shelf = shelf_by_id[shelf_id]
        if shelf["pickup_node_id"] != pickup_node_id or shelf["section"] != product.get("shelf_section"):
            raise DemoMapValidationError(f"Demo product {product_id} does not match its shelf mapping")
        seen_product_ids.add(product_id)

    tag_rows: list[dict[str, Any]] = []
    seen_checkpoint_ids: set[int] = set()
    seen_checkpoint_nodes: set[str] = set()
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping):
            raise DemoMapValidationError("Each checkpoint must be an object")
        checkpoint_id = checkpoint.get("checkpoint_id")
        node_id = checkpoint.get("node_id")
        if (
            isinstance(checkpoint_id, bool)
            or not isinstance(checkpoint_id, int)
            or checkpoint_id in seen_checkpoint_ids
            or not isinstance(node_id, str)
            or node_id not in graph
            or node_id in seen_checkpoint_nodes
        ):
            raise DemoMapValidationError("Checkpoint IDs and node mappings must be unique and valid")
        x_m, y_m = node_coordinates[node_id]
        tag_rows.append(
            {
                "tag_id": checkpoint_id,
                "node_id": node_id,
                "x_m": x_m,
                "y_m": y_m,
                "orientation_deg": 0.0,
                "size_m": 0.16,
                "location_name": str(checkpoint.get("name", node_id)),
            }
        )
        seen_checkpoint_ids.add(checkpoint_id)
        seen_checkpoint_nodes.add(node_id)
    checkpoint_layout = AprilTagLayout.from_dict(
        {"family": "tag36h11", "tags": tag_rows}, graph
    )

    raw_payload = dict(raw)
    raw_payload["nodes"] = nodes
    raw_payload["edges"] = [
        {**edge, "kind": "walkable_lane"} for edge in edges
    ]
    raw_payload["walkable_lanes"] = {
        **dict(lanes),
        "horizontal_corridors": [
            {"y_m": y_m, "width_m": lane_width} for y_m in rows
        ],
        "cross_aisle_corridors": [
            {"x_m": columns[index], "width_m": lane_width} for index in cross_columns
        ],
    }
    return DemoStore(graph, raw_payload, checkpoint_layout)


def load_demo_store(path: str | Path = DEFAULT_DEMO_MAP_PATH) -> DemoStore:
    """Read the versioned synthetic layout and validate it before use."""
    map_path = Path(path)
    try:
        raw = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoMapValidationError(f"Unable to load synthetic demo map: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise DemoMapValidationError("Synthetic demo map root must be a JSON object")
    return build_demo_store(raw)
