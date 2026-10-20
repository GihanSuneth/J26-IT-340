"""Generate and validate the optional dense AprilTag 36h11 demo layout."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from component3.simulations.navigation_dashboard.demo_store import load_demo_store  # noqa: E402


MAX_OPPORTUNITY_SPACING_M = 2.0
RETAINED = {"N0_0": 200, "N2_3": 201, "N4_5": 202}
SHELF_NODES = {"N1_1", "N1_2", "N1_4", "N2_1", "N2_2", "N2_4"}


def generate() -> dict[str, object]:
    store = load_demo_store()
    tags: list[dict[str, object]] = []
    next_id = 203
    node_ids: dict[str, int] = {}
    for node in sorted(store.graph.nodes.values(), key=lambda item: item.node_id):
        tag_id = RETAINED.get(node.node_id)
        if tag_id is None:
            tag_id, next_id = next_id, next_id + 1
        node_ids[node.node_id] = tag_id
        tags.append({
            "tag_id": tag_id, "family": "AprilTag 36h11",
            "x_m": node.x_m, "y_m": node.y_m, "orientation_deg": 0,
            "anchor": {"type": "node", "node_id": node.node_id},
            "purpose": (
                "retained_checkpoint" if node.node_id in RETAINED
                else "shelf_approach" if node.node_id in SHELF_NODES
                else "junction"
            ),
            "practical_subset": node.node_id in RETAINED or node.node_id in SHELF_NODES,
        })
    edge_reports = []
    for edge in sorted(store.graph.edges, key=lambda item: (item.source, item.target)):
        start, end = store.graph.node(edge.source), store.graph.node(edge.target)
        segment_count = max(1, math.ceil(edge.distance_m / MAX_OPPORTUNITY_SPACING_M))
        offsets = [0.0]
        for index in range(1, segment_count):
            fraction = index / segment_count
            offset = edge.distance_m * fraction
            offsets.append(offset)
            tags.append({
                "tag_id": next_id, "family": "AprilTag 36h11",
                "x_m": round(start.x_m + (end.x_m - start.x_m) * fraction, 6),
                "y_m": round(start.y_m + (end.y_m - start.y_m) * fraction, 6),
                "orientation_deg": 0,
                "anchor": {"type": "edge", "source": edge.source,
                           "target": edge.target, "offset_m": round(offset, 6)},
                "purpose": "mid_edge_localization", "practical_subset": False,
            })
            next_id += 1
        offsets.append(edge.distance_m)
        gaps = [round(b - a, 6) for a, b in zip(offsets, offsets[1:])]
        edge_reports.append({
            "source": edge.source, "target": edge.target,
            "edge_length_m": edge.distance_m, "opportunity_offsets_m": offsets,
            "maximum_spacing_m": max(gaps), "passes": max(gaps) <= MAX_OPPORTUNITY_SPACING_M,
        })
    tag_ids = [int(tag["tag_id"]) for tag in tags]
    return {
        "schema_version": "2.0", "layout_id": "comp3-dense-apriltag-layout-v2",
        "map_id": store.data["map_id"], "status": "optional_synthetic_demo_layout",
        "family": "AprilTag 36h11", "maximum_tag_id": 586,
        "nominal_max_graph_path_opportunity_spacing_m": MAX_OPPORTUNITY_SPACING_M,
        "important_note": "Coverage opportunity is not camera detection. Lighting, distance, occlusion, print scale, motion blur and viewing angle still govern detection.",
        "retained_checkpoint_ids": [200, 201, 202],
        "tags": sorted(tags, key=lambda item: int(item["tag_id"])),
        "practical_subset_tag_ids": sorted(int(tag["tag_id"]) for tag in tags if tag["practical_subset"]),
        "coverage_report": {
            "edge_count": len(edge_reports), "tag_count": len(tags),
            "unique_ids": len(tag_ids) == len(set(tag_ids)),
            "all_edges_pass": all(bool(item["passes"]) for item in edge_reports),
            "observed_maximum_spacing_m": max(float(item["maximum_spacing_m"]) for item in edge_reports),
            "edges": edge_reports,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "v2" / "dense_apriltag_layout.json")
    args = parser.parse_args()
    layout = generate()
    report = layout["coverage_report"]
    if not report["unique_ids"] or not report["all_edges_pass"]:
        raise RuntimeError("Dense layout failed uniqueness or spacing validation")
    if max(int(tag["tag_id"]) for tag in layout["tags"]) > int(layout["maximum_tag_id"]):
        raise RuntimeError("Tag ID exceeds the AprilTag 36h11 dictionary")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    print(f"validated {report['tag_count']} unique tags across {report['edge_count']} edges; max spacing {report['observed_maximum_spacing_m']:.2f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
