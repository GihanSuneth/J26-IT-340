"""Generate report-quality PNG views of the simulated Component 3 store map.

The script uses only the Python standard library to compose SVG and an installed
macOS renderer (``sips`` when it supports SVG, otherwise Quick Look) to create
PNGs. All plotted geometry and labels are loaded from the two JSON source files.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRAPH = Path(__file__).with_name("store_graph.json")
DEFAULT_TAGS = Path(__file__).with_name("apriltag_layout.json")
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "docs/research_evidence/component3/02_store_map/screenshots"
)
CANVAS_WIDTH = 1700
CANVAS_HEIGHT = 1120
PLOT_LEFT = 120
PLOT_BOTTOM = 990
SCALE = 48
SECTION_COLOURS = ["#DFF3E4", "#FCE8C3", "#DDEBFA", "#F7DCDC", "#DDE5F8", "#EFE4F7"]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sx(x_m: float) -> float:
    return PLOT_LEFT + x_m * SCALE


def sy(y_m: float) -> float:
    return PLOT_BOTTOM - y_m * SCALE


def text(x: float, y: float, value: object, *, size: int = 18, anchor: str = "middle", weight: str = "normal", colour: str = "#172033") -> str:
    safe = html.escape(str(value))
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{colour}">{safe}</text>'
    )


def base_svg(title: str, subtitle: str, graph: dict) -> list[str]:
    width = float(graph["dimensions_m"]["width"])
    height = float(graph["dimensions_m"]["height"])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="#FFFFFF"/>',
        text(60, 46, title, size=30, anchor="start", weight="bold"),
        text(60, 78, subtitle, size=17, anchor="start", colour="#4B5563"),
        f'<rect x="{sx(0):.1f}" y="{sy(height):.1f}" width="{width * SCALE:.1f}" height="{height * SCALE:.1f}" fill="#FAFBFC" stroke="#111827" stroke-width="3"/>',
    ]
    for x_tick in range(0, int(width) + 1, 3):
        x = sx(x_tick)
        parts.append(f'<line x1="{x:.1f}" y1="{sy(0):.1f}" x2="{x:.1f}" y2="{sy(0) + 8:.1f}" stroke="#111827"/>')
        parts.append(text(x, sy(0) + 29, x_tick, size=14))
    for y_tick in range(0, int(height) + 1, 3):
        y = sy(y_tick)
        parts.append(f'<line x1="{sx(0) - 8:.1f}" y1="{y:.1f}" x2="{sx(0):.1f}" y2="{y:.1f}" stroke="#111827"/>')
        parts.append(text(sx(0) - 15, y + 5, y_tick, size=14, anchor="end"))
    parts.extend(
        [
            text(sx(width / 2), 1060, "x coordinate (metres east)", size=17, weight="bold"),
            f'<text x="35" y="{sy(height / 2):.1f}" transform="rotate(-90 35 {sy(height / 2):.1f})" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="bold" fill="#172033">y coordinate (metres north)</text>',
        ]
    )
    return parts


def add_sections(parts: list[str], graph: dict) -> None:
    nodes = {node["id"]: node for node in graph["nodes"]}
    for index, section in enumerate(graph["sections"]):
        access = [nodes[node_id] for node_id in section["access_node_ids"]]
        centre_x = access[0]["x_m"]
        x = sx(centre_x - 1.25)
        y = sy(15.7)
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{2.5 * SCALE:.1f}" height="{13.4 * SCALE:.1f}" rx="12" fill="{SECTION_COLOURS[index]}" fill-opacity="0.88" stroke="#9CA3AF" stroke-width="1.5"/>'
        )
        parts.append(text(sx(centre_x), sy(16.25), section["name"], size=15, weight="bold"))
        parts.append(text(sx(centre_x), sy(15.82), section["id"], size=12, colour="#4B5563"))


def add_graph(parts: list[str], graph: dict, *, label_edges: bool, faint: bool = False) -> None:
    nodes = {node["id"]: node for node in graph["nodes"]}
    stroke = "#9CA3AF" if faint else "#374151"
    opacity = "0.55" if faint else "1"
    labelled = {frozenset(pair) for pair in [("ENT", "B4"), ("CHK", "B5"), ("B1", "B2"), ("B2", "B3"), ("B3", "B4"), ("B4", "B5"), ("B5", "B6"), ("B1", "M1"), ("M1", "T1")]}
    for edge in graph["edges"]:
        source = nodes[edge["source"]]
        target = nodes[edge["target"]]
        x1, y1 = sx(source["x_m"]), sy(source["y_m"])
        x2, y2 = sx(target["x_m"]), sy(target["y_m"])
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="4" opacity="{opacity}"/>')
        if label_edges and frozenset((edge["source"], edge["target"])) in labelled:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            parts.append(f'<rect x="{mx - 22:.1f}" y="{my - 14:.1f}" width="44" height="19" rx="4" fill="#FFFFFF" fill-opacity="0.9"/>')
            parts.append(text(mx, my + 1, f'{edge["distance_m"]:g} m', size=12))
    for node in graph["nodes"]:
        x, y = sx(node["x_m"]), sy(node["y_m"])
        colour = "#16A34A" if node["type"] == "entrance" else "#DC2626" if node["type"] == "checkout" else "#1D4ED8"
        radius = 10 if node["type"] in {"entrance", "checkout"} else 7
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{colour}" stroke="#FFFFFF" stroke-width="2"/>')
        if not faint:
            dy = 25 if node["id"].startswith("T") else -14
            parts.append(text(x, y + dy, node["id"], size=12, weight="bold"))
    if not faint:
        for node_id in ("ENT", "CHK"):
            node = nodes[node_id]
            parts.append(text(sx(node["x_m"]), sy(node["y_m"]) + 35, node["name"], size=16, weight="bold"))


def add_tags(parts: list[str], layout: dict, *, include_orientation: bool) -> None:
    for tag in layout["tags"]:
        x, y = sx(tag["x_m"]), sy(tag["y_m"])
        parts.append(f'<rect x="{x - 13:.1f}" y="{y - 13:.1f}" width="26" height="26" fill="#C026D3" stroke="#701A75" stroke-width="3"/>')
        label_y = y - 22 if include_orientation or tag["y_m"] <= 1 else y + 32
        parts.append(text(x, label_y, f'Tag {tag["tag_id"]}', size=13, weight="bold", colour="#86198F"))
        if include_orientation:
            angle = math.radians(tag["orientation_deg"])
            end_x = x + 42 * math.cos(angle)
            end_y = y - 42 * math.sin(angle)
            parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}" stroke="#86198F" stroke-width="4" marker-end="url(#arrow)"/>')


def add_graph_legend(parts: list[str], graph: dict, layout: dict) -> None:
    x = 1320
    parts.append(text(x, 145, "Map summary", size=22, anchor="start", weight="bold"))
    lines = [
        f'{graph["dimensions_m"]["width"]:g} m × {graph["dimensions_m"]["height"]:g} m simulated footprint',
        f'{len(graph["nodes"])} graph nodes; {len(graph["edges"])} undirected edges',
        f'{len(graph["sections"])} sections; {len(layout["tags"])} AprilTag checkpoints',
        "Origin: south-west store corner",
        "Axes: +x east, +y north",
    ]
    for index, line in enumerate(lines):
        parts.append(text(x, 183 + index * 27, line, size=15, anchor="start"))
    parts.append(text(x, 350, "Legend", size=20, anchor="start", weight="bold"))
    legend = [("#16A34A", "Entrance"), ("#DC2626", "Checkout"), ("#1D4ED8", "Walkable graph node"), ("#C026D3", "AprilTag checkpoint")]
    for index, (colour, label) in enumerate(legend):
        cy = 385 + index * 38
        parts.append(f'<circle cx="{x + 8}" cy="{cy}" r="8" fill="{colour}"/>')
        parts.append(text(x + 28, cy + 6, label, size=15, anchor="start"))
    parts.append(text(x, 570, "Section palette", size=20, anchor="start", weight="bold"))
    for index, section in enumerate(graph["sections"]):
        cy = 607 + index * 38
        parts.append(f'<rect x="{x}" y="{cy - 14}" width="22" height="22" fill="{SECTION_COLOURS[index]}" stroke="#9CA3AF"/>')
        parts.append(text(x + 32, cy + 3, f'{section["id"]} — {section["name"]}', size=15, anchor="start"))
    parts.append(text(x, 900, "Prototype note", size=20, anchor="start", weight="bold"))
    parts.append(text(x, 933, "Geometry is simulated for research", size=15, anchor="start"))
    parts.append(text(x, 958, "design and has not been field-surveyed.", size=15, anchor="start"))


def add_tag_table(parts: list[str], layout: dict) -> None:
    x = 1320
    parts.append(text(x, 145, "Checkpoint register", size=22, anchor="start", weight="bold"))
    parts.append(text(x, 178, f'Family: {layout["family"]} · marker size: {layout["tags"][0]["size_m"]:.2f} m', size=15, anchor="start"))
    parts.append(text(x, 215, "ID", size=14, anchor="start", weight="bold"))
    parts.append(text(x + 55, 215, "Node", size=14, anchor="start", weight="bold"))
    parts.append(text(x + 120, 215, "Location", size=14, anchor="start", weight="bold"))
    parts.append(f'<line x1="{x}" y1="224" x2="1660" y2="224" stroke="#9CA3AF"/>')
    for index, tag in enumerate(layout["tags"]):
        y = 254 + index * 55
        parts.append(text(x, y, tag["tag_id"], size=14, anchor="start", weight="bold", colour="#86198F"))
        parts.append(text(x + 55, y, tag["node_id"], size=14, anchor="start"))
        parts.append(text(x + 120, y, tag["location_name"], size=14, anchor="start"))
        parts.append(text(x + 120, y + 20, f'({tag["x_m"]:g}, {tag["y_m"]:g}) m · {tag["orientation_deg"]:g}°', size=12, anchor="start", colour="#4B5563"))
    parts.append(text(x, 735, "Orientation convention", size=20, anchor="start", weight="bold"))
    parts.append(text(x, 768, "Arrows show marker orientation measured", size=14, anchor="start"))
    parts.append(text(x, 791, "counter-clockwise from the +x axis.", size=14, anchor="start"))
    parts.append(text(x, 850, "Prototype note", size=20, anchor="start", weight="bold"))
    parts.append(text(x, 883, "Placements and sizes are simulated;", size=14, anchor="start"))
    parts.append(text(x, 906, "camera visibility remains to be field-tested.", size=14, anchor="start"))


def render_png(svg_parts: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    svg_parts.append("</svg>")
    with tempfile.TemporaryDirectory(prefix="comp3-map-") as temp_dir:
        temp_path = Path(temp_dir)
        svg_path = temp_path / f"{output.stem}.svg"
        svg_path.write_text("\n".join(svg_parts), encoding="utf-8")
        render_errors: list[str] = []
        sips = shutil.which("sips")
        if sips:
            completed = subprocess.run(
                [sips, "-s", "format", "png", str(svg_path), "--out", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                render_errors.append(f"sips: {completed.stderr.strip()}")
        quicklook = shutil.which("qlmanage")
        if (not output.is_file() or output.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n") and quicklook:
            completed = subprocess.run(
                [quicklook, "-t", "-s", str(CANVAS_WIDTH), "-o", str(temp_path), str(svg_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            rendered = temp_path / f"{svg_path.name}.png"
            if completed.returncode == 0 and rendered.is_file():
                shutil.move(rendered, output)
            else:
                render_errors.append(f"qlmanage: {completed.stderr.strip()}")
    if not output.is_file() or output.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(
            f"Installed renderers did not produce a valid PNG: {output}; "
            + " | ".join(render_errors)
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--tags", type=Path, default=DEFAULT_TAGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = load_json(args.graph)
    layout = load_json(args.tags)

    graph_svg = base_svg(
        "Component 3 store navigation graph",
        "SIMULATED PROTOTYPE LAYOUT — connected walking graph, section access, edge distances, and checkpoints",
        graph,
    )
    add_sections(graph_svg, graph)
    add_graph(graph_svg, graph, label_edges=True)
    add_tags(graph_svg, layout, include_orientation=False)
    add_graph_legend(graph_svg, graph, layout)
    graph_output = args.output_dir / "C3-MAP-001_store_graph.png"
    render_png(graph_svg, graph_output)

    tag_svg = base_svg(
        "Component 3 AprilTag checkpoint layout",
        "SIMULATED PROTOTYPE LAYOUT — tag36h11 checkpoint positions, IDs, and marker orientations",
        graph,
    )
    tag_svg.insert(1, '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#86198F"/></marker></defs>')
    add_sections(tag_svg, graph)
    add_graph(tag_svg, graph, label_edges=False, faint=True)
    add_tags(tag_svg, layout, include_orientation=True)
    add_tag_table(tag_svg, layout)
    tag_output = args.output_dir / "C3-MAP-002_apriltag_layout.png"
    render_png(tag_svg, tag_output)

    print(f"Generated {graph_output.relative_to(REPOSITORY_ROOT)}")
    print(f"Generated {tag_output.relative_to(REPOSITORY_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
