"""Command-line demonstration of Component 3 Dijkstra routing."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

from .dijkstra import dijkstra_shortest_path
from .store_graph import DEFAULT_STORE_GRAPH_PATH, StoreGraph, load_store_graph


DEFAULT_DEMOS = (
    ("Entrance to Checkout", "ENT", "CHK"),
    ("Entrance to Produce", "ENT", "B1"),
    ("Entrance to Frozen", "ENT", "B5"),
)


def route_summary(graph: StoreGraph, start: str, destination: str) -> list[str]:
    """Return human-readable lines for one computed route."""
    route = dijkstra_shortest_path(graph, start, destination)
    names = [graph.node(node_id).name for node_id in route.node_ids]
    return [
        f"Start: {start} — {graph.node(start).name}",
        f"Destination: {destination} — {graph.node(destination).name}",
        f"Node sequence: {' -> '.join(route.node_ids)}",
        f"Total walking distance: {route.total_distance_m:.2f} m",
        f"Route summary: {' -> '.join(names)}",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_STORE_GRAPH_PATH)
    parser.add_argument("--start")
    parser.add_argument("--destination")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.start) != bool(args.destination):
        parser.error("--start and --destination must be supplied together")
    return args


def main() -> int:
    args = parse_args()
    graph = load_store_graph(args.graph)
    command = (
        "python3 -B -m "
        "component3.backend.comp3_reco_navigation.navigation.dijkstra_demo"
    )
    if args.start:
        command += f" --start {args.start} --destination {args.destination}"
    if args.output:
        command += f" --output {args.output}"

    lines = [
        "Component 3 Dijkstra Routing Demonstration",
        "==========================================",
        f"Executed: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Python: {sys.version.split()[0]}",
        f"Command: {command}",
        f"Graph: {args.graph}",
        "",
    ]
    scenarios = (
        (("Requested route", args.start, args.destination),)
        if args.start
        else DEFAULT_DEMOS
    )
    for title, start, destination in scenarios:
        lines.append(f"[{title}]")
        lines.extend(route_summary(graph, start, destination))
        lines.append("")
    report = "\n".join(lines).rstrip() + "\n"
    print(report, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
