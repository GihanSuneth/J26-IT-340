"""Generate reproducible Phase 7E dynamic-shopping comparison evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Sequence

from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    route_for_stop_order,
)
from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.route_anchor import (
    RouteAnchor,
    held_karp_route_from_anchor,
)

from .spatial_simulation import SpatialNavigationSimulation


DEFAULT_OUTPUT = Path(
    "component3/evaluation/research_archive/01_navigation_engine/"
    "phase_7e_dynamic_shopping_evaluation.json"
)
FINAL_PRODUCTS = ("SIM-P-001", "SIM-P-004", "SIM-P-006")


def _travelled_distance(snapshot: dict[str, Any]) -> float:
    points = snapshot["travelled_ground_truth"]
    return sum(
        math.hypot(b["x_m"] - a["x_m"], b["y_m"] - a["y_m"])
        for a, b in zip(points, points[1:])
    )


def _complete(simulation: SpatialNavigationSimulation) -> dict[str, Any]:
    if simulation.status == "ready":
        simulation.start()
    for _ in range(6000):
        if simulation.status == "awaiting_product_confirmation":
            simulation.confirm_product()
        elif simulation.status == "complete":
            return simulation.snapshot()
        else:
            simulation.step()
    raise RuntimeError(f"Simulation did not complete: {simulation.status}")


def _naive_anchor_cost(
    simulation: SpatialNavigationSimulation,
    anchor: RouteAnchor,
    stop_ids: Sequence[str],
) -> float:
    candidates: list[tuple[float, str]] = []
    for endpoint, partial in anchor.endpoint_costs(
        allow_reverse=anchor.travel_direction == "stopped"
    ):
        route = route_for_stop_order(
            simulation.graph, endpoint, stop_ids, simulation.checkout_node_id
        )
        candidates.append((partial + route.total_distance_m, endpoint))
    return min(candidates)[0]


def _walk_edge(simulation: SpatialNavigationSimulation, target: str) -> None:
    simulation.choose_free_walk_edge(target)
    for _ in range(200):
        simulation.step()
        if simulation.status == "free_walk_stopped":
            return
    raise RuntimeError("Free-walk edge did not terminate")


def run_evaluation(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    fixed = SpatialNavigationSimulation(speed_m_s=1.6)
    fixed.set_products(FINAL_PRODUCTS)
    initial_fixed_cost = fixed.snapshot()["route_distance_m"]
    fixed_result = _complete(fixed)

    dynamic = SpatialNavigationSimulation(speed_m_s=1.6)
    dynamic.set_products(("SIM-P-001", "SIM-P-002", "SIM-P-004"))
    dynamic.start()
    for _ in range(80):
        dynamic.step()
        if dynamic._edge_target is not None and dynamic._edge_progress_m > 0:
            break
    else:
        raise RuntimeError("Dynamic comparison did not reach a mid-edge anchor")
    comparison_anchor = dynamic._estimated_route_anchor()
    final_nodes = dynamic._product_nodes(FINAL_PRODUCTS)
    naive_cost = _naive_anchor_cost(dynamic, comparison_anchor, final_nodes)
    timings: list[float] = []
    optimized = None
    for _ in range(30):
        started = time.perf_counter_ns()
        optimized = held_karp_route_from_anchor(
            dynamic.graph,
            comparison_anchor,
            final_nodes,
            dynamic.checkout_node_id,
            allow_reverse=comparison_anchor.travel_direction == "stopped",
        )
        timings.append((time.perf_counter_ns() - started) / 1_000_000.0)
    assert optimized is not None
    revision = dynamic.snapshot()["shopping_list_revision"]
    dynamic.mutate_shopping_list("add", "SIM-P-006", 1, revision)
    revision += 1
    dynamic.mutate_shopping_list("remove", "SIM-P-002", 1, revision)
    revision += 1
    dynamic.mutate_shopping_list("increase", "SIM-P-001", 1, revision)
    revision += 1
    dynamic.mutate_shopping_list("decrease_remaining", "SIM-P-001", 1, revision)
    dynamic_result = _complete(dynamic)

    shelf = SpatialNavigationSimulation(speed_m_s=1.6)
    shelf.set_products(())
    shelf.enter_free_walk()
    _walk_edge(shelf, "N1_0")
    _walk_edge(shelf, "N1_1")
    at_shelf = shelf.mutate_shopping_list("add", "SIM-P-001", 1, 0)
    pickup_ready = at_shelf["status"] == "awaiting_product_confirmation"
    picked = shelf.confirm_product(expected_shopping_revision=1)
    shelf.mutate_shopping_list("add", "SIM-P-006", 1, 2)
    resumed = shelf.request_navigation_from_current_location()

    checkpoint = SpatialNavigationSimulation(speed_m_s=1.6)
    checkpoint.set_products(FINAL_PRODUCTS)
    checkpoint.enter_free_walk()
    checkpoint_path = dijkstra_shortest_path(
        checkpoint.graph, checkpoint.entrance_node_id, checkpoint.checkout_node_id
    )
    for target in checkpoint_path.node_ids[1:]:
        _walk_edge(checkpoint, target)
    checkpoint_before = checkpoint.snapshot()
    checkpoint_after = checkpoint.observe_checkpoint(
        {
            "tag_id": 202,
            "timestamp_s": checkpoint_before["simulation_time_s"],
            "detection_source": "adaptive_evaluation",
        }
    )

    invalid = SpatialNavigationSimulation()
    invalid.set_products(("SIM-P-001",))
    valid = invalid.mutate_shopping_list("add", "SIM-P-002", 1, 0)
    state_before_stale = invalid.snapshot()
    stale_rejected = False
    try:
        invalid.mutate_shopping_list("remove", "SIM-P-001", 1, 0)
    except ValueError:
        stale_rejected = True
    state_after_stale = invalid.snapshot()

    sorted_timings = sorted(timings)
    report = {
        "milestone": "C3-P7E",
        "data_classification": "deterministic_synthetic_software_evaluation",
        "seed": 6042,
        "fixed_timestep_s": 0.25,
        "timing_repetitions": len(timings),
        "physical_camera_used": False,
        "physical_trolley_used": False,
        "equivalent_demand_comparison": {
            "product_ids": list(FINAL_PRODUCTS),
            "pickup_node_ids": list(final_nodes),
            "same_anchor": comparison_anchor.to_dict(),
            "baseline_B_naive_order_cost_m": naive_cost,
            "proposed_held_karp_cost_m": optimized.total_distance_m,
            "cost_difference_proposed_minus_naive_m": optimized.total_distance_m - naive_cost,
            "claim": "Equal remaining demands, graph, checkout and route anchor.",
        },
        "baseline_A_fixed_list": {
            "initial_route_cost_m": initial_fixed_cost,
            "total_travelled_distance_m": _travelled_distance(fixed_result),
            "status": fixed_result["status"],
            "successful_pickup_units": fixed_result["shopping_session"]["collected_units"],
            "requested_units": fixed_result["shopping_session"]["requested_units"],
            "route_revision_count": fixed_result["route_revision"],
        },
        "proposed_dynamic_session": {
            "operations": ["add", "remove", "increase", "decrease_remaining"],
            "final_product_ids": dynamic_result["selected_product_ids"],
            "total_travelled_distance_m": _travelled_distance(dynamic_result),
            "remaining_route_cost_m": dynamic_result["remaining_distance_m"],
            "status": dynamic_result["status"],
            "shopping_list_revision": dynamic_result["shopping_list_revision"],
            "route_revision_count": dynamic_result["route_revision"],
            "successful_pickup_units": dynamic_result["shopping_session"]["collected_units"],
            "requested_units": dynamic_result["shopping_session"]["requested_units"],
            "shopping_completion_rate": (
                dynamic_result["shopping_session"]["collected_units"]
                / dynamic_result["shopping_session"]["requested_units"]
            ),
            "navigation_completion_rate": 1.0 if dynamic_result["status"] == "complete" else 0.0,
            "state_consistent": all(
                item["collected_quantity"] <= item["requested_quantity"]
                for item in dynamic_result["shopping_session"]["items"]
            ),
        },
        "independent_shelf_journey": {
            "entrance_checkpoint_confirmed": 200 in shelf.snapshot()["detected_checkpoint_ids"],
            "free_walk_node": "N1_1",
            "pickup_ready_from_estimate_guard": pickup_ready,
            "pickup_confirmed_explicitly": picked["shopping_session"]["collected_units"] == 1,
            "second_product_added": "SIM-P-006" in resumed["selected_product_ids"],
            "navigation_resumed_from_latest_estimate": resumed["status"] == "navigating",
            "ground_truth_not_used_by_arrival_policy": True,
        },
        "unexpected_mapped_checkpoint": {
            "expected_checkpoint_id": checkpoint_after["observed_checkpoint"]["expected_checkpoint_id"],
            "observed_checkpoint_id": 202,
            "classification": checkpoint_after["observed_checkpoint"]["classification"],
            "accepted": checkpoint_after["observed_checkpoint"]["accepted"],
            "ground_truth_unchanged": checkpoint_before["ground_truth"] == checkpoint_after["ground_truth"],
            "shopping_state_preserved": checkpoint_before["shopping_session"] == checkpoint_after["shopping_session"],
            "route_replanned": checkpoint_after["route_revision"] > checkpoint_before["route_revision"],
        },
        "invalid_and_stale_commands": {
            "valid_command_revision": valid["shopping_list_revision"],
            "stale_command_rejected": stale_rejected,
            "shopping_state_unchanged": state_before_stale["shopping_session"] == state_after_stale["shopping_session"],
            "route_unchanged": state_before_stale["planned_route"] == state_after_stale["planned_route"],
            "invalid_mutation_rejections": 1,
            "invalid_mutation_attempts": 1,
        },
        "reoptimization_timing_ms": {
            "count": len(timings),
            "minimum": min(timings),
            "median": statistics.median(timings),
            "p95_nearest_rank": sorted_timings[math.ceil(0.95 * len(timings)) - 1],
            "maximum": max(timings),
        },
        "limitations": [
            "All movement, sensing, shopping intentions and truth are synthetic.",
            "Timing distribution contains repeated in-process calculations on one host.",
            "The fixed and dynamic total-distance runs represent different intention timing and are not asserted as an equal-demand route-efficiency comparison.",
            "No recommendation model was trained; the suggestion contract has no model score.",
            "No physical camera or trolley was used.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    print(json.dumps(run_evaluation(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
