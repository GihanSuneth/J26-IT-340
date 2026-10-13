"""Run and record three simulated Held-Karp shopping-route comparisons."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

from .held_karp import HeldKarpRoute, OrderedRoute, held_karp_route, route_for_stop_order
from .store_graph import DEFAULT_STORE_GRAPH_PATH, StoreGraph, load_store_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOG = REPOSITORY_ROOT / "component3/evaluation/logs/held_karp_demo.txt"
DEFAULT_METRICS = (
    REPOSITORY_ROOT / "component3/evaluation/metrics/held_karp_comparison.csv"
)


@dataclass(frozen=True, slots=True)
class SessionDefinition:
    session_id: str
    title: str
    requested_stop_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionComparison:
    definition: SessionDefinition
    original: OrderedRoute
    optimized: HeldKarpRoute
    distance_saved_m: float
    percentage_reduction: float


SESSIONS = (
    SessionDefinition(
        "A",
        "Produce → Dairy → Frozen",
        ("B1", "B3", "B5"),
    ),
    SessionDefinition(
        "B",
        "General Grocery → Bakery → Meat",
        ("B6", "B2", "B4"),
    ),
    SessionDefinition(
        "C",
        "Frozen → Produce → Dairy → Bakery",
        ("B5", "B1", "B3", "B2"),
    ),
)


def compare_sessions(graph: StoreGraph) -> tuple[SessionComparison, ...]:
    comparisons: list[SessionComparison] = []
    for definition in SESSIONS:
        original = route_for_stop_order(
            graph,
            "ENT",
            definition.requested_stop_ids,
            "CHK",
        )
        optimized = held_karp_route(
            graph,
            "ENT",
            definition.requested_stop_ids,
            "CHK",
        )
        saved = original.total_distance_m - optimized.total_distance_m
        reduction = (
            saved / original.total_distance_m * 100.0
            if original.total_distance_m > 0
            else 0.0
        )
        comparisons.append(
            SessionComparison(definition, original, optimized, saved, reduction)
        )
    return tuple(comparisons)


def format_report(
    graph_path: Path,
    comparisons: tuple[SessionComparison, ...],
) -> str:
    lines = [
        "Component 3 Held-Karp Multi-Stop Demonstration",
        "================================================",
        f"Executed: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Python: {sys.version.split()[0]}",
        "Command: python3 -B -m component3.backend.comp3_reco_navigation.navigation.held_karp_demo",
        f"Graph: {graph_path}",
        "Start: ENT — Entrance",
        "Checkout: CHK — Checkout",
        "Prototype notice: simulated graph distances; not real-world trolley performance.",
        "",
    ]
    for comparison in comparisons:
        definition = comparison.definition
        lines.extend(
            [
                f"[Session {definition.session_id}: {definition.title}]",
                "Requested stop order: " + " -> ".join(definition.requested_stop_ids),
                "Original expanded route: "
                + " -> ".join(comparison.original.route_node_ids),
                f"Original-order distance: {comparison.original.total_distance_m:.2f} m",
                "Optimized stop order: "
                + " -> ".join(comparison.optimized.optimized_stop_ids),
                "Optimized expanded route: "
                + " -> ".join(comparison.optimized.route_node_ids),
                f"Optimized distance: {comparison.optimized.total_distance_m:.2f} m",
                f"Distance saved: {comparison.distance_saved_m:.2f} m",
                f"Percentage reduction: {comparison.percentage_reduction:.2f}%",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_metrics(
    output: Path,
    comparisons: tuple[SessionComparison, ...],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "session_id",
        "unique_shopping_stops",
        "original_order_distance_m",
        "optimized_distance_m",
        "distance_saved_m",
        "percentage_reduction",
        "original_stop_order",
        "optimized_stop_order",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for comparison in comparisons:
            writer.writerow(
                {
                    "session_id": comparison.definition.session_id,
                    "unique_shopping_stops": len(
                        comparison.optimized.unique_required_stop_ids
                    ),
                    "original_order_distance_m": (
                        f"{comparison.original.total_distance_m:.2f}"
                    ),
                    "optimized_distance_m": (
                        f"{comparison.optimized.total_distance_m:.2f}"
                    ),
                    "distance_saved_m": f"{comparison.distance_saved_m:.2f}",
                    "percentage_reduction": (
                        f"{comparison.percentage_reduction:.2f}"
                    ),
                    "original_stop_order": " -> ".join(
                        comparison.definition.requested_stop_ids
                    ),
                    "optimized_stop_order": " -> ".join(
                        comparison.optimized.optimized_stop_ids
                    ),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_STORE_GRAPH_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = load_store_graph(args.graph)
    comparisons = compare_sessions(graph)
    report = format_report(args.graph.resolve(), comparisons)
    print(report, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    write_metrics(args.metrics, comparisons)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
