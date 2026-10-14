"""Run deterministic navigation-simulation scenarios and export measured results."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from component3.backend.comp3_reco_navigation.navigation.dead_reckoning import (
    PositionEstimate,
)
from component3.backend.comp3_reco_navigation.navigation.deviation import (
    RouteDeviationMonitor,
)

from .engine import FIXED_TIMESTEP_S, NavigationSimulation
from .sensors import SensorConfig


DEFAULT_OUTPUT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "navigation_simulation"
)


def _run_to_completion(simulation: NavigationSimulation, *, guided: bool) -> None:
    """Advance one simulation deterministically, confirming only stopped visits."""
    if guided:
        simulation.guided_start()
    else:
        simulation.start()
    for _ in range(20000):
        if simulation.status == "complete":
            return
        if simulation.status == "awaiting_stop_confirmation":
            simulation.confirm_current_stop()
            simulation.resume()
            continue
        if simulation.status in {"paused", "ready"}:
            simulation.resume() if simulation.status == "paused" else simulation.start()
            continue
        simulation.step()
    raise RuntimeError("Simulation did not complete within the deterministic step limit")


def _scenario_report(
    simulation: NavigationSimulation,
) -> dict[str, Any]:
    """Return a compact report computed from one simulation's output."""
    event_types = [event.event_type for event in simulation.events]
    return {
        **simulation.metrics(),
        "status": simulation.status,
        "seed": simulation.sensor_config.seed,
        "events": {
            name: event_types.count(name)
            for name in sorted(set(event_types))
        },
        "planned_route": list(simulation.route_manager.current_planned_route),
    }


def run_evaluation() -> dict[str, Any]:
    """Execute requested navigation, sensor, deviation, reroute, and replay cases."""
    normal = NavigationSimulation(
        sensor_config=SensorConfig(
            encoder_noise_std_m=0.0,
            encoder_bias_fraction=0.0,
            imu_yaw_noise_std_rad=0.0,
            imu_yaw_bias_rad_per_sample=0.0,
        )
    )
    _run_to_completion(normal, guided=False)

    noisy = NavigationSimulation(
        sensor_config=SensorConfig(
            seed=6042,
            encoder_noise_std_m=0.012,
            encoder_bias_fraction=0.012,
            imu_yaw_noise_std_rad=math.radians(0.8),
            imu_yaw_bias_rad_per_sample=math.radians(0.12),
        )
    )
    _run_to_completion(noisy, guided=False)

    guided = NavigationSimulation()
    _run_to_completion(guided, guided=True)

    failed = NavigationSimulation(max_snapping_distance_m=0.001)
    failed_original_route = tuple(failed.route_manager.current_planned_route)
    failed.guided_start()
    for _ in range(300):
        if any(event.event_type == "reroute_failed" for event in failed.events):
            break
        failed.step()

    brief = NavigationSimulation(
        sensor_config=SensorConfig(
            encoder_noise_std_m=0.0,
            encoder_bias_fraction=0.0,
            imu_yaw_noise_std_rad=0.0,
            imu_yaw_bias_rad_per_sample=0.0,
        )
    )
    monitor = RouteDeviationMonitor(
        brief.graph, brief.route_manager.current_planned_route, enter_confirmations=3
    )
    start = brief.graph.node("ENT")
    brief_states = [
        monitor.update(PositionEstimate(start.x_m + 0.5, 1.0, 0.0, 0.25)),
        monitor.update(PositionEstimate(start.x_m + 0.5, 1.0, 0.0, 0.50)),
        monitor.update(PositionEstimate(start.x_m, 1.0, 0.0, 0.75)),
    ]
    brief_report = {
        "instantaneous_deviation_samples": sum(
            state.measurement.is_deviating for state in brief_states
        ),
        "confirmed_deviation": any(state.entered_deviation for state in brief_states),
        "returned_to_route": not brief_states[-1].is_deviated,
        "reroute_count": 0,
    }

    replay = NavigationSimulation()
    _run_to_completion(replay, guided=True)
    deterministic = (
        replay.metrics() == guided.metrics()
        and replay.snapshot()["events"] == guided.snapshot()["events"]
        and replay.snapshot()["trajectory_ground_truth"]
        == guided.snapshot()["trajectory_ground_truth"]
        and replay.snapshot()["trajectory_estimated"]
        == guided.snapshot()["trajectory_estimated"]
    )
    controls = NavigationSimulation()
    controls.start()
    controls.pause()
    paused_at_s = controls.simulation_time_s
    controls.resume()
    controls.step()
    stepped_at_s = controls.simulation_time_s
    controls.reset()
    controls_report = {
        "paused_without_advancing": paused_at_s == 0.0,
        "resumed_and_advanced_one_fixed_step": (
            stepped_at_s == FIXED_TIMESTEP_S
        ),
        "reset_restored_ready_state": (
            controls.status == "ready" and controls.simulation_time_s == 0.0
        ),
    }
    failed_report = _scenario_report(failed)
    failed_report["atomic_failure_preserved_route"] = (
        tuple(failed.route_manager.current_planned_route) == failed_original_route
    )
    return {
        "schema_version": "1.0",
        "description": (
            "Measured software-in-the-loop results using the existing Component 3 "
            "store graph and navigation algorithms; all sensor and tag events are simulated."
        ),
        "fixed_timestep_s": guided.snapshot()["fixed_timestep_s"],
        "scenarios": {
            "normal_navigation": _scenario_report(normal),
            "noisy_navigation": _scenario_report(noisy),
            "brief_deviation": brief_report,
            "checkpoint_correction": {
                "correction_count": guided.metrics()["checkpoint_corrections"],
                "first_correction": next(
                    (
                        event.details
                        for event in guided.events
                        if event.event_type == "checkpoint_correction"
                    ),
                    None,
                ),
            },
            "confirmed_deviation_and_successful_reroute": _scenario_report(guided),
            "failed_rerouting": failed_report,
            "duplicate_reroute_suppression": {
                "confirmed_reroute_count": guided.metrics()["reroute_count"],
                "single_deviation_episode": guided.metrics()["reroute_count"] == 1,
            },
            "shopping_stop_confirmation": {
                "visited_destinations": guided.metrics()["visited_destinations"],
                "remaining_destinations": guided.metrics()["remaining_destinations"],
            },
            "checkout_completion": {
                "completed": guided.metrics()["completed"],
                "checkout_node_id": guided.checkout_node_id,
                "simulation_time_s": guided.simulation_time_s,
            },
            "pause_resume_reset": controls_report,
            "deterministic_replay": {"identical": deterministic},
        },
        "guided_demo": guided.snapshot(),
        "failed_reroute_demo": failed.snapshot(),
    }


def write_evaluation(output_root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    """Write genuine JSON metrics and guided-demo CSV sensor/event logs."""
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "navigation_simulation_results.json"
    csv_path = output_root / "guided_demo_telemetry.csv"
    json_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    guided = report["guided_demo"]
    csv_path.write_text(_csv_for_snapshot(guided), encoding="utf-8")
    return json_path, csv_path


def _csv_for_snapshot(snapshot: dict[str, Any]) -> str:
    """Serialize aligned truth/estimate rows plus chronological event records."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "record_type",
            "simulation_time_s",
            "x_true_m",
            "y_true_m",
            "x_estimated_m",
            "y_estimated_m",
            "position_error_m",
            "event_type",
            "event_message",
        ]
    )
    estimates = {
        sample["timestamp_s"]: sample
        for sample in snapshot["trajectory_estimated"]
    }
    for truth in snapshot["trajectory_ground_truth"]:
        estimate = estimates[truth["timestamp_s"]]
        writer.writerow(
            [
                "sample",
                truth["timestamp_s"],
                truth["x_m"],
                truth["y_m"],
                estimate["x_m"],
                estimate["y_m"],
                estimate["error_m"],
                "",
                "",
            ]
        )
    for event in snapshot["events"]:
        writer.writerow(
            [
                "event",
                event["timestamp_s"],
                "",
                "",
                "",
                "",
                "",
                event["event_type"],
                event["message"],
            ]
        )
    return output.getvalue()


def main() -> None:
    """Run evaluation cases and write requested reproducible output files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    arguments = parser.parse_args()
    report = run_evaluation()
    json_path, csv_path = write_evaluation(arguments.output, report)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path)}, indent=2))
    for name, result in report["scenarios"].items():
        print(f"{name}: {json.dumps(result, sort_keys=True)}")


if __name__ == "__main__":
    main()
