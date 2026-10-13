"""Validate the simulated Component 3 store graph and AprilTag layout."""

from __future__ import annotations

import argparse
from collections import deque
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GRAPH = Path(__file__).with_name("store_graph.json")
DEFAULT_TAGS = Path(__file__).with_name("apriltag_layout.json")
DEFAULT_PRODUCTS = REPOSITORY_ROOT / "shared/db/seed/products.csv"
DEFAULT_LOCATIONS = REPOSITORY_ROOT / "shared/db/seed/store_locations.csv"
EXPECTED_SECTIONS = {"produce", "bakery", "dairy", "meat", "frozen", "general_grocery"}


class Validation:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str) -> None:
        self.results.append((name, bool(condition), detail))

    @property
    def passed(self) -> bool:
        return all(result for _, result, _ in self.results)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def current_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def validate(graph: dict, layout: dict, products: list[dict[str, str]], store_locations: list[dict[str, str]]) -> Validation:
    result = Validation()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    sections = graph.get("sections", [])
    mappings = graph.get("product_locations", [])
    tags = layout.get("tags", [])

    node_ids = [node.get("id") for node in nodes]
    node_by_id = {node.get("id"): node for node in nodes}
    section_ids = {section.get("id") for section in sections}
    product_ids = {row.get("product_id") for row in products if row.get("product_id")}

    result.check("JSON structure", isinstance(nodes, list) and isinstance(edges, list) and isinstance(tags, list), "Graph and tag documents parsed as JSON objects with list collections")
    result.check("Unique graph node IDs", len(node_ids) == len(set(node_ids)) and all(node_ids), f"{len(node_ids)} node IDs checked")
    edge_refs_valid = all(edge.get("source") in node_by_id and edge.get("target") in node_by_id for edge in edges)
    result.check("Valid edge references", edge_refs_valid, f"{len(edges)} edge endpoint pairs checked")
    positive_edges = all(isinstance(edge.get("distance_m"), (int, float)) and edge["distance_m"] > 0 for edge in edges)
    result.check("Positive edge distances", positive_edges, f"{len(edges)} distances checked in metres")

    duplicate_edges = len({frozenset((edge.get("source"), edge.get("target"))) for edge in edges}) != len(edges)
    result.check("Undirected edge uniqueness", not duplicate_edges, "No duplicated undirected node pairs")

    adjacency = {node_id: set() for node_id in node_ids}
    if edge_refs_valid:
        for edge in edges:
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])
    visited: set[str] = set()
    if node_ids:
        queue = deque([node_ids[0]])
        while queue:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            queue.extend(adjacency[node_id] - visited)
    result.check("Graph connectivity", set(node_ids) == visited, f"{len(visited)} of {len(node_ids)} nodes reachable")

    node_types = [node.get("type") for node in nodes]
    result.check("Entrance and checkout", node_types.count("entrance") == 1 and node_types.count("checkout") == 1, "Exactly one entrance and one checkout node")

    dimensions = graph.get("dimensions_m", {})
    width, height = dimensions.get("width"), dimensions.get("height")
    coords_valid = isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0
    coords_valid = coords_valid and graph.get("coordinate_system", {}).get("unit") == "metre"
    if coords_valid:
        coords_valid = all(
            isinstance(node.get("x_m"), (int, float))
            and isinstance(node.get("y_m"), (int, float))
            and 0 <= node["x_m"] <= width
            and 0 <= node["y_m"] <= height
            for node in nodes
        )
    result.check("Coordinate system and units", coords_valid, f"All nodes within simulated {width} m × {height} m footprint; metres declared")

    geometry_valid = edge_refs_valid and all(
        edge["distance_m"] + 0.011 >= math.dist(
            (node_by_id[edge["source"]]["x_m"], node_by_id[edge["source"]]["y_m"]),
            (node_by_id[edge["target"]]["x_m"], node_by_id[edge["target"]]["y_m"]),
        )
        for edge in edges
    )
    result.check("Edge geometry consistency", geometry_valid, "Walking distances are not shorter than straight-line coordinate distances")

    categories = {section.get("category") for section in sections}
    section_refs_valid = categories == EXPECTED_SECTIONS and all(
        node_id in node_by_id for section in sections for node_id in section.get("access_node_ids", [])
    ) and all(node.get("aisle_ref") in section_ids for node in nodes if "aisle_ref" in node)
    result.check("Six section references", section_refs_valid, ", ".join(sorted(categories)))

    mappings_valid = all(
        mapping.get("product_id") in product_ids
        and mapping.get("node_id") in node_by_id
        and mapping.get("aisle_id") in section_ids
        for mapping in mappings
    )
    seed_locations_valid = all(
        row.get("product_id") in product_ids and row.get("aisle_id") in section_ids
        for row in store_locations
    )
    result.check("Valid product-location references", mappings_valid and seed_locations_valid, f"{len(mappings)} graph mappings and {len(store_locations)} seed location rows checked against {len(product_ids)} product IDs")

    tag_ids = [tag.get("tag_id") for tag in tags]
    result.check("Unique AprilTag IDs", len(tag_ids) == len(set(tag_ids)) and all(isinstance(tag_id, int) for tag_id in tag_ids), f"{len(tag_ids)} integer tag IDs checked")
    tag_refs_valid = all(tag.get("node_id") in node_by_id for tag in tags)
    result.check("Valid AprilTag node mappings", tag_refs_valid, f"{len(tags)} tag-to-node mappings checked")
    tag_properties_valid = layout.get("family") == "tag36h11" and all(
        isinstance(tag.get("size_m"), (int, float))
        and tag["size_m"] > 0
        and isinstance(tag.get("orientation_deg"), (int, float))
        and 0 <= tag["orientation_deg"] < 360
        and bool(tag.get("location_name"))
        for tag in tags
    )
    result.check("AprilTag family and physical properties", tag_properties_valid, f"Family {layout.get('family')}; positive size and valid orientation checked")
    tag_coords_match = tag_refs_valid and all(
        math.isclose(tag["x_m"], node_by_id[tag["node_id"]]["x_m"], abs_tol=1e-9)
        and math.isclose(tag["y_m"], node_by_id[tag["node_id"]]["y_m"], abs_tol=1e-9)
        for tag in tags
    )
    result.check("AprilTag coordinate consistency", tag_coords_match, "Every tag position matches its mapped graph node")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--tags", type=Path, default=DEFAULT_TAGS)
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--store-locations", type=Path, default=DEFAULT_LOCATIONS)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_paths = [args.graph, args.tags, args.products, args.store_locations]
    try:
        graph = read_json(args.graph)
        layout = read_json(args.tags)
        products = read_csv(args.products)
        locations = read_csv(args.store_locations)
        result = validate(graph, layout, products, locations)
        load_error = None
    except (OSError, json.JSONDecodeError, csv.Error, TypeError, ValueError) as exc:
        result = Validation()
        result.check("JSON and CSV parsing", False, f"{type(exc).__name__}: {exc}")
        graph, layout, products, locations = {}, {}, [], []
        load_error = exc

    lines = [
        "Component 3 Store Map Validation",
        "================================",
        f"Executed: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Python: {sys.version.split()[0]}",
        f"Git commit: {current_commit()}",
        "Command: python3 component3/data/store_map/validate_store_map.py --output component3/evaluation/test_results/store_map_validation.txt",
        "Sources:",
        *(f"- {path.relative_to(REPOSITORY_ROOT)}" for path in source_paths),
        "",
    ]
    for name, passed, detail in result.results:
        lines.append(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    lines.extend(
        [
            "",
            f"Graph nodes: {len(graph.get('nodes', []))}",
            f"Graph edges: {len(graph.get('edges', []))}",
            f"Store sections: {len(graph.get('sections', []))}",
            f"Product seed rows: {len(products)}",
            f"Product mappings: {len(graph.get('product_locations', []))}",
            f"AprilTag checkpoints: {len(layout.get('tags', []))}",
            f"Overall result: {'PASS' if result.passed else 'FAIL'}",
        ]
    )
    report = "\n".join(lines) + "\n"
    print(report, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    return 0 if result.passed and load_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
