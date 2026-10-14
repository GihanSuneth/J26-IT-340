"""Measure Phase 7A automatic guidance using labeled synthetic fixtures."""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import PositionEstimate

from .checkpoint_observations import CheckpointObservation, CheckpointObservationProcessor
from .demo_store import load_demo_store
from .guidance import GuidanceEngine, ProductArrivalMonitor, classify_turn, product_shelf_side
from .spatial_simulation import SpatialNavigationSimulation


OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "evaluation/navigation_simulation"


def _complete_guided_run() -> dict[str, Any]:
    simulation = SpatialNavigationSimulation()
    simulation.start_guided_demo()
    for _ in range(2500):
        if simulation.status == "complete":
            return simulation.snapshot()
        simulation.step()
    raise RuntimeError("Phase 7A guided scenario did not complete")


def evaluate() -> dict[str, Any]:
    """Return metrics with explicit fixtures and denominators."""
    turn_fixtures = [
        ("straight", 0.0, 0.0, "STRAIGHT"),
        ("left", 0.0, math.pi / 2, "TURN_LEFT"),
        ("right", 0.0, -math.pi / 2, "TURN_RIGHT"),
        ("u_turn", 0.0, math.pi, "U_TURN"),
    ]
    turn_results = [
        {"case": name, "expected": expected, "actual": classify_turn(before, after)}
        for name, before, after, expected in turn_fixtures
    ]
    side_fixtures = [
        ("east_north_shelf", 0.0, (0.0, 0.0), (0.0, 1.0), "left"),
        ("west_north_shelf", math.pi, (0.0, 0.0), (0.0, 1.0), "right"),
        ("north_west_shelf", math.pi / 2, (0.0, 0.0), (-1.0, 0.0), "left"),
        ("south_west_shelf", -math.pi / 2, (0.0, 0.0), (-1.0, 0.0), "right"),
    ]
    side_results = [
        {"case": name, "expected": expected, "actual": product_shelf_side(heading, pickup, facing)}
        for name, heading, pickup, facing, expected in side_fixtures
    ]
    arrival_fixtures = [
        ("stable_inside", [(0.8, 0.1), (0.6, 0.1)], 0.2, True),
        ("outside", [(1.4, 0.0), (1.2, 0.0)], 0.2, False),
        ("uncertain_inside", [(0.2, 0.0), (0.1, 0.0)], 0.9, False),
        ("single_inside", [(0.5, 0.0)], 0.2, False),
    ]
    arrival_results = []
    for name, estimates, uncertainty, expected in arrival_fixtures:
        monitor = ProductArrivalMonitor()
        result = None
        for estimate in estimates:
            result = monitor.update(
                target_product_id=name,
                estimated_position_m=estimate,
                pickup_coordinate_m=(0.0, 0.0),
                localization_uncertainty_m=uncertainty,
            )
        arrival_results.append({"case": name, "expected": expected, "actual": bool(result and result.arrived)})

    store = load_demo_store()
    timing_engine = GuidanceEngine(store.graph)
    near_turn, _ = timing_engine.navigation_instruction(
        timestamp=0,
        estimated_heading_rad=math.pi / 2,
        remaining_route=["N1_0", "N1_1"],
        distance_to_route_start_m=1.0,
        active_product=None,
        distance_to_product_m=None,
        next_checkpoint=None,
        distance_to_checkpoint_m=None,
        localization_uncertain=False,
    )
    far_turn, _ = timing_engine.navigation_instruction(
        timestamp=1,
        estimated_heading_rad=math.pi / 2,
        remaining_route=["N1_0", "N1_1"],
        distance_to_route_start_m=1.5,
        active_product=None,
        distance_to_product_m=None,
        next_checkpoint=None,
        distance_to_checkpoint_m=None,
        localization_uncertain=False,
    )
    processor = CheckpointObservationProcessor(store.checkpoint_layout, store.data["map_id"])
    pose = PositionEstimate(2.0, 2.0, 0.0, 0.0)
    near_cp201 = PositionEstimate(12.5, 7.0, 0.0, 6.0)
    observations = [
        (CheckpointObservation(200, 1, "synthetic_evaluation", store.data["map_id"], 1.0), 200, True, pose),
        (CheckpointObservation(200, 2, "synthetic_evaluation", store.data["map_id"], 1.0), 201, False, pose),
        (CheckpointObservation(999, 3, "synthetic_evaluation", store.data["map_id"], 1.0), 201, False, pose),
        (CheckpointObservation(202, 4, "synthetic_evaluation", store.data["map_id"], 1.0), 201, False, pose),
        (CheckpointObservation(201, 5, "synthetic_evaluation", store.data["map_id"], 0.2), 201, False, near_cp201),
        (CheckpointObservation(201, 6, "synthetic_evaluation", store.data["map_id"], 1.0), 201, True, near_cp201),
    ]
    checkpoint_results = []
    for observation, expected_id, expected_acceptance, observation_pose in observations:
        result = processor.process(observation, observation_pose, expected_tag_id=expected_id)
        checkpoint_results.append(
            {"tag_id": observation.tag_id, "expected_acceptance": expected_acceptance, "accepted": result.accepted, "reason": result.reason}
        )

    runs = [_complete_guided_run() for _ in range(3)]
    first = runs[0]
    guidance_types = [item["instruction_type"] for item in first["guidance_events"]]
    product_reached = [item for item in first["guidance_events"] if item["instruction_type"] == "PRODUCT_REACHED"]
    reroute_events = [item for item in first["guidance_events"] if item["instruction_type"] == "REROUTING"]
    metadata_valid = sum(
        bool(product.get("shelf_id") and product.get("shelf_section") and product.get("shelf_level") and product.get("shelf_bay"))
        for product in store.data["products"]
    )
    return {
        "schema_version": "1.0",
        "data_classification": "synthetic_software_evaluation_only",
        "limitations": [
            "No physical trolley, camera, surveyed store, shopper trial, or real POS data was used.",
            "Checkpoint observations are labeled simulator inputs, not live AprilTag camera detections.",
            "Arrival precision and recall apply only to the four declared synthetic fixtures.",
        ],
        "turn_instruction_accuracy": {"correct": sum(x["actual"] == x["expected"] for x in turn_results), "total": len(turn_results), "fixtures": turn_results},
        "shelf_side_accuracy": {"correct": sum(x["actual"] == x["expected"] for x in side_results), "total": len(side_results), "fixtures": side_results},
        "product_metadata_validity": {"valid": metadata_valid, "total": len(store.data["products"])},
        "checkpoint_observations": {"correct_decisions": sum(x["accepted"] == x["expected_acceptance"] for x in checkpoint_results), "total": len(checkpoint_results), "fixtures": checkpoint_results},
        "arrival_classification": {
            "true_positive": sum(x["expected"] and x["actual"] for x in arrival_results),
            "true_negative": sum(not x["expected"] and not x["actual"] for x in arrival_results),
            "false_positive": sum(not x["expected"] and x["actual"] for x in arrival_results),
            "false_negative": sum(x["expected"] and not x["actual"] for x in arrival_results),
            "total": len(arrival_results),
            "fixtures": arrival_results,
        },
        "turn_notification_timing": {
            "correct": int(near_turn.instruction_type == "TURN_RIGHT") + int(far_turn.instruction_type == "STRAIGHT"),
            "total": 2,
            "fixtures": [
                {"distance_m": 1.0, "expected": "TURN_RIGHT", "actual": near_turn.instruction_type},
                {"distance_m": 1.5, "expected": "STRAIGHT", "actual": far_turn.instruction_type},
            ],
        },
        "notification_thresholds_m": {"turn": 1.25, "checkpoint": 1.5, "product": 2.0, "stable_arrival_radius": 1.0},
        "guided_scenario": {
            "runs": 3,
            "deterministic": all(run["events"] == first["events"] and run["guidance_events"] == first["guidance_events"] for run in runs[1:]),
            "completed_runs": sum(run["status"] == "complete" for run in runs),
            "completion_rate": sum(run["status"] == "complete" for run in runs) / len(runs),
            "collected_product_ids": first["collected_product_ids"],
            "checkpoint_sequence": first["detected_checkpoint_ids"],
            "reroute_count": first["reroute_count"],
            "guidance_types": guidance_types,
            "product_arrivals_with_shelf_level_and_side": sum(item["shelf_level"] is not None and item["shelf_side"] in {"left", "right"} for item in product_reached),
            "product_arrivals": len(product_reached),
            "reroute_guidance_updates": len(reroute_events),
            "simulation_time_s": first["simulation_time_s"],
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_ROOT / "phase7a_guidance_evaluation.json"
    csv_path = OUTPUT_ROOT / "phase7a_guidance_events.csv"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    snapshot = _complete_guided_run()
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "event_id",
            "timestamp",
            "instruction_type",
            "instruction_text",
            "distance_to_maneuver_m",
            "target_node",
            "target_product_id",
            "target_shelf_id",
            "shelf_section",
            "shelf_level",
            "shelf_side",
            "route_revision",
        ],
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(snapshot["guidance_events"])
    csv_path.write_text(stream.getvalue(), encoding="utf-8")
    return json_path, csv_path


def main() -> int:
    report = evaluate()
    paths = write_outputs(report)
    print(json.dumps({"outputs": [str(path) for path in paths], "metrics": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
