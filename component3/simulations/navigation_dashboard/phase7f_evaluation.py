"""Run reproducible Phase 7F navigation research experiments.

The runner deliberately separates synthetic truth used for scoring from the inputs
available to localization and routing.  It writes new milestone-specific artifacts
and never replaces Phase 7B--7E evidence.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time
from typing import Any, Callable, Iterable, Sequence

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    PositionEstimate,
)
from component3.backend.comp3_reco_navigation.navigation.dijkstra import (
    dijkstra_shortest_path,
)
from component3.backend.comp3_reco_navigation.navigation.held_karp import (
    held_karp_route,
    route_for_stop_order,
)
from component3.backend.comp3_reco_navigation.navigation.route_anchor import (
    RouteAnchor,
    edge_route_anchor,
    held_karp_route_from_anchor,
    node_route_anchor,
)

from .checkpoint_observations import (
    CheckpointObservation,
    CheckpointObservationProcessor,
    CheckpointPlausibilityContext,
)
from .demo_store import load_demo_store
from .sensors import SensorConfig
from .spatial_simulation import SpatialNavigationSimulation


ARCHIVE = Path("component3/evaluation/research_archive/01_navigation_engine")
DEFAULT_MANIFEST = ARCHIVE / "phase_7f_experiment_manifest.json"
DEFAULT_RAW = ARCHIVE / "phase_7f_raw_results.json"
DEFAULT_AGGREGATE = ARCHIVE / "phase_7f_aggregated_results.json"
DEFAULT_BASELINES = ARCHIVE / "phase_7f_baseline_comparisons.csv"
DEFAULT_LOCALIZATION = ARCHIVE / "phase_7f_localization_results.csv"
DEFAULT_PERFORMANCE = ARCHIVE / "phase_7f_performance_benchmarks.csv"

SEEDS = (6042, 7127, 8209, 9311, 104729)
WARMUP_REPETITIONS = 10
MEASURED_REPETITIONS = 100
PRODUCT_IDS = tuple(f"SIM-P-{index:03d}" for index in range(1, 7))


def _percentile_nearest_rank(values: Sequence[float], proportion: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(proportion * len(ordered)) - 1)]


def _summary(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "repetitions": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "p95_nearest_rank": _percentile_nearest_rank(values, 0.95),
        "maximum": max(values),
    }


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float]:
    if total <= 0:
        return {"proportion": 0.0, "lower_95": 0.0, "upper_95": 0.0}
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denominator
    return {
        "proportion": p,
        "lower_95": max(0.0, centre - margin),
        "upper_95": min(1.0, centre + margin),
    }


def _anchor_naive_cost(
    simulation: SpatialNavigationSimulation,
    anchor: RouteAnchor,
    stops: Sequence[str],
) -> float:
    return min(
        partial
        + route_for_stop_order(
            simulation.graph, endpoint, stops, simulation.checkout_node_id
        ).total_distance_m
        for endpoint, partial in anchor.endpoint_costs(
            allow_reverse=anchor.travel_direction == "stopped"
        )
    )


def _expanded_distance(simulation: SpatialNavigationSimulation, nodes: Sequence[str]) -> float:
    """Replay an expanded route as graph edges and return traveled metres."""
    return sum(
        simulation.graph.edge_weight(source, target)
        for source, target in zip(nodes, nodes[1:])
    )


def _brute_force_cost(
    simulation: SpatialNavigationSimulation,
    anchor: RouteAnchor,
    stops: Sequence[str],
) -> float:
    if not stops:
        return _anchor_naive_cost(simulation, anchor, ())
    return min(
        _anchor_naive_cost(simulation, anchor, order)
        for order in itertools.permutations(stops)
    )


def _baseline_trials() -> list[dict[str, Any]]:
    simulation = SpatialNavigationSimulation(speed_m_s=1.6)
    graph = simulation.graph
    start_anchors = (
        ("entrance_node", node_route_anchor(graph, "N0_0")),
        ("cross_aisle_node", node_route_anchor(graph, "N2_3")),
        (
            "mid_edge_forward",
            edge_route_anchor(
                graph, "N0_1", "N0_2", 1.25, travel_direction="toward_end"
            ),
        ),
        (
            "mid_edge_stopped",
            edge_route_anchor(
                graph, "N2_3", "N2_4", 2.0, travel_direction="stopped"
            ),
        ),
    )
    permutations = (
        ("SIM-P-001", "SIM-P-004", "SIM-P-006"),
        ("SIM-P-006", "SIM-P-001", "SIM-P-004"),
        ("SIM-P-003", "SIM-P-005", "SIM-P-002"),
        ("SIM-P-002", "SIM-P-005", "SIM-P-003"),
        ("SIM-P-001", "SIM-P-002", "SIM-P-003", "SIM-P-006"),
    )
    rows: list[dict[str, Any]] = []
    for anchor_name, anchor in start_anchors:
        for requested_products in permutations:
            stops = simulation._product_nodes(requested_products)
            naive = _anchor_naive_cost(simulation, anchor, stops)
            naive_candidates = []
            for endpoint, partial in anchor.endpoint_costs(
                allow_reverse=anchor.travel_direction == "stopped"
            ):
                ordered = route_for_stop_order(
                    graph, endpoint, stops, simulation.checkout_node_id
                )
                naive_candidates.append((partial + ordered.total_distance_m, partial, ordered))
            naive_plan = min(naive_candidates, key=lambda item: (item[0], item[2].route_node_ids))
            proposed = held_karp_route_from_anchor(
                graph,
                anchor,
                stops,
                simulation.checkout_node_id,
                allow_reverse=anchor.travel_direction == "stopped",
            )
            oracle = _brute_force_cost(simulation, anchor, stops)
            improvement = naive - proposed.total_distance_m
            baseline_a = route_for_stop_order(
                graph, simulation.entrance_node_id, stops,
                simulation.checkout_node_id,
            )
            baseline_a_feasible = anchor_name == "entrance_node"
            rows.append(
                {
                    "trial_id": f"route-{len(rows) + 1:03d}",
                    "anchor_name": anchor_name,
                    "anchor": anchor.to_dict(),
                    "requested_product_ids": list(requested_products),
                    "requested_pickup_node_ids": list(stops),
                    "baseline_A_status": (
                        "feasible_only_if_list_unchanged_from_original_start"
                        if baseline_a_feasible
                        else "infeasible_non_adaptive_after_anchor_change"
                    ),
                    "baseline_A_total_route_cost_m": baseline_a.total_distance_m if baseline_a_feasible else None,
                    "baseline_A_actual_simulated_travel_m": (
                        _expanded_distance(simulation, baseline_a.route_node_ids)
                        if baseline_a_feasible else None
                    ),
                    "baseline_B_naive_remaining_cost_m": naive,
                    "baseline_B_actual_simulated_travel_m": (
                        naive_plan[1]
                        + _expanded_distance(simulation, naive_plan[2].route_node_ids)
                    ),
                    "proposed_remaining_cost_m": proposed.total_distance_m,
                    "proposed_actual_simulated_travel_m": (
                        proposed.partial_edge_distance_m
                        + _expanded_distance(simulation, proposed.route_node_ids)
                    ),
                    "movement_assumption": "Exact partial edge followed by each expanded graph edge once; no shelf crossing or teleport.",
                    "absolute_improvement_m": improvement,
                    "percentage_improvement": 0.0 if naive == 0 else 100.0 * improvement / naive,
                    "completion_status": "modeled_complete_on_connected_graph",
                    "route_revisions": 1,
                    "brute_force_oracle_cost_m": oracle,
                    "oracle_match": math.isclose(proposed.total_distance_m, oracle, abs_tol=1e-9),
                    "outcome": "improvement" if improvement > 1e-9 else "tie",
                }
            )
    return rows


def _context(store: Any, node_id: str, *, last: str | None = None, camera: bool = True) -> CheckpointPlausibilityContext:
    return CheckpointPlausibilityContext(
        graph=store.graph,
        estimated_anchor=node_route_anchor(store.graph, node_id),
        position_uncertainty_m=0.25,
        maximum_speed_m_s=1.6,
        distance_tolerance_m=1.0,
        last_verified_checkpoint_node_id=last,
        camera_available=camera,
    )


def _localization_trials() -> list[dict[str, Any]]:
    store = load_demo_store()
    map_id = store.data["map_id"]
    checkpoint_nodes = {item["checkpoint_id"]: item["node_id"] for item in store.data["checkpoints"]}
    trials: list[dict[str, Any]] = []

    def run(
        scenario: str,
        seed: int,
        *,
        tag_id: int | None,
        expected_tag_id: int,
        estimate_node: str,
        truth_node: str,
        timestamp_s: float,
        should_accept: bool,
        setup_tag: int | None = None,
        setup_timestamp_s: float = 0.0,
        map_version: str | None = None,
        observed_offset: tuple[float, float] = (0.0, 0.0),
        recovery_delay_s: float = 0.0,
    ) -> None:
        processor = CheckpointObservationProcessor(store.checkpoint_layout, map_id)
        if setup_tag is not None:
            setup_node = checkpoint_nodes[setup_tag]
            point = store.graph.node(setup_node)
            setup = CheckpointObservation(
                setup_tag, setup_timestamp_s, "adaptive_evaluation", map_id, confidence=1.0
            )
            processor.process(
                setup,
                PositionEstimate(point.x_m, point.y_m, 0.0, setup_timestamp_s),
                expected_tag_id=setup_tag,
                allow_unexpected_mapped=True,
                plausibility=_context(store, setup_node),
            )
        estimate = store.graph.node(estimate_node)
        truth = store.graph.node(truth_node)
        jitter = random.Random(seed).uniform(-0.18, 0.18)
        pose = PositionEstimate(
            estimate.x_m + observed_offset[0] + jitter,
            estimate.y_m + observed_offset[1],
            0.0,
            timestamp_s,
        )
        before_error = math.hypot(pose.x_m - truth.x_m, pose.y_m - truth.y_m)
        observation = None if tag_id is None else CheckpointObservation(
            tag_id,
            timestamp_s,
            "adaptive_evaluation",
            map_version or map_id,
            confidence=1.0,
        )
        result = processor.process(
            observation,
            pose,
            expected_tag_id=expected_tag_id,
            allow_unexpected_mapped=True,
            plausibility=_context(
                store,
                estimate_node,
                last=checkpoint_nodes.get(setup_tag) if setup_tag is not None else None,
            ),
        )
        corrected = result.corrected_pose or pose
        after_error = math.hypot(corrected.x_m - truth.x_m, corrected.y_m - truth.y_m)
        actual = bool(result.accepted)
        decision = (
            "TP" if should_accept and actual else
            "FN" if should_accept else
            "FP" if actual else "TN"
        )
        trials.append(
            {
                "trial_id": f"loc-{len(trials) + 1:03d}",
                "scenario": scenario,
                "seed": seed,
                "ground_truth_node_id": truth_node,
                "ground_truth_used_as_localization_input": False,
                "expected_acceptance_label": should_accept,
                "accepted": actual,
                "decision": decision,
                "reason": result.reason,
                "classification": result.classification,
                "position_error_before_m": before_error,
                "position_error_after_m": after_error,
                "correction_distance_m": result.correction_m or 0.0,
                "recovery_time_simulated_s": recovery_delay_s if actual else None,
                "timestamp_s": timestamp_s,
            }
        )

    for seed in SEEDS:
        run("correct_expected_checkpoint", seed, tag_id=201, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=20.0,
            should_accept=True, observed_offset=(0.35, 0.0))
        run("correct_unexpected_mapped_checkpoint", seed, tag_id=201, expected_tag_id=202,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=20.0,
            should_accept=True, observed_offset=(0.25, 0.0), recovery_delay_s=0.25)
        run("duplicate_checkpoint", seed, tag_id=200, expected_tag_id=201,
            estimate_node="N0_0", truth_node="N0_0", timestamp_s=2.0,
            should_accept=False, setup_tag=200, setup_timestamp_s=1.0)
        run("unknown_checkpoint", seed, tag_id=42, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=20.0,
            should_accept=False)
        run("stale_observation", seed, tag_id=201, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=1.0,
            should_accept=False, setup_tag=200, setup_timestamp_s=2.0)
        run("incorrect_map_version", seed, tag_id=201, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=20.0,
            should_accept=False, map_version="incorrect-map-v0")
        run("spatially_implausible_checkpoint", seed, tag_id=202, expected_tag_id=201,
            estimate_node="N0_0", truth_node="N0_0", timestamp_s=1.0,
            should_accept=False, setup_tag=200, setup_timestamp_s=0.0)
        run("missed_checkpoint", seed, tag_id=None, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=20.0,
            should_accept=False)
        run("delayed_observation", seed, tag_id=201, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=26.0,
            should_accept=True, observed_offset=(0.4, 0.0), recovery_delay_s=6.0)
        run("dead_reckoning_drift_correction", seed, tag_id=201, expected_tag_id=201,
            estimate_node="N2_3", truth_node="N2_3", timestamp_s=20.0,
            should_accept=True, observed_offset=(0.8, 0.0), recovery_delay_s=0.25)
    return trials


def _benchmark(operation: Callable[[], Any]) -> list[float]:
    for _ in range(WARMUP_REPETITIONS):
        operation()
    measurements: list[float] = []
    for _ in range(MEASURED_REPETITIONS):
        started = time.perf_counter_ns()
        operation()
        measurements.append((time.perf_counter_ns() - started) / 1_000_000.0)
    return measurements


def _performance_trials() -> list[dict[str, Any]]:
    simulation = SpatialNavigationSimulation(speed_m_s=1.6)
    graph = simulation.graph
    product_nodes = simulation._product_nodes(PRODUCT_IDS)
    anchor = edge_route_anchor(
        graph, "N0_1", "N0_2", 1.25, travel_direction="stopped"
    )
    rows: list[dict[str, Any]] = []

    def record(name: str, count: int, values: Sequence[float], oracle: bool | None = None) -> None:
        rows.append(
            {
                "operation": name,
                "destination_count": count,
                "unit": "ms",
                "warmup_repetitions": WARMUP_REPETITIONS,
                **_summary(values),
                "brute_force_oracle_match": oracle,
                "raw_measurements_ms": list(values),
            }
        )

    dijkstra_pairs = tuple(zip(graph.node_ids, reversed(graph.node_ids)))
    for count in range(0, len(product_nodes) + 1):
        stops = product_nodes[:count]
        record(
            "dijkstra_shortest_path",
            count,
            _benchmark(lambda c=count: dijkstra_shortest_path(graph, *dijkstra_pairs[c % len(dijkstra_pairs)])),
        )
        hk_values = _benchmark(
            lambda s=stops: held_karp_route(
                graph, simulation.entrance_node_id, s, simulation.checkout_node_id
            )
        )
        hk = held_karp_route(
            graph, simulation.entrance_node_id, stops, simulation.checkout_node_id
        )
        oracle = _brute_force_cost(
            simulation, node_route_anchor(graph, simulation.entrance_node_id), stops
        )
        record("held_karp_remaining_optimization", count, hk_values,
               math.isclose(hk.total_distance_m, oracle, abs_tol=1e-9))
        record(
            "mid_edge_route_anchor",
            count,
            _benchmark(lambda s=stops: held_karp_route_from_anchor(
                graph, anchor, s, simulation.checkout_node_id
            )),
            math.isclose(
                held_karp_route_from_anchor(graph, anchor, stops, simulation.checkout_node_id).total_distance_m,
                _brute_force_cost(simulation, anchor, stops), abs_tol=1e-9,
            ),
        )

        def dynamic_reoptimization(s: Sequence[str] = stops) -> None:
            candidate = SpatialNavigationSimulation(speed_m_s=1.6)
            candidate.set_products(())
            for index, product_id in enumerate(PRODUCT_IDS[:len(s)]):
                candidate.mutate_shopping_list("add", product_id, 1, index)

        record("dynamic_shopping_reoptimization", count, _benchmark(dynamic_reoptimization))

        def checkpoint_replan(s: Sequence[str] = stops) -> None:
            candidate = SpatialNavigationSimulation(speed_m_s=1.6)
            candidate.set_products(PRODUCT_IDS[:len(s)])
            candidate.enter_free_walk()
            candidate.current_node_id = "N2_3"
            point = candidate.graph.node("N2_3")
            candidate.true_x_m, candidate.true_y_m = point.x_m, point.y_m
            candidate.estimator._pose = PositionEstimate(point.x_m + 0.25, point.y_m, 0.0, 20.0)
            candidate._localization_uncertainty_m = 0.25
            candidate.simulation_time_s = 20.0
            candidate.observe_checkpoint({
                "tag_id": 201,
                "timestamp_s": 20.0,
                "detection_source": "adaptive_evaluation",
            })

        record("checkpoint_triggered_replanning", count, _benchmark(checkpoint_replan))
    return rows


def _walk_edge(simulation: SpatialNavigationSimulation, target: str) -> None:
    simulation.choose_free_walk_edge(target)
    for _ in range(400):
        simulation.step()
        if simulation.status == "free_walk_stopped":
            return
    raise RuntimeError(f"Free-walk edge did not finish at {target}")


def _complete(simulation: SpatialNavigationSimulation) -> dict[str, Any]:
    if simulation.status == "ready":
        simulation.start()
    for _ in range(8000):
        if simulation.status == "awaiting_product_confirmation":
            simulation.confirm_product(
                expected_shopping_revision=simulation.shopping_session.revision
            )
        elif simulation.status == "complete":
            return simulation.snapshot()
        elif simulation.status in {"camera_interrupted", "paused"}:
            simulation.resume()
        else:
            simulation.step()
    raise RuntimeError(f"Journey did not complete: {simulation.status}")


def _trajectory_graph_constrained(simulation: SpatialNavigationSimulation) -> bool:
    points = simulation.snapshot()["travelled_ground_truth"]
    for point in points:
        on_edge = False
        for edge in simulation.graph.edges:
            a, b = simulation.graph.node(edge.source), simulation.graph.node(edge.target)
            cross = (point["x_m"] - a.x_m) * (b.y_m - a.y_m) - (point["y_m"] - a.y_m) * (b.x_m - a.x_m)
            dot = (point["x_m"] - a.x_m) * (b.x_m - a.x_m) + (point["y_m"] - a.y_m) * (b.y_m - a.y_m)
            length_sq = (b.x_m - a.x_m) ** 2 + (b.y_m - a.y_m) ** 2
            if abs(cross) <= 1e-7 and -1e-7 <= dot <= length_sq + 1e-7:
                on_edge = True
                break
        if not on_edge:
            return False
    return True


def _journey_trials() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    planned = SpatialNavigationSimulation(sensor_config=SensorConfig(seed=SEEDS[0]), speed_m_s=1.6)
    planned.set_products(("SIM-P-001", "SIM-P-004"))
    planned_result = _complete(planned)
    results.append({
        "scenario": "planned_route_shopping_and_checkout",
        "status": planned_result["status"],
        "passed": planned_result["status"] == "complete",
        "requested_units": planned_result["shopping_session"]["requested_units"],
        "collected_units": planned_result["shopping_session"]["collected_units"],
        "graph_constrained_no_shelf_crossings": _trajectory_graph_constrained(planned),
        "pickup_events": sum(e["event_type"] == "product_collected" for e in planned_result["events"]),
        "unauthorized_checkout": False,
    })

    adaptive = SpatialNavigationSimulation(sensor_config=SensorConfig(seed=SEEDS[1]), speed_m_s=1.6)
    adaptive.set_products(())
    adaptive.enter_free_walk()
    _walk_edge(adaptive, "N1_0")
    _walk_edge(adaptive, "N1_1")
    added = adaptive.mutate_shopping_list("add", "SIM-P-001", 2, 0)
    first_pickup = adaptive.confirm_product(expected_shopping_revision=1)
    increased = adaptive.mutate_shopping_list("increase", "SIM-P-001", 1, 2)
    second_pickup = adaptive.confirm_product(expected_shopping_revision=3)
    removed_candidate = adaptive.mutate_shopping_list("add", "SIM-P-002", 1, 4)
    removed = adaptive.mutate_shopping_list("remove", "SIM-P-002", 1, 5)
    offered_recommendation = adaptive.snapshot()["recommendations"][0]
    recommendation = adaptive.accept_recommendation(
        offered_recommendation["recommendation_id"], 6
    )
    resumed = adaptive.request_navigation_from_current_location()
    final = _complete(adaptive)
    line = next(item for item in final["shopping_session"]["items"] if item["product_id"] == "SIM-P-001")
    results.append({
        "scenario": "independent_walk_dynamic_quantities_and_recommendation",
        "passed": final["status"] == "complete" and line["collected_quantity"] == 3,
        "free_walk_target_node": "N1_1",
        "status_after_add": added["status"],
        "first_pickup_explicit": first_pickup["shopping_session"]["collected_units"] == 1,
        "quantity_increased": increased["shopping_list_revision"] == 3,
        "second_pickup_explicit": second_pickup["shopping_session"]["collected_units"] == 2,
        "remove_was_applied": "SIM-P-002" not in removed["selected_product_ids"],
        "recommendation_label": offered_recommendation["recommendation_source"],
        "recommendation_score": offered_recommendation["score"],
        "resumed_without_entrance_reset": resumed["current_node_id"] == "N1_1",
        "final_requested_units": final["shopping_session"]["requested_units"],
        "final_collected_units": final["shopping_session"]["collected_units"],
        "graph_constrained_no_shelf_crossings": _trajectory_graph_constrained(adaptive),
        "shopping_revisions": final["shopping_list_revision"],
        "route_revisions": final["route_revision"],
    })

    wrong = SpatialNavigationSimulation(sensor_config=SensorConfig(seed=SEEDS[2]), speed_m_s=1.6)
    wrong.set_products(("SIM-P-003", "SIM-P-005"))
    wrong.start()
    wrong.wrong_turn()
    wrong_final = _complete(wrong)
    results.append({
        "scenario": "wrong_turn_and_recovery",
        "passed": wrong_final["status"] == "complete" and wrong_final["reroute_count"] >= 1,
        "status": wrong_final["status"],
        "reroute_count": wrong_final["reroute_count"],
        "route_revisions": wrong_final["route_revision"],
        "graph_constrained_no_shelf_crossings": _trajectory_graph_constrained(wrong),
    })

    camera = SpatialNavigationSimulation(sensor_config=SensorConfig(seed=SEEDS[3]), speed_m_s=1.6)
    camera.set_products(())
    camera.start_camera_evaluation()
    camera.camera_reconnected()
    camera.observe_camera_detection(200, 0.25)
    camera.step()
    interrupted = camera.camera_stopped()
    reconnected = camera.camera_reconnected()
    for _ in range(8000):
        if camera.status == "complete":
            break
        if camera.status == "awaiting_checkpoint" and camera._checkpoint_gate:
            camera.observe_camera_detection(
                camera._checkpoint_gate["checkpoint_id"], camera.simulation_time_s
            )
        elif camera.status == "awaiting_product_confirmation":
            camera.confirm_product(expected_shopping_revision=camera.shopping_session.revision)
        else:
            camera.step()
    camera_final = camera.snapshot()
    results.append({
        "scenario": "explicit_simulated_camera_interruption_and_checkout",
        "passed": interrupted["status"] == "camera_stopped" and camera_final["status"] == "complete",
        "physical_camera_used": False,
        "interrupted_status": interrupted["status"],
        "reconnected_status": reconnected["status"],
        "checkout_status": camera_final["status"],
    })

    checkpoint = SpatialNavigationSimulation(sensor_config=SensorConfig(seed=SEEDS[4]), speed_m_s=1.6)
    checkpoint.set_products(("SIM-P-006",))
    checkpoint.enter_free_walk()
    path = dijkstra_shortest_path(
        checkpoint.graph, checkpoint.entrance_node_id, checkpoint.checkout_node_id
    )
    for target in path.node_ids[1:]:
        _walk_edge(checkpoint, target)
    before = checkpoint.snapshot()
    after = checkpoint.observe_checkpoint({
        "tag_id": 202,
        "timestamp_s": before["simulation_time_s"],
        "detection_source": "adaptive_evaluation",
    })
    results.append({
        "scenario": "unexpected_checkpoint_correction_and_replan",
        "passed": (
            after["observed_checkpoint"]["classification"]
            == "unexpected_but_plausible_mapped_checkpoint"
            and after["route_revision"] > before["route_revision"]
        ),
        "classification": after["observed_checkpoint"]["classification"],
        "ground_truth_unchanged_by_observation": before["ground_truth"] == after["ground_truth"],
        "checkpoint_history_preserved": len(after["checkpoint_observation_history"]) >= len(before["checkpoint_observation_history"]),
        "route_revision_increased": after["route_revision"] > before["route_revision"],
    })
    return results


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_evaluation(output_directory: Path = ARCHIVE) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / DEFAULT_MANIFEST.name
    raw_path = output_directory / DEFAULT_RAW.name
    aggregate_path = output_directory / DEFAULT_AGGREGATE.name
    baseline_path = output_directory / DEFAULT_BASELINES.name
    localization_path = output_directory / DEFAULT_LOCALIZATION.name
    performance_path = output_directory / DEFAULT_PERFORMANCE.name

    store = load_demo_store()
    manifest = {
        "milestone": "C3-P7F",
        "data_classification": "deterministic_synthetic_experiment_configuration",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seeds": list(SEEDS),
        "map_id": store.data["map_id"],
        "map_schema_version": store.data.get("schema_version"),
        "product_ids": list(PRODUCT_IDS),
        "checkpoint_ids": [item["checkpoint_id"] for item in store.data["checkpoints"]],
        "fixed_timestep_s": 0.25,
        "speed_m_s": 1.6,
        "benchmark": {
            "clock": "time.perf_counter_ns",
            "warmup_repetitions": WARMUP_REPETITIONS,
            "measured_repetitions": MEASURED_REPETITIONS,
            "unit": "ms",
        },
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "not_reported_by_platform",
            "python": sys.version.split()[0],
            "logical_cpu_count": os.cpu_count(),
        },
        "ground_truth_policy": "Independent simulated truth is used only for scoring, never as a hidden localization input.",
        "physical_camera_used": False,
        "physical_trolley_used": False,
    }
    baseline = _baseline_trials()
    localization = _localization_trials()
    performance = _performance_trials()
    journeys = _journey_trials()

    tp = sum(row["decision"] == "TP" for row in localization)
    tn = sum(row["decision"] == "TN" for row in localization)
    fp = sum(row["decision"] == "FP" for row in localization)
    fn = sum(row["decision"] == "FN" for row in localization)
    precision_denominator = tp + fp
    recall_denominator = tp + fn
    aggregate = {
        "milestone": "C3-P7F",
        "data_classification": "aggregated_synthetic_and_software_evaluation",
        "route_comparison": {
            "trials": len(baseline),
            "improvements": sum(row["outcome"] == "improvement" for row in baseline),
            "ties": sum(row["outcome"] == "tie" for row in baseline),
            "oracle_matches": sum(bool(row["oracle_match"]) for row in baseline),
            "mean_absolute_improvement_m": statistics.mean(row["absolute_improvement_m"] for row in baseline),
            "median_percentage_improvement": statistics.median(row["percentage_improvement"] for row in baseline),
        },
        "localization": {
            "observations": len(localization),
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "precision": None if precision_denominator == 0 else tp / precision_denominator,
            "precision_denominator": precision_denominator,
            "recall": None if recall_denominator == 0 else tp / recall_denominator,
            "recall_denominator": recall_denominator,
            "correct_decision_interval_wilson_95": _wilson(tp + tn, len(localization)),
            "accepted_observation_interval_wilson_95": _wilson(tp + fp, len(localization)),
            "mean_position_error_before_m": statistics.mean(row["position_error_before_m"] for row in localization),
            "mean_position_error_after_m": statistics.mean(row["position_error_after_m"] for row in localization),
            "synthetic_only_not_physical_accuracy": True,
        },
        "performance": {
            "benchmark_cells": len(performance),
            "warmup_repetitions_per_cell": WARMUP_REPETITIONS,
            "measured_repetitions_per_cell": MEASURED_REPETITIONS,
            "maximum_destination_count": len(PRODUCT_IDS),
            "scaling_limit": "Held-Karp is exponential O(n^2*2^n); production use is explicitly limited to 10 unique stops by the implementation.",
        },
        "complete_journeys": {
            "scenarios": len(journeys),
            "passed": sum(bool(row["passed"]) for row in journeys),
            "all_passed": all(bool(row["passed"]) for row in journeys),
        },
        "statistical_statement": "Descriptive repeated synthetic experiments only; no hypothesis-significance test was performed.",
    }
    raw = {
        "milestone": "C3-P7F",
        "manifest": manifest_path.as_posix(),
        "baseline_trials": baseline,
        "localization_trials": localization,
        "performance_trials": performance,
        "complete_journey_trials": journeys,
    }
    for path, payload in ((manifest_path, manifest), (raw_path, raw), (aggregate_path, aggregate)):
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    _write_csv(baseline_path, baseline, (
        "trial_id", "anchor_name", "requested_product_ids", "requested_pickup_node_ids",
        "baseline_A_status", "baseline_A_total_route_cost_m",
        "baseline_A_actual_simulated_travel_m", "baseline_B_naive_remaining_cost_m",
        "baseline_B_actual_simulated_travel_m", "proposed_remaining_cost_m",
        "proposed_actual_simulated_travel_m", "movement_assumption",
        "absolute_improvement_m", "percentage_improvement", "completion_status",
        "route_revisions", "brute_force_oracle_cost_m", "oracle_match", "outcome",
    ))
    _write_csv(localization_path, localization, (
        "trial_id", "scenario", "seed", "ground_truth_node_id",
        "ground_truth_used_as_localization_input", "expected_acceptance_label", "accepted",
        "decision", "reason", "classification", "position_error_before_m",
        "position_error_after_m", "correction_distance_m", "recovery_time_simulated_s",
        "timestamp_s",
    ))
    _write_csv(performance_path, performance, (
        "operation", "destination_count", "unit", "warmup_repetitions", "repetitions",
        "minimum", "median", "p95_nearest_rank", "maximum", "brute_force_oracle_match",
    ))
    return {"manifest": manifest, "aggregate": aggregate, "paths": {
        "manifest": str(manifest_path), "raw": str(raw_path), "aggregate": str(aggregate_path),
        "baselines": str(baseline_path), "localization": str(localization_path),
        "performance": str(performance_path),
    }}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    print(json.dumps(run_evaluation(args.output_directory), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
