"""Run deterministic Phase 7D free-walk and adaptive-localization scenarios."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)

from .sensors import SensorConfig
from .spatial_simulation import SpatialNavigationSimulation


DEFAULT_OUTPUT = Path(
    "component3/evaluation/research_archive/01_navigation_engine/"
    "phase_7d_deterministic_evaluation.json"
)
SEED = 6042


def _walk_edge(simulation: SpatialNavigationSimulation, target: str) -> None:
    simulation.choose_free_walk_edge(target)
    for _ in range(200):
        state = simulation.step()
        if state["status"] == "free_walk_stopped":
            return
    raise RuntimeError(f"Free walk did not reach {target}")


def _walk_path(
    simulation: SpatialNavigationSimulation, path: tuple[str, ...]
) -> None:
    for target in path[1:]:
        _walk_edge(simulation, target)


def _complete_baseline() -> dict[str, Any]:
    simulation = SpatialNavigationSimulation(sensor_config=SensorConfig(seed=SEED))
    simulation.set_products(["SIM-P-001", "SIM-P-006"])
    simulation.start()
    for _ in range(4000):
        state = simulation.snapshot()
        if state["status"] == "complete":
            return state
        if state["status"] == "awaiting_product_confirmation":
            simulation.confirm_product()
        else:
            simulation.step()
    raise RuntimeError("Fixed-route baseline did not complete")


def run_evaluation(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    baseline = _complete_baseline()

    adaptive = SpatialNavigationSimulation(
        sensor_config=SensorConfig(seed=SEED), speed_m_s=1.6
    )
    adaptive.enter_free_walk()
    path_to_other_shelf = dijkstra_shortest_path(
        adaptive.graph, adaptive.entrance_node_id, "N1_4"
    )
    _walk_path(adaptive, path_to_other_shelf.node_ids)
    other_shelf_state = adaptive.snapshot()
    path_to_checkpoint = dijkstra_shortest_path(
        adaptive.graph, "N1_4", adaptive.checkout_node_id
    )
    _walk_path(adaptive, path_to_checkpoint.node_ids)
    before = adaptive.snapshot()
    before_error = before["position_error_m"]
    before_cost = before["route_distance_m"]
    corrected = adaptive.observe_checkpoint(
        {
            "tag_id": 202,
            "timestamp_s": before["simulation_time_s"],
            "detection_source": "adaptive_evaluation",
        }
    )
    correction = corrected["localization_correction_event"]
    replan = corrected["adaptive_replan_history"][-1]

    unknown_sim = SpatialNavigationSimulation()
    unknown_sim.enter_free_walk()
    unknown = unknown_sim.observe_checkpoint(
        {"tag_id": 999, "timestamp_s": 0.25, "detection_source": "adaptive_evaluation"}
    )
    duplicate_sim = SpatialNavigationSimulation()
    duplicate_sim.enter_free_walk()
    duplicate = duplicate_sim.observe_checkpoint(
        {"tag_id": 200, "timestamp_s": 0.25, "detection_source": "adaptive_evaluation"}
    )
    implausible_sim = SpatialNavigationSimulation()
    implausible_sim.enter_free_walk()
    implausible_before = implausible_sim.snapshot()
    implausible = implausible_sim.observe_checkpoint(
        {"tag_id": 202, "timestamp_s": 0.25, "detection_source": "adaptive_evaluation"}
    )

    camera = SpatialNavigationSimulation()
    camera.set_products([])
    camera.start_camera_evaluation()
    camera.camera_reconnected()
    camera.observe_camera_detection(200, 0.25)
    camera.step()
    interrupted = camera.camera_stopped()
    resumed = camera.camera_reconnected()

    observations = [
        corrected["observed_checkpoint"],
        unknown["observed_checkpoint"],
        duplicate["observed_checkpoint"],
        implausible["observed_checkpoint"],
    ]
    accepted = sum(bool(item["accepted"]) for item in observations)
    result = {
        "milestone": "C3-P7D",
        "data_classification": "deterministic_synthetic_software_evaluation",
        "physical_camera_used": False,
        "physical_trolley_used": False,
        "seed": SEED,
        "fixed_timestep_s": baseline["fixed_timestep_s"],
        "speed_m_s": {"baseline": 0.8, "free_walk": 1.6},
        "map_id": baseline["map_id"],
        "scenarios": {
            "A_follow_original_route": {
                "status": baseline["status"],
                "completed": baseline["status"] == "complete",
                "products_confirmed": len(baseline["collected_product_ids"]),
                "products_requested": len(baseline["selected_product_ids"]),
                "simulation_time_s": baseline["simulation_time_s"],
                "route_revisions": baseline["route_revision"],
            },
            "B_free_walk_to_other_location": {
                "target_product": "Milk carton",
                "target_pickup_node_id": "N1_4",
                "path_node_ids": list(path_to_other_shelf.node_ids),
                "path_distance_m": path_to_other_shelf.total_distance_m,
                "final_node_id": other_shelf_state["current_node_id"],
                "movement_constrained_to_graph": True,
            },
            "C_D_E_off_route_accept_correct_replan": {
                "observation": corrected["observed_checkpoint"],
                "localization_error_before_m": before_error,
                "localization_error_after_m": corrected["position_error_m"],
                "correction_distance_m": correction["correction_m"],
                "route_cost_before_m": before_cost,
                "route_cost_after_m": corrected["route_distance_m"],
                "partial_edge_distance_m": replan["partial_edge_distance_m"],
                "replanning_computation_ms": replan["replanning_computation_ms"],
                "route_revision_count": corrected["route_revision"],
                "ground_truth_unchanged_by_scan": corrected["ground_truth"] == before["ground_truth"],
                "shopping_list_preserved": corrected["selected_product_ids"] == before["selected_product_ids"],
                "collected_products_preserved": corrected["collected_product_ids"] == before["collected_product_ids"],
            },
            "F_unknown_tag": unknown["observed_checkpoint"],
            "G_duplicate_tag": duplicate["observed_checkpoint"],
            "H_spatially_implausible_tag": {
                **implausible["observed_checkpoint"],
                "estimate_unchanged": implausible["estimate"] == implausible_before["estimate"],
                "confirmed_checkpoint_unchanged": implausible["last_confirmed_checkpoint"] == implausible_before["last_confirmed_checkpoint"],
            },
            "I_J_camera_interruption_resume": {
                "observation_injected_for_software_evaluation": True,
                "status_after_interruption": interrupted["status"],
                "status_after_resume": resumed["status"],
                "resumed": resumed["status"] == "navigating" and resumed["running"],
            },
        },
        "metrics": {
            "checkpoint_observations": len(observations),
            "checkpoint_accepted": accepted,
            "checkpoint_rejected": len(observations) - accepted,
            "acceptance_rate": accepted / len(observations),
            "rejection_rate": (len(observations) - accepted) / len(observations),
            "localization_error_before_m": before_error,
            "localization_error_after_m": corrected["position_error_m"],
            "localization_error_change_m": corrected["position_error_m"] - before_error,
            "correction_distance_m": correction["correction_m"],
            "route_cost_before_m": before_cost,
            "route_cost_after_m": corrected["route_distance_m"],
            "replanning_computation_ms": replan["replanning_computation_ms"],
            "route_revision_count": corrected["route_revision"],
            "baseline_completion_rate": 1.0 if baseline["status"] == "complete" else 0.0,
            "baseline_completion_denominator": 1,
        },
        "limitations": [
            "All movement, sensor noise, checkpoints and ground truth are synthetic.",
            "Camera interruption uses a direct software callback; no physical camera was opened.",
            "One deterministic trial per scenario is functional evidence, not a population accuracy estimate.",
            "Ground truth is used only for reported evaluation error, not checkpoint acceptance.",
        ],
    }
    if not all(math.isfinite(value) for value in (
        before_error, corrected["position_error_m"], correction["correction_m"],
        replan["replanning_computation_ms"],
    )):
        raise RuntimeError("Evaluation produced a non-finite metric")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    print(json.dumps(run_evaluation(arguments.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
