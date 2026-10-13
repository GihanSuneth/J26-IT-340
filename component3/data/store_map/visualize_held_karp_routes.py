"""Generate report-quality Held-Karp route-comparison evidence figures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from component3.backend.comp3_reco_navigation.navigation.held_karp_demo import (  # noqa: E402
    SessionComparison,
    compare_sessions,
)
from component3.backend.comp3_reco_navigation.navigation.store_graph import (  # noqa: E402
    StoreGraph,
    load_store_graph,
)
from component3.data.store_map.visualize_store_map import (  # noqa: E402
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
OUTPUT_NAMES = {
    "A": "C3-NAV-006_held_karp_session_a.png",
    "B": "C3-NAV-007_held_karp_session_b.png",
    "C": "C3-NAV-008_held_karp_session_c.png",
}
ORIGINAL_COLOUR = "#F97316"
OPTIMIZED_COLOUR = "#7C3AED"


def load_raw_graph(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def add_route_lines(
    parts: list[str],
    graph: StoreGraph,
    route_node_ids: tuple[str, ...],
    *,
    colour: str,
    width: int,
    dashed: bool,
) -> None:
    """Draw an expanded graph route without inventing geometric shortcuts."""
    dash = ' stroke-dasharray="16 10"' if dashed else ""
    for source_id, target_id in zip(route_node_ids, route_node_ids[1:]):
        source = graph.node(source_id)
        target = graph.node(target_id)
        parts.append(
            f'<line x1="{sx(source.x_m):.1f}" y1="{sy(source.y_m):.1f}" '
            f'x2="{sx(target.x_m):.1f}" y2="{sy(target.y_m):.1f}" '
            f'stroke="#FFFFFF" stroke-width="{width + 6}" stroke-linecap="round"/>'
        )
        parts.append(
            f'<line x1="{sx(source.x_m):.1f}" y1="{sy(source.y_m):.1f}" '
            f'x2="{sx(target.x_m):.1f}" y2="{sy(target.y_m):.1f}" '
            f'stroke="{colour}" stroke-width="{width}" stroke-linecap="round"'
            f' opacity="0.88"{dash}/>'
        )


def add_stop_markers(
    parts: list[str], graph: StoreGraph, comparison: SessionComparison
) -> None:
    for position, node_id in enumerate(
        comparison.optimized.optimized_stop_ids, start=1
    ):
        node = graph.node(node_id)
        x, y = sx(node.x_m), sy(node.y_m)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="{OPTIMIZED_COLOUR}" '
            'stroke="#FFFFFF" stroke-width="4"/>'
        )
        parts.append(text(x, y + 5, position, size=13, weight="bold", colour="#FFFFFF"))

    for node_id, colour, label in (
        (comparison.optimized.start_node_id, "#16A34A", "S"),
        (comparison.optimized.checkout_node_id, "#DC2626", "C"),
    ):
        node = graph.node(node_id)
        x, y = sx(node.x_m), sy(node.y_m)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="18" fill="{colour}" '
            'stroke="#FFFFFF" stroke-width="4"/>'
        )
        parts.append(text(x, y + 5, label, size=12, weight="bold", colour="#FFFFFF"))


def add_comparison_panel(
    parts: list[str], graph: StoreGraph, comparison: SessionComparison
) -> None:
    x = 1310
    requested = comparison.definition.requested_stop_ids
    optimized = comparison.optimized.optimized_stop_ids
    parts.append(text(x, 142, "Held-Karp comparison", size=22, anchor="start", weight="bold"))
    parts.append(
        text(
            x,
            178,
            f"Session {comparison.definition.session_id}: {comparison.definition.title}",
            size=16,
            anchor="start",
            weight="bold",
            colour=OPTIMIZED_COLOUR,
        )
    )
    parts.append(text(x, 224, "Fixed endpoints", size=17, anchor="start", weight="bold"))
    parts.append(text(x, 253, "ENT (Entrance) → CHK (Checkout)", size=14, anchor="start"))

    parts.append(text(x, 303, "Requested shopping order", size=17, anchor="start", weight="bold"))
    parts.append(text(x, 333, " → ".join(requested), size=15, anchor="start", colour=ORIGINAL_COLOUR, weight="bold"))
    parts.append(text(x, 363, f"{comparison.original.total_distance_m:.2f} metres", size=20, anchor="start", colour=ORIGINAL_COLOUR, weight="bold"))

    parts.append(text(x, 418, "Optimized shopping order", size=17, anchor="start", weight="bold"))
    parts.append(text(x, 448, " → ".join(optimized), size=15, anchor="start", colour=OPTIMIZED_COLOUR, weight="bold"))
    parts.append(text(x, 478, f"{comparison.optimized.total_distance_m:.2f} metres", size=20, anchor="start", colour=OPTIMIZED_COLOUR, weight="bold"))

    parts.append(text(x, 535, "Measured graph-distance saving", size=17, anchor="start", weight="bold"))
    parts.append(text(x, 570, f"{comparison.distance_saved_m:.2f} m ({comparison.percentage_reduction:.2f}%)", size=24, anchor="start", colour="#166534", weight="bold"))

    parts.append(text(x, 638, "Legend", size=18, anchor="start", weight="bold"))
    parts.append(f'<line x1="{x}" y1="672" x2="{x + 55}" y2="672" stroke="{ORIGINAL_COLOUR}" stroke-width="8" stroke-dasharray="16 10"/>')
    parts.append(text(x + 70, 678, "Requested-order route", size=14, anchor="start"))
    parts.append(f'<line x1="{x}" y1="711" x2="{x + 55}" y2="711" stroke="{OPTIMIZED_COLOUR}" stroke-width="7"/>')
    parts.append(text(x + 70, 717, "Held-Karp optimized route", size=14, anchor="start"))
    for offset, colour, label in (
        (756, "#16A34A", "Start"),
        (791, "#DC2626", "Checkout"),
        (826, OPTIMIZED_COLOUR, "Stop number in optimized order"),
    ):
        parts.append(f'<circle cx="{x + 9}" cy="{offset}" r="9" fill="{colour}"/>')
        parts.append(text(x + 30, offset + 5, label, size=14, anchor="start"))

    parts.append(text(x, 895, "Method", size=18, anchor="start", weight="bold"))
    parts.append(text(x, 927, "Pairwise distances: Dijkstra", size=14, anchor="start"))
    parts.append(text(x, 952, "Stop ordering: exact Held-Karp DP", size=14, anchor="start"))
    parts.append(text(x, 987, "SIMULATED PROTOTYPE — not field surveyed", size=13, anchor="start", weight="bold", colour="#B45309"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_graph = load_raw_graph(args.graph)
    graph = load_store_graph(args.graph)
    for comparison in compare_sessions(graph):
        session_id = comparison.definition.session_id
        parts = base_svg(
            f"Component 3 multi-stop route — Session {session_id}",
            "SIMULATED PROTOTYPE LAYOUT — requested order compared with exact Held-Karp optimization over Dijkstra graph distances",
            raw_graph,
        )
        add_sections(parts, raw_graph)
        add_graph(parts, raw_graph, label_edges=False, faint=True)
        add_route_lines(
            parts,
            graph,
            comparison.original.route_node_ids,
            colour=ORIGINAL_COLOUR,
            width=10,
            dashed=True,
        )
        add_route_lines(
            parts,
            graph,
            comparison.optimized.route_node_ids,
            colour=OPTIMIZED_COLOUR,
            width=6,
            dashed=False,
        )
        add_stop_markers(parts, graph, comparison)
        add_comparison_panel(parts, graph, comparison)
        output = args.output_dir / OUTPUT_NAMES[session_id]
        render_png(parts, output)
        print(
            f"Generated {output.relative_to(REPOSITORY_ROOT)}: "
            f"{comparison.original.total_distance_m:.2f} m -> "
            f"{comparison.optimized.total_distance_m:.2f} m "
            f"({comparison.percentage_reduction:.2f}% reduction)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
