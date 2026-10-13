"""Generate report-quality Dijkstra route figures from the store graph JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from component3.backend.comp3_reco_navigation.navigation.dijkstra import (  # noqa: E402
    ShortestPath,
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (  # noqa: E402
    StoreGraph,
    load_store_graph,
)
from data.store_map.visualize_store_map import (  # noqa: E402
    add_graph,
    add_sections,
    base_svg,
    render_png,
    sx,
    sy,
    text,
)


DEFAULT_GRAPH = Path(__file__).with_name("store_graph.json")
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "component3/docs/research_evidence/04_navigation_algorithms/screenshots"
)
ROUTES = (
    ("C3-NAV-001_entrance_to_checkout.png", "Entrance to Checkout", "ENT", "CHK"),
    ("C3-NAV-002_entrance_to_produce.png", "Entrance to Produce", "ENT", "B1"),
    ("C3-NAV-003_entrance_to_frozen.png", "Entrance to Frozen", "ENT", "B5"),
)
ROUTE_COLOUR = "#F97316"


def load_raw_graph(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def add_route_overlay(
    parts: list[str],
    graph: StoreGraph,
    route: ShortestPath,
) -> None:
    """Highlight an algorithm-produced route over the base graph."""
    for source_id, target_id in zip(route.node_ids, route.node_ids[1:]):
        source = graph.node(source_id)
        target = graph.node(target_id)
        parts.append(
            f'<line x1="{sx(source.x_m):.1f}" y1="{sy(source.y_m):.1f}" '
            f'x2="{sx(target.x_m):.1f}" y2="{sy(target.y_m):.1f}" '
            f'stroke="#FFFFFF" stroke-width="15" stroke-linecap="round"/>'
        )
        parts.append(
            f'<line x1="{sx(source.x_m):.1f}" y1="{sy(source.y_m):.1f}" '
            f'x2="{sx(target.x_m):.1f}" y2="{sy(target.y_m):.1f}" '
            f'stroke="{ROUTE_COLOUR}" stroke-width="9" stroke-linecap="round"/>'
        )

    for index, node_id in enumerate(route.node_ids, start=1):
        node = graph.node(node_id)
        x, y = sx(node.x_m), sy(node.y_m)
        colour = "#16A34A" if index == 1 else "#DC2626" if index == len(route.node_ids) else ROUTE_COLOUR
        radius = 15 if index in {1, len(route.node_ids)} else 11
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" '
            f'fill="{colour}" stroke="#FFFFFF" stroke-width="4"/>'
        )
        parts.append(
            text(x, y + 5, index, size=12, weight="bold", colour="#FFFFFF")
        )


def add_route_panel(
    parts: list[str],
    graph: StoreGraph,
    route: ShortestPath,
    title: str,
) -> None:
    """Add route details and a legend beside the plot."""
    x = 1320
    start = graph.node(route.node_ids[0])
    destination = graph.node(route.node_ids[-1])
    parts.append(text(x, 145, "Dijkstra result", size=23, anchor="start", weight="bold"))
    parts.append(text(x, 184, title, size=18, anchor="start", weight="bold", colour=ROUTE_COLOUR))
    parts.append(text(x, 222, f"Start: {start.node_id} — {start.name}", size=15, anchor="start"))
    parts.append(text(x, 250, f"Destination: {destination.node_id} — {destination.name}", size=15, anchor="start"))
    parts.append(text(x, 292, "Ordered node sequence", size=17, anchor="start", weight="bold"))
    parts.append(text(x, 322, " → ".join(route.node_ids), size=15, anchor="start", colour=ROUTE_COLOUR, weight="bold"))
    parts.append(text(x, 370, "Total walking distance", size=17, anchor="start", weight="bold"))
    parts.append(text(x, 410, f"{route.total_distance_m:.2f} metres", size=28, anchor="start", colour=ROUTE_COLOUR, weight="bold"))
    parts.append(text(x, 466, "Edge accumulation", size=17, anchor="start", weight="bold"))
    y = 499
    for source_id, target_id in zip(route.node_ids, route.node_ids[1:]):
        distance_m = graph.edge_weight(source_id, target_id)
        parts.append(text(x, y, f"{source_id} → {target_id}: {distance_m:.2f} m", size=14, anchor="start"))
        y += 26

    legend_y = max(y + 28, 680)
    parts.append(text(x, legend_y, "Legend", size=18, anchor="start", weight="bold"))
    legend = (
        ("#16A34A", "Start node"),
        ("#DC2626", "Destination node"),
        (ROUTE_COLOUR, "Shortest-path edge / intermediate node"),
        ("#1D4ED8", "Other walkable node"),
    )
    for index, (colour, label) in enumerate(legend):
        cy = legend_y + 35 + index * 36
        parts.append(f'<circle cx="{x + 8}" cy="{cy}" r="8" fill="{colour}"/>')
        parts.append(text(x + 28, cy + 5, label, size=14, anchor="start"))

    parts.append(text(x, 910, "Method note", size=18, anchor="start", weight="bold"))
    parts.append(text(x, 942, "Route computed from graph edge weights", size=14, anchor="start"))
    parts.append(text(x, 966, "using deterministic Dijkstra traversal.", size=14, anchor="start"))
    parts.append(text(x, 1012, "SIMULATED PROTOTYPE — not field surveyed", size=14, anchor="start", weight="bold", colour="#B45309"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_graph = load_raw_graph(args.graph)
    graph = load_store_graph(args.graph)

    for filename, title, start, destination in ROUTES:
        route = dijkstra_shortest_path(graph, start, destination)
        parts = base_svg(
            f"Component 3 shortest route — {title}",
            "SIMULATED PROTOTYPE LAYOUT — highlighted route is computed by Dijkstra from stored graph-edge distances",
            raw_graph,
        )
        add_sections(parts, raw_graph)
        add_graph(parts, raw_graph, label_edges=False)
        add_route_overlay(parts, graph, route)
        add_route_panel(parts, graph, route, title)
        output = args.output_dir / filename
        render_png(parts, output)
        print(
            f"Generated {output.relative_to(REPOSITORY_ROOT)}: "
            f"{' -> '.join(route.node_ids)} ({route.total_distance_m:.2f} m)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
