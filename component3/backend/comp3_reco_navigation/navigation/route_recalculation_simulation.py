"""Reproducible evaluation of rerouting after confirmed route deviation."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import random
from typing import Any, Sequence

import cv2
import numpy as np

from .deviation import RouteDeviationMonitor
from .dead_reckoning import PositionEstimate
from .held_karp import held_karp_route
from .route_manager import (
    RouteManager,
    RouteRecalculation,
    localize_position_to_graph,
)
from .store_graph import DEFAULT_STORE_GRAPH_PATH, StoreGraph, load_store_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "component3/evaluation/route_recalculation"
DEFAULT_EVIDENCE_ROOT = (
    REPOSITORY_ROOT
    / "component3/docs/research_evidence/05_position_tracking/screenshots"
)

SEED = 5052
SNAP_DISTANCE_M = 1.5
SAMPLE_INTERVAL_S = 0.5
DEVIATION_OFFSET_M = 1.2


def _position_on_deviation_side(
    graph: StoreGraph,
    route: Sequence[str],
    timestamp_s: float,
    offset_m: float = DEVIATION_OFFSET_M,
) -> PositionEstimate:
    """Create a deterministic off-route estimate normal to the first segment."""
    start = graph.node(route[0])
    end = graph.node(route[1])
    dx = end.x_m - start.x_m
    dy = end.y_m - start.y_m
    length = math.hypot(dx, dy)
    return PositionEstimate(
        x_m=(start.x_m + end.x_m) / 2.0 - dy / length * offset_m,
        y_m=(start.y_m + end.y_m) / 2.0 + dx / length * offset_m,
        heading_rad=0.0,
        timestamp_s=timestamp_s,
    )


def _run_confirmed_deviation(
    manager: RouteManager,
    position: PositionEstimate,
    *,
    repeats: int = 3,
) -> tuple[RouteRecalculation | None, int]:
    """Feed identical sensor estimates until detector entry is confirmed."""
    monitor = RouteDeviationMonitor(
        manager.graph,
        manager.current_route,
        enter_confirmations=3,
        recovery_confirmations=2,
    )
    result: RouteRecalculation | None = None
    confirmation_sample: int | None = None
    for index in range(repeats):
        sample = PositionEstimate(
            position.x_m,
            position.y_m,
            position.heading_rad,
            position.timestamp_s + index * SAMPLE_INTERVAL_S,
        )
        state = monitor.update(sample)
        if state.entered_deviation:
            confirmation_sample = index
        attempt = manager.process_position(sample, state)
        if attempt is not None:
            result = attempt
    return result, confirmation_sample if confirmation_sample is not None else -1


def _run_scenario(
    name: str,
    graph: StoreGraph,
    stops: Sequence[str],
    *,
    mode: str,
    deviation_offset_m: float = DEVIATION_OFFSET_M,
) -> dict[str, Any]:
    """Run one isolated scenario; truth expectations never enter routing."""
    manager = RouteManager(
        graph,
        "ENT" if "ENT" in graph else "A",
        stops,
        "CHK" if "CHK" in graph else "C",
        max_snapping_distance_m=SNAP_DISTANCE_M,
    )
    original_route = manager.current_route
    original_distance = manager.current_route_distance_m
    attempt: RouteRecalculation | None = None
    confirmation_sample = -1
    extra_reroutes = 0
    trigger_position: PositionEstimate | None = None

    if mode == "normal":
        monitor = RouteDeviationMonitor(graph, manager.current_route)
        for index, node_id in enumerate(manager.current_route):
            node = graph.node(node_id)
            position = PositionEstimate(
                node.x_m, node.y_m, 0.0, index * SAMPLE_INTERVAL_S
            )
            state = monitor.update(position)
            if manager.process_position(position, state) is not None:
                extra_reroutes += 1
    elif mode == "brief":
        monitor = RouteDeviationMonitor(graph, manager.current_route)
        base = _position_on_deviation_side(graph, manager.current_route, 0.0)
        for index in range(6):
            if index == 2:
                position = base
            else:
                node = graph.node(manager.current_route[0])
                position = PositionEstimate(
                    node.x_m, node.y_m, 0.0, index * SAMPLE_INTERVAL_S
                )
            state = monitor.update(position)
            if manager.process_position(position, state) is not None:
                extra_reroutes += 1
    elif mode in {"sustained", "repeated"}:
        base = _position_on_deviation_side(
            graph, manager.current_route, 1.0, deviation_offset_m
        )
        trigger_position = base
        attempt, confirmation_sample = _run_confirmed_deviation(
            manager, base, repeats=6 if mode == "repeated" else 3
        )
        extra_reroutes = max(0, len(manager.rerouting_history) - int(attempt is not None))
    elif mode == "far":
        far = PositionEstimate(100.0, 100.0, 0.0, 2.0)
        trigger_position = far
        attempt, confirmation_sample = _run_confirmed_deviation(
            manager, far, repeats=3
        )
    elif mode == "invalid":
        invalid_localization = localize_position_to_graph(
            graph, object(), SNAP_DISTANCE_M  # type: ignore[arg-type]
        )
        if invalid_localization.failure_reason != "invalid_position":
            raise RuntimeError("Invalid position did not fail graph localization")
    elif mode == "unreachable":
        offroute = PositionEstimate(10.2, 0.0, 0.0, 2.0)
        trigger_position = offroute
        attempt, confirmation_sample = _run_confirmed_deviation(
            manager, offroute, repeats=3
        )
    elif mode == "visit":
        first_stop = manager.remaining_destinations[0]
        visit = manager.confirm_destination_visit(first_stop, 4.0)
        if not visit.confirmed:
            raise RuntimeError(f"Explicit visit failed unexpectedly: {visit.failure_reason}")
    elif mode == "return":
        offroute = _position_on_deviation_side(
            graph, manager.current_route, 1.0, deviation_offset_m
        )
        trigger_position = offroute
        attempt, confirmation_sample = _run_confirmed_deviation(
            manager, offroute, repeats=3
        )
        if attempt is None or not attempt.successful:
            raise RuntimeError("Expected initial return-scenario reroute to succeed")
        monitor = RouteDeviationMonitor(graph, manager.current_route)
        for index, node_id in enumerate(manager.current_route):
            node = graph.node(node_id)
            position = PositionEstimate(
                node.x_m,
                node.y_m,
                0.0,
                offroute.timestamp_s + 3.0 + index * SAMPLE_INTERVAL_S,
            )
            state = monitor.update(position)
            if manager.process_position(position, state) is not None:
                extra_reroutes += 1
    else:
        raise ValueError(f"Unknown simulation mode: {mode}")

    successful_attempts = [
        record for record in manager.rerouting_history if record.successful
    ]
    failed_attempts = [
        record for record in manager.rerouting_history if not record.successful
    ]
    result_record = attempt or (manager.rerouting_history[-1] if manager.rerouting_history else None)
    return {
        "scenario": name,
        "mode": mode,
        "expected_reroute": mode in {"sustained", "repeated", "far", "unreachable", "return"},
        "original_route": " ".join(original_route),
        "new_route": " ".join(manager.current_route),
        "remaining_destinations_before": " ".join(stops),
        "remaining_destinations_after": " ".join(manager.remaining_destinations),
        "visited_destinations": " ".join(manager.visited_destinations),
        "reroute_attempts": len(manager.rerouting_history),
        "successful_reroutes": len(successful_attempts),
        "failed_reroutes": len(failed_attempts),
        "false_reroute_triggers": extra_reroutes + int(
            mode in {"normal", "brief"} and bool(manager.rerouting_history)
        ),
        "missed_reroute_triggers": int(
            mode in {"sustained", "repeated", "return"}
            and not successful_attempts
        ),
        "detection_delay_samples": 0 if attempt and attempt.successful else "",
        "detection_delay_s": (
            f"{attempt.delay_s:.3f}" if attempt and attempt.successful else ""
        ),
        "previous_route_distance_m": (
            f"{result_record.previous_route_distance_m:.6f}" if result_record else f"{original_distance:.6f}"
        ),
        "new_route_distance_m": (
            f"{result_record.new_route_distance_m:.6f}"
            if result_record and result_record.successful
            and result_record.new_route_distance_m is not None
            else ""
        ),
        "route_distance_change_m": (
            f"{result_record.new_route_distance_m - result_record.previous_route_distance_m:.6f}"
            if result_record and result_record.successful
            and result_record.new_route_distance_m is not None
            else ""
        ),
        "remaining_stops_preserved": int(
            not result_record
            or not result_record.successful
            or result_record.remaining_destinations == manager.remaining_destinations
        ),
        "checkout_preserved": int(
            not result_record
            or not result_record.successful
            or manager.current_route[-1] == manager.checkout_node_id
        ),
        "duplicate_reroute_suppressed": int(mode == "repeated" and len(manager.rerouting_history) == 1),
        "confirmation_sample_index": confirmation_sample,
        "failure_reason": (
            result_record.failure_reason
            if result_record
            else (
                "invalid_position"
                if mode == "invalid"
                else ""
            )
        ),
        "_manager": manager,
        "_attempt": attempt,
        "_trigger_position": trigger_position,
    }


def build_evaluation_rows(graph: StoreGraph) -> list[dict[str, Any]]:
    """Execute the twelve required route-management scenarios."""
    rng = random.Random(SEED)
    offsets = {
        name: DEVIATION_OFFSET_M + rng.uniform(-0.01, 0.01)
        for name in (
            "sustained_deviation_success",
            "multiple_remaining_stops",
            "one_remaining_stop",
            "no_remaining_stops",
            "repeated_deviated_samples",
            "return_to_route_after_reroute",
        )
    }
    scenarios: list[tuple[str, StoreGraph, Sequence[str], str]] = [
        ("normal_route_following", graph, ("B1", "B3", "B5"), "normal"),
        ("brief_deviation_no_reroute", graph, ("B1", "B3", "B5"), "brief"),
        ("sustained_deviation_success", graph, ("B1", "B3", "B5"), "sustained"),
        ("multiple_remaining_stops", graph, ("B1", "B3", "B5"), "sustained"),
        ("one_remaining_stop", graph, ("B5",), "sustained"),
        ("no_remaining_stops", graph, (), "sustained"),
        ("invalid_position_estimate", graph, ("B1", "B3"), "invalid"),
        ("position_beyond_snap_limit", graph, ("B1", "B3"), "far"),
        (
            "unreachable_destination",
            StoreGraph.from_dict(
                {
                    "nodes": [
                        {"id": "A", "name": "A", "type": "test", "x_m": 0, "y_m": 0},
                        {"id": "B", "name": "B", "type": "test", "x_m": 1, "y_m": 0},
                        {"id": "C", "name": "C", "type": "test", "x_m": 2, "y_m": 0},
                        {"id": "D", "name": "D", "type": "test", "x_m": 10, "y_m": 0},
                        {"id": "E", "name": "E", "type": "test", "x_m": 11, "y_m": 0},
                    ],
                    "edges": [
                        {"source": "A", "target": "B", "distance_m": 1.0},
                        {"source": "B", "target": "C", "distance_m": 1.0},
                        {"source": "D", "target": "E", "distance_m": 1.0},
                    ],
                }
            ),
            ("B",),
            "unreachable",
        ),
        ("repeated_deviated_samples", graph, ("B1", "B3"), "repeated"),
        ("explicit_visit_confirmation", graph, ("B1", "B3", "B5"), "visit"),
        ("return_to_route_after_reroute", graph, ("B1", "B3", "B5"), "return"),
    ]
    return [
        _run_scenario(
            name,
            scenario_graph,
            stops,
            mode=mode,
            deviation_offset_m=offsets.get(name, DEVIATION_OFFSET_M),
        )
        for name, scenario_graph, stops, mode in scenarios
    ]


def _aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Calculate counts and means using explicit scenario/attempt denominators."""
    attempted = [
        row for row in rows if row["reroute_attempts"] > 0
    ]
    successful = sum(row["successful_reroutes"] for row in rows)
    failed = sum(row["failed_reroutes"] for row in rows)
    confirmed_expected = [
        row for row in rows if row["expected_reroute"]
    ]
    detected_expected = [
        row for row in confirmed_expected if row["reroute_attempts"] > 0
    ]
    valid_delays = [
        float(row["detection_delay_s"])
        for row in rows
        if row["detection_delay_s"] != ""
    ]
    route_changes = [
        float(row["route_distance_change_m"])
        for row in rows
        if row["route_distance_change_m"] != ""
    ]
    return {
        "seed": SEED,
        "scenario_count": len(rows),
        "successful_reroutes": successful,
        "failed_reroutes": failed,
        "false_reroute_triggers": sum(row["false_reroute_triggers"] for row in rows),
        "missed_reroute_triggers": sum(row["missed_reroute_triggers"] for row in rows),
        "expected_trigger_scenarios": len(confirmed_expected),
        "trigger_scenarios_attempted": len(detected_expected),
        "mean_confirmed_to_reroute_delay_s": (
            sum(valid_delays) / len(valid_delays) if valid_delays else 0.0
        ),
        "mean_route_distance_change_m": (
            sum(route_changes) / len(route_changes) if route_changes else 0.0
        ),
        "remaining_stop_preservation_rate": (
            sum(row["remaining_stops_preserved"] for row in attempted) / len(attempted)
            if attempted
            else 1.0
        ),
        "checkout_preservation_rate": (
            sum(row["checkout_preserved"] for row in attempted) / len(attempted)
            if attempted
            else 1.0
        ),
        "duplicate_reroutes_suppressed": sum(
            row["duplicate_reroute_suppressed"] for row in rows
        ),
        "route_change_attempt_count": len(attempted),
    }


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    """Write deterministic CSV files with stable headers and line endings."""
    if not rows:
        raise ValueError("CSV requires at least one row")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _clean_scenario_row(row: dict[str, Any]) -> dict[str, Any]:
    """Remove in-memory objects from the serialized scenario event record."""
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _draw_evidence(
    path: Path,
    graph: StoreGraph,
    successful_row: dict[str, Any],
    failed_row: dict[str, Any],
) -> None:
    """Render original and recalculated graph paths plus a failure summary."""
    image = np.full((900, 1400, 3), 255, dtype=np.uint8)
    left, top, width, height = 95, 145, 900, 650
    scale = min(width / 24.0, height / 18.0)
    map_width, map_height = 24.0 * scale, 18.0 * scale
    offset_x = left + (width - map_width) / 2
    offset_y = top + (height - map_height) / 2

    def pixel(node_id: str) -> tuple[int, int]:
        node = graph.node(node_id)
        return (
            round(offset_x + node.x_m * scale),
            round(offset_y + map_height - node.y_m * scale),
        )

    cv2.putText(image, "Confirmed-deviation route recalculation", (80, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (31, 41, 55), 2, cv2.LINE_AA)
    cv2.putText(image, "Node-only routing uses graph edges; marker is projected deviation estimate", (80, 91), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (71, 85, 105), 1, cv2.LINE_AA)
    for edge in graph.edges:
        cv2.line(image, pixel(edge.source), pixel(edge.target), (220, 225, 232), 2, cv2.LINE_AA)
    original = tuple(successful_row["original_route"].split())
    new_route = tuple(successful_row["new_route"].split())
    original_points = np.array([pixel(node_id) for node_id in original], dtype=np.int32)
    new_points = np.array([pixel(node_id) for node_id in new_route], dtype=np.int32)
    cv2.polylines(image, [original_points], False, (190, 80, 65), 3, cv2.LINE_AA)
    cv2.polylines(image, [new_points], False, (50, 130, 45), 4, cv2.LINE_AA)
    for node_id in set(successful_row["remaining_destinations_before"].split()):
        if node_id:
            center = pixel(node_id)
            cv2.circle(image, center, 9, (20, 145, 210), -1, cv2.LINE_AA)
            cv2.putText(image, node_id, (center[0] + 8, center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (31, 41, 55), 1, cv2.LINE_AA)
    offroute = successful_row["_trigger_position"]
    if not isinstance(offroute, PositionEstimate):
        raise ValueError("successful evidence scenario has no trigger position")
    trigger = (
        round(offset_x + offroute.x_m * scale),
        round(offset_y + map_height - offroute.y_m * scale),
    )
    cv2.drawMarker(image, trigger, (20, 20, 220), cv2.MARKER_TILTED_CROSS, 24, 3)
    cv2.putText(image, "Remaining confirmed shopping stops", (1040, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (31, 41, 55), 1, cv2.LINE_AA)
    y = 220
    for node_id in successful_row["remaining_destinations_before"].split():
        cv2.circle(image, (1052, y - 5), 7, (20, 145, 210), -1, cv2.LINE_AA)
        cv2.putText(image, node_id, (1070, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (31, 41, 55), 1, cv2.LINE_AA)
        y += 30
    cv2.putText(image, "Successful reroute", (1040, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 115, 40), 2, cv2.LINE_AA)
    cv2.putText(image, f"Distance: {successful_row['previous_route_distance_m']} -> {successful_row['new_route_distance_m']} m", (1040, 380), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.putText(image, "Failed scenario", (1040, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 190), 2, cv2.LINE_AA)
    cv2.putText(image, failed_row["scenario"], (1040, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.putText(image, failed_row["failure_reason"][:42], (1040, 505), cv2.FONT_HERSHEY_SIMPLEX, 0.31, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.line(image, (80, 842), (125, 842), (190, 80, 65), 4, cv2.LINE_AA)
    cv2.putText(image, "Original route", (135, 847), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.line(image, (310, 842), (355, 842), (50, 130, 45), 4, cv2.LINE_AA)
    cv2.putText(image, "Recalculated route", (365, 847), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.drawMarker(image, (600, 842), (20, 20, 220), cv2.MARKER_TILTED_CROSS, 18, 2)
    cv2.putText(image, "Confirmed deviation estimate", (620, 847), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (31, 41, 55), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"OpenCV could not write route-recalculation evidence: {path}")


def run_evaluation(
    graph: StoreGraph | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    """Run scenarios and write event logs, metrics, configuration, and evidence."""
    graph = graph or load_store_graph(DEFAULT_STORE_GRAPH_PATH)
    scenario_rows = build_evaluation_rows(graph)
    clean_rows = [_clean_scenario_row(row) for row in scenario_rows]
    metrics = _aggregate(clean_rows)
    output_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    events_path = output_root / "events.csv"
    _write_csv(events_path, clean_rows)
    metrics_path = output_root / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    config = {
        "seed": SEED,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "position_offset_m": DEVIATION_OFFSET_M,
        "seeded_offset_jitter_m": 0.01,
        "maximum_graph_snapping_distance_m": SNAP_DISTANCE_M,
        "deviation_enter_confirmations": 3,
        "deviation_recovery_confirmations": 2,
        "route_start_node_id": "ENT",
        "checkout_node_id": "CHK",
        "shopping_destinations": ["B1", "B3", "B5"],
        "localization_policy": (
            "Project to nearest valid edge; equal-distance edges choose lexical "
            "unordered endpoints; start at nearer endpoint, lexical tie-break."
        ),
        "node_only_limitation": (
            "The fractional edge position is not represented in Dijkstra/Held-Karp "
            "costs; routing starts at the selected endpoint and omits partial-edge travel."
        ),
        "scenario_count": len(clean_rows),
        "truth_usage": "No ground-truth label is passed to RouteManager.",
        "physical_calibration": False,
    }
    (output_root / "simulation_config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    log = [
        "Component 3 Phase 5B route recalculation simulation",
        f"Seed: {SEED}",
        f"Scenarios: {metrics['scenario_count']}",
        f"Successful reroutes: {metrics['successful_reroutes']}",
        f"Failed reroutes: {metrics['failed_reroutes']}",
        f"False reroute triggers: {metrics['false_reroute_triggers']}",
        f"Missed reroute triggers: {metrics['missed_reroute_triggers']}",
        f"Mean confirmed-to-reroute delay: {metrics['mean_confirmed_to_reroute_delay_s']:.3f} s",
        f"Mean route-distance change: {metrics['mean_route_distance_change_m']:.3f} m",
        f"Remaining-stop preservation: {metrics['remaining_stop_preservation_rate']:.3f}",
        f"Checkout preservation: {metrics['checkout_preservation_rate']:.3f}",
        f"Duplicate reroutes suppressed: {metrics['duplicate_reroutes_suppressed']}",
        "Scenario labels are evaluation controls and are not detector or route-manager inputs.",
        "No hardware accuracy claim is made.",
    ]
    (output_root / "reproducibility.log").write_text(
        "\n".join(log) + "\n", encoding="utf-8"
    )
    successful = next(
        row for row in scenario_rows if row["scenario"] == "sustained_deviation_success"
    )
    failed = next(
        row for row in scenario_rows if row["scenario"] == "position_beyond_snap_limit"
    )
    png_path = evidence_root / "C3-POS-010_route_recalculation.png"
    _draw_evidence(png_path, graph, successful, failed)
    svg_path = evidence_root / "C3-POS-010_route_recalculation.svg"
    svg_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">'
        '<title>Confirmed-deviation route recalculation</title>'
        '<desc>Original planned route, deviation estimate, recalculated route, remaining stops and a failed snap scenario.</desc>'
        f'<image href="{png_path.name}" width="1400" height="900"/></svg>\n',
        encoding="utf-8",
    )
    print("\n".join(log))
    print(f"Events: {events_path}")
    print(f"Metrics: {metrics_path}")
    return metrics


def main() -> int:
    """Run the fixed-seed route-recalculation simulation."""
    run_evaluation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
