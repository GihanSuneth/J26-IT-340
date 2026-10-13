"""Reproducible sensor-only position-tracking simulation over the store graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import math
from pathlib import Path
import random
from typing import Iterable, Sequence
import xml.sax.saxutils as xml_utils

import cv2
import numpy as np

from .apriltag import (
    AprilTagLayout,
    DEFAULT_APRILTAG_LAYOUT_PATH,
)
from .dead_reckoning import (
    DeadReckoner,
    MotionMeasurement,
    PositionEstimate,
    SimulatedCheckpointObservation,
    correct_to_checkpoint,
    normalize_heading,
)
from .held_karp import held_karp_route
from .store_graph import DEFAULT_STORE_GRAPH_PATH, StoreGraph, load_store_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "component3/evaluation/position_tracking"
DEFAULT_EVIDENCE_ROOT = (
    REPOSITORY_ROOT
    / "component3/docs/research_evidence/05_position_tracking/screenshots"
)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Explicit simulation assumptions; these are not hardware calibrations."""

    seed: int = 3404
    sample_interval_s: float = 0.25
    nominal_speed_m_s: float = 0.8
    turn_duration_s: float = 0.5
    stationary_samples_per_node: int = 1
    encoder_noise_std_m: float = 0.003
    encoder_bias_fraction: float = 0.002
    imu_yaw_noise_std_rad: float = math.radians(0.25)
    imu_yaw_bias_rad_s: float = math.radians(0.15)
    start_node_id: str = "ENT"
    checkout_node_id: str = "CHK"
    shopping_stop_ids: tuple[str, ...] = ("B1", "B3", "B5")

    def __post_init__(self) -> None:
        positive = (
            self.sample_interval_s,
            self.nominal_speed_m_s,
            self.turn_duration_s,
        )
        nonnegative = (
            self.encoder_noise_std_m,
            self.encoder_bias_fraction,
            self.imu_yaw_noise_std_rad,
            self.imu_yaw_bias_rad_s,
        )
        if any(not math.isfinite(value) or value <= 0 for value in positive):
            raise ValueError("sampling interval, speed, and turn duration must be positive")
        if any(not math.isfinite(value) or value < 0 for value in nonnegative):
            raise ValueError("noise and bias assumptions must be finite and nonnegative")
        if self.stationary_samples_per_node < 1:
            raise ValueError("stationary_samples_per_node must be at least one")


@dataclass(frozen=True, slots=True)
class GroundTruthPoint:
    """Simulation-only ground-truth pose; never passed to the estimator."""

    timestamp_s: float
    x_m: float
    y_m: float
    heading_rad: float


@dataclass(frozen=True, slots=True)
class CheckpointEvent:
    """A simulated known-tag observation at a graph-node arrival."""

    sample_index: int
    observation: SimulatedCheckpointObservation


@dataclass(frozen=True, slots=True)
class SimulationTrace:
    """One ground-truth path and aligned ideal/noisy sensor-only sequences."""

    route_node_ids: tuple[str, ...]
    initial_estimate: PositionEstimate
    ground_truth: tuple[GroundTruthPoint, ...]
    ideal_measurements: tuple[MotionMeasurement, ...]
    noisy_measurements: tuple[MotionMeasurement, ...]
    checkpoint_events: tuple[CheckpointEvent, ...]


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Per-sample estimator output and the independently measured errors."""

    name: str
    estimates: tuple[PositionEstimate, ...]
    errors_m: tuple[float, ...]
    checkpoint_errors: tuple[tuple[int, float, float], ...]


@dataclass(frozen=True, slots=True)
class ScenarioMetrics:
    """Aggregate position errors and checkpoint correction effects."""

    scenario: str
    measurement_mode: str
    checkpoint_corrections: int
    mean_position_error_m: float
    rmse_position_error_m: float
    max_position_error_m: float
    final_position_error_m: float
    mean_error_before_checkpoint_m: float
    mean_error_after_checkpoint_m: float


def _load_layout(path: Path, graph: StoreGraph) -> AprilTagLayout:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return AprilTagLayout.from_dict(data, graph)


def _measurement(
    timestamp_s: float,
    distance_m: float,
    yaw_delta_rad: float,
) -> MotionMeasurement:
    return MotionMeasurement(timestamp_s, distance_m, yaw_delta_rad)


def build_simulation_trace(
    graph: StoreGraph,
    layout: AprilTagLayout,
    config: SimulationConfig,
) -> SimulationTrace:
    """Build identical ground truth and seeded ideal/noisy measurement streams."""
    route = held_karp_route(
        graph,
        config.start_node_id,
        config.shopping_stop_ids,
        config.checkout_node_id,
    ).route_node_ids
    rng = random.Random(config.seed)
    start_node = graph.node(config.start_node_id)
    initial_estimate = PositionEstimate(
        start_node.x_m,
        start_node.y_m,
        0.0,
        0.0,
    )
    ground_truth = [
        GroundTruthPoint(
            timestamp_s=0.0,
            x_m=start_node.x_m,
            y_m=start_node.y_m,
            heading_rad=initial_estimate.heading_rad,
        )
    ]
    ideal_measurements: list[MotionMeasurement] = []
    noisy_measurements: list[MotionMeasurement] = []
    checkpoint_events: list[CheckpointEvent] = []
    tag_for_node = {
        checkpoint.node_id: tag_id for tag_id, checkpoint in layout.checkpoints.items()
    }
    timestamp_s = 0.0
    heading_rad = 0.0
    x_m = ground_truth[0].x_m
    y_m = ground_truth[0].y_m

    def append_sample(distance_m: float, yaw_delta_rad: float) -> None:
        nonlocal timestamp_s, heading_rad, x_m, y_m
        timestamp_s += config.sample_interval_s
        midpoint = normalize_heading(heading_rad + yaw_delta_rad / 2.0)
        x_m += distance_m * math.cos(midpoint)
        y_m += distance_m * math.sin(midpoint)
        heading_rad = normalize_heading(heading_rad + yaw_delta_rad)
        ground_truth.append(
            GroundTruthPoint(timestamp_s, x_m, y_m, heading_rad)
        )
        ideal_measurements.append(
            _measurement(timestamp_s, distance_m, yaw_delta_rad)
        )
        noisy_distance = (
            distance_m
            + config.encoder_bias_fraction * distance_m
            + rng.gauss(0.0, config.encoder_noise_std_m)
        )
        noisy_yaw = (
            yaw_delta_rad
            + config.imu_yaw_bias_rad_s * config.sample_interval_s
            + rng.gauss(0.0, config.imu_yaw_noise_std_rad)
        )
        noisy_measurements.append(
            _measurement(timestamp_s, noisy_distance, noisy_yaw)
        )

    for source_id, target_id in zip(route, route[1:]):
        source = graph.node(source_id)
        target = graph.node(target_id)
        dx = target.x_m - source.x_m
        dy = target.y_m - source.y_m
        segment_length_m = math.hypot(dx, dy)
        if segment_length_m <= 0.0:
            raise ValueError(f"Route contains a zero-length coordinate edge: {source_id}")
        target_heading = math.atan2(dy, dx)
        turn_delta = normalize_heading(target_heading - heading_rad)
        turn_steps = max(
            1,
            math.ceil(config.turn_duration_s / config.sample_interval_s),
        )
        for _ in range(turn_steps):
            append_sample(0.0, turn_delta / turn_steps)

        movement_steps = max(
            1,
            math.ceil(
                segment_length_m
                / (config.nominal_speed_m_s * config.sample_interval_s)
            ),
        )
        distance_per_step = segment_length_m / movement_steps
        for _ in range(movement_steps):
            append_sample(distance_per_step, 0.0)
        for _ in range(config.stationary_samples_per_node):
            append_sample(0.0, 0.0)

        tag_id = tag_for_node.get(target_id)
        if tag_id is not None:
            checkpoint_events.append(
                CheckpointEvent(
                    sample_index=len(ground_truth) - 1,
                    observation=SimulatedCheckpointObservation(
                        tag_id=tag_id,
                        timestamp_s=timestamp_s,
                        node_id=target_id,
                    ),
                )
            )

    return SimulationTrace(
        route_node_ids=route,
        initial_estimate=initial_estimate,
        ground_truth=tuple(ground_truth),
        ideal_measurements=tuple(ideal_measurements),
        noisy_measurements=tuple(noisy_measurements),
        checkpoint_events=tuple(checkpoint_events),
    )


def run_scenario(
    name: str,
    measurements: Sequence[MotionMeasurement],
    trace: SimulationTrace,
    layout: AprilTagLayout,
    apply_checkpoint_corrections: bool,
) -> ScenarioResult:
    """Estimate from measurements only and score against separate truth output."""
    if len(measurements) != len(trace.ground_truth) - 1:
        raise ValueError("measurement and ground-truth sequence lengths do not align")
    reckoner = DeadReckoner(trace.initial_estimate)
    event_by_index = {
        event.sample_index: event.observation for event in trace.checkpoint_events
    }
    estimates = [reckoner.pose]
    errors = [0.0]
    checkpoint_errors: list[tuple[int, float, float]] = []

    for sample_index, measurement in enumerate(measurements, start=1):
        estimate = reckoner.update(measurement)
        event = event_by_index.get(sample_index)
        if event is not None and apply_checkpoint_corrections:
            truth = trace.ground_truth[sample_index]
            error_before = math.hypot(estimate.x_m - truth.x_m, estimate.y_m - truth.y_m)
            corrected = correct_to_checkpoint(estimate, layout, event.tag_id)
            error_after = math.hypot(corrected.x_m - truth.x_m, corrected.y_m - truth.y_m)
            if corrected.timestamp_s != event.timestamp_s:
                raise ValueError("simulated checkpoint timestamp does not match estimator")
            reckoner = DeadReckoner(corrected)
            estimate = corrected
            checkpoint_errors.append((sample_index, error_before, error_after))
        truth = trace.ground_truth[sample_index]
        estimates.append(estimate)
        errors.append(math.hypot(estimate.x_m - truth.x_m, estimate.y_m - truth.y_m))

    return ScenarioResult(
        name,
        tuple(estimates),
        tuple(errors),
        tuple(checkpoint_errors),
    )


def calculate_metrics(
    result: ScenarioResult,
    measurement_mode: str,
) -> ScenarioMetrics:
    """Calculate mean, RMSE, maximum, final, and checkpoint error metrics."""
    errors = result.errors_m
    before = [entry[1] for entry in result.checkpoint_errors]
    after = [entry[2] for entry in result.checkpoint_errors]
    return ScenarioMetrics(
        scenario=result.name,
        measurement_mode=measurement_mode,
        checkpoint_corrections=len(result.checkpoint_errors),
        mean_position_error_m=sum(errors) / len(errors),
        rmse_position_error_m=math.sqrt(sum(error * error for error in errors) / len(errors)),
        max_position_error_m=max(errors),
        final_position_error_m=errors[-1],
        mean_error_before_checkpoint_m=sum(before) / len(before) if before else 0.0,
        mean_error_after_checkpoint_m=sum(after) / len(after) if after else 0.0,
    )


def _write_json(path: Path, content: object) -> None:
    path.write_text(
        json.dumps(content, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_trajectory_csv(
    path: Path,
    trace: SimulationTrace,
    ideal: ScenarioResult,
    noisy: ScenarioResult,
    corrected: ScenarioResult,
) -> None:
    events = {event.sample_index: event.observation for event in trace.checkpoint_events}
    fieldnames = [
        "sample_index",
        "timestamp_s",
        "ground_truth_x_m",
        "ground_truth_y_m",
        "ground_truth_heading_rad",
        "wheel_displacement_m",
        "imu_yaw_delta_rad",
        "ideal_x_m",
        "ideal_y_m",
        "ideal_error_m",
        "noisy_x_m",
        "noisy_y_m",
        "noisy_error_m",
        "corrected_x_m",
        "corrected_y_m",
        "corrected_error_m",
        "checkpoint_tag_id",
        "checkpoint_node_id",
        "correction_error_before_m",
        "correction_error_after_m",
    ]
    before_after = {
        sample_index: (before, after)
        for sample_index, before, after in corrected.checkpoint_errors
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for index, truth in enumerate(trace.ground_truth):
            measurement = (
                trace.noisy_measurements[index - 1] if index > 0 else None
            )
            event = events.get(index)
            correction_errors = before_after.get(index, ("", ""))
            writer.writerow(
                {
                    "sample_index": index,
                    "timestamp_s": f"{truth.timestamp_s:.6f}",
                    "ground_truth_x_m": f"{truth.x_m:.6f}",
                    "ground_truth_y_m": f"{truth.y_m:.6f}",
                    "ground_truth_heading_rad": f"{truth.heading_rad:.8f}",
                    "wheel_displacement_m": (
                        f"{measurement.wheel_displacement_m:.8f}"
                        if measurement
                        else ""
                    ),
                    "imu_yaw_delta_rad": (
                        f"{measurement.imu_yaw_delta_rad:.8f}"
                        if measurement
                        else ""
                    ),
                    "ideal_x_m": f"{ideal.estimates[index].x_m:.6f}",
                    "ideal_y_m": f"{ideal.estimates[index].y_m:.6f}",
                    "ideal_error_m": f"{ideal.errors_m[index]:.8f}",
                    "noisy_x_m": f"{noisy.estimates[index].x_m:.6f}",
                    "noisy_y_m": f"{noisy.estimates[index].y_m:.6f}",
                    "noisy_error_m": f"{noisy.errors_m[index]:.8f}",
                    "corrected_x_m": f"{corrected.estimates[index].x_m:.6f}",
                    "corrected_y_m": f"{corrected.estimates[index].y_m:.6f}",
                    "corrected_error_m": f"{corrected.errors_m[index]:.8f}",
                    "checkpoint_tag_id": event.tag_id if event else "",
                    "checkpoint_node_id": event.node_id if event else "",
                    "correction_error_before_m": correction_errors[0],
                    "correction_error_after_m": correction_errors[1],
                }
            )


def _write_metrics_csv(path: Path, metrics: Sequence[ScenarioMetrics]) -> None:
    fieldnames = list(asdict(metrics[0]).keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            row = asdict(metric)
            for key, value in row.items():
                if isinstance(value, float):
                    row[key] = f"{value:.8f}"
            writer.writerow(row)


def _svg_header(title: str, description: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">',
        "<rect width=\"1400\" height=\"900\" fill=\"#ffffff\"/>",
        f"<title>{xml_utils.escape(title)}</title>",
        f"<desc>{xml_utils.escape(description)}</desc>",
        '<style>text{font-family:Arial,sans-serif;fill:#1f2937}.title{font-size:30px;font-weight:bold}.subtitle{font-size:17px}.axis{stroke:#334155;stroke-width:2}.grid{stroke:#e2e8f0;stroke-width:1}.truth{stroke:#166534;stroke-width:5;fill:none}.dead{stroke:#dc2626;stroke-width:4;fill:none;stroke-dasharray:12 8}.corrected{stroke:#2563eb;stroke-width:4;fill:none}.checkpoint{fill:#f59e0b;stroke:#7c2d12;stroke-width:3}.legend{font-size:18px}.tick{font-size:14px}</style>',
    ]


def _polyline(points: Iterable[tuple[float, float]], css_class: str) -> str:
    values = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polyline class="{css_class}" points="{values}"/>'


def _write_trajectory_svg(
    path: Path,
    graph: StoreGraph,
    layout: AprilTagLayout,
    trace: SimulationTrace,
    noisy: ScenarioResult,
    corrected: ScenarioResult | None,
    title: str,
) -> None:
    left, top, width, height = 110.0, 130.0, 1120.0, 650.0
    x_min, x_max = 0.0, 24.0
    y_min, y_max = 0.0, 18.0

    def point(x_m: float, y_m: float) -> tuple[float, float]:
        return (
            left + (x_m - x_min) / (x_max - x_min) * width,
            top + height - (y_m - y_min) / (y_max - y_min) * height,
        )

    lines = _svg_header(
        title,
        "Simulated store-floor coordinate plot. All dimensions and measurements are assumptions.",
    )
    lines.append(f'<text x="{left}" y="52" class="title">{xml_utils.escape(title)}</text>')
    lines.append(
        '<text x="110" y="84" class="subtitle">Simulated coordinates (m); not a physical hardware accuracy result</text>'
    )
    for x_tick in range(0, 25, 4):
        x, _ = point(x_tick, 0.0)
        lines.extend(
            [
                f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + height}"/>',
                f'<text class="tick" x="{x:.1f}" y="{top + height + 24}" text-anchor="middle">{x_tick}</text>',
            ]
        )
    for y_tick in range(0, 19, 3):
        _, y = point(0.0, y_tick)
        lines.extend(
            [
                f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + width}" y2="{y:.1f}"/>',
                f'<text class="tick" x="{left - 18}" y="{y + 5:.1f}" text-anchor="end">{y_tick}</text>',
            ]
        )
    lines.extend(
        [
            f'<line class="axis" x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top + height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + height}"/>',
            f'<text x="{left + width / 2}" y="842" text-anchor="middle" class="legend">x (m), east</text>',
            f'<text x="32" y="{top + height / 2}" transform="rotate(-90 32 {top + height / 2})" text-anchor="middle" class="legend">y (m), north</text>',
        ]
    )
    for edge in graph.edges:
        source = graph.node(edge.source)
        target = graph.node(edge.target)
        x1, y1 = point(source.x_m, source.y_m)
        x2, y2 = point(target.x_m, target.y_m)
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#cbd5e1" stroke-width="2"/>'
        )
    truth_points = [point(p.x_m, p.y_m) for p in trace.ground_truth]
    dead_points = [point(p.x_m, p.y_m) for p in noisy.estimates]
    lines.append(_polyline(truth_points, "truth"))
    lines.append(_polyline(dead_points, "dead"))
    if corrected is not None:
        lines.append(
            _polyline([point(p.x_m, p.y_m) for p in corrected.estimates], "corrected")
        )
    for checkpoint in layout.checkpoints.values():
        cx, cy = point(checkpoint.x_m, checkpoint.y_m)
        lines.append(
            f'<circle class="checkpoint" cx="{cx:.2f}" cy="{cy:.2f}" r="9"><title>tag {checkpoint.tag_id}: {xml_utils.escape(checkpoint.node_id)}</title></circle>'
        )
    legend_items = [
        ("Ground truth", "truth"),
        ("Noisy dead reckoning", "dead"),
    ]
    if corrected is not None:
        legend_items.append(("Noisy + simulated checkpoint corrections", "corrected"))
    legend_x = 770
    for index, (label, css_class) in enumerate(legend_items):
        y = 112 + index * 29
        lines.append(f'<line class="{css_class}" x1="{legend_x}" y1="{y}" x2="{legend_x + 42}" y2="{y}"/>')
        lines.append(f'<text x="{legend_x + 52}" y="{y + 6}" class="legend">{xml_utils.escape(label)}</text>')
    lines.append('<circle class="checkpoint" cx="1220" cy="112" r="8"/>')
    lines.append('<text x="1235" y="118" class="legend">AprilTag checkpoint</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_error_svg(
    path: Path,
    trace: SimulationTrace,
    ideal: ScenarioResult,
    noisy: ScenarioResult,
    corrected: ScenarioResult,
) -> None:
    left, top, width, height = 120.0, 130.0, 1120.0, 650.0
    max_time = max(point.timestamp_s for point in trace.ground_truth)
    max_error = max(max(noisy.errors_m), max(corrected.errors_m), 0.05) * 1.08

    def point(timestamp_s: float, error_m: float) -> tuple[float, float]:
        return (
            left + timestamp_s / max_time * width,
            top + height - error_m / max_error * height,
        )

    lines = _svg_header(
        "Position error over time",
        "Actual simulation error series for ideal, noisy, and checkpoint-corrected scenarios.",
    )
    lines.append('<text x="110" y="52" class="title">Position error over time</text>')
    lines.append(
        '<text x="110" y="84" class="subtitle">Euclidean position error (m); checkpoint events are simulated map snaps</text>'
    )
    for tick in range(6):
        y_value = max_error * tick / 5
        y = top + height - tick / 5 * height
        lines.extend(
            [
                f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + width}" y2="{y:.1f}"/>',
                f'<text class="tick" x="{left - 12}" y="{y + 5:.1f}" text-anchor="end">{y_value:.2f}</text>',
            ]
        )
        x_value = max_time * tick / 5
        x = left + tick / 5 * width
        lines.extend(
            [
                f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + height}"/>',
                f'<text class="tick" x="{x:.1f}" y="{top + height + 24}" text-anchor="middle">{x_value:.1f}</text>',
            ]
        )
    lines.extend(
        [
            f'<line class="axis" x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top + height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + height}"/>',
            f'<text x="{left + width / 2}" y="842" text-anchor="middle" class="legend">Elapsed time (s)</text>',
            f'<text x="32" y="{top + height / 2}" transform="rotate(-90 32 {top + height / 2})" text-anchor="middle" class="legend">Position error (m)</text>',
        ]
    )
    for result, css_class in (
        (ideal, "truth"),
        (noisy, "dead"),
        (corrected, "corrected"),
    ):
        lines.append(
            _polyline(
                [
                    point(truth.timestamp_s, error)
                    for truth, error in zip(trace.ground_truth, result.errors_m)
                ],
                css_class,
            )
        )
    for event in trace.checkpoint_events:
        when = trace.ground_truth[event.sample_index].timestamp_s
        x, _ = point(when, 0.0)
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + height}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5 8"/>'
        )
    for index, (label, css_class) in enumerate(
        (
            ("Ideal measurements", "truth"),
            ("Noisy, no corrections", "dead"),
            ("Same noisy stream + corrections", "corrected"),
        )
    ):
        y = 112 + index * 29
        lines.append(f'<line class="{css_class}" x1="770" y1="{y}" x2="812" y2="{y}"/>')
        lines.append(f'<text x="822" y="{y + 6}" class="legend">{label}</text>')
    lines.append('<line x1="1120" y1="112" x2="1162" y2="112" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5 8"/>')
    lines.append('<text x="1172" y="118" class="legend">Checkpoint</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_trajectory_png(
    path: Path,
    graph: StoreGraph,
    layout: AprilTagLayout,
    trace: SimulationTrace,
    noisy: ScenarioResult,
    corrected: ScenarioResult | None,
    title: str,
) -> None:
    """Render a report-size store-coordinate trajectory plot with OpenCV."""
    image = np.full((900, 1400, 3), 255, dtype=np.uint8)
    left, top, width, height = 110, 145, 1120, 650
    x_max, y_max = 24.0, 18.0

    def point(x_m: float, y_m: float) -> tuple[int, int]:
        return (
            round(left + x_m / x_max * width),
            round(top + height - y_m / y_max * height),
        )

    cv2.putText(image, title, (110, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (31, 41, 55), 2, cv2.LINE_AA)
    cv2.putText(
        image,
        "Simulated store-floor coordinates (m); not a physical hardware accuracy result",
        (110, 92),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (71, 85, 105),
        1,
        cv2.LINE_AA,
    )
    for x_tick in range(0, 25, 4):
        x, _ = point(float(x_tick), 0.0)
        cv2.line(image, (x, top), (x, top + height), (226, 232, 240), 1)
        cv2.putText(image, str(x_tick), (x - 10, top + height + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (51, 65, 85), 1, cv2.LINE_AA)
    for y_tick in range(0, 19, 3):
        _, y = point(0.0, float(y_tick))
        cv2.line(image, (left, y), (left + width, y), (226, 232, 240), 1)
        cv2.putText(image, str(y_tick), (left - 35, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (51, 65, 85), 1, cv2.LINE_AA)
    cv2.line(image, (left, top + height), (left + width, top + height), (51, 65, 85), 2)
    cv2.line(image, (left, top), (left, top + height), (51, 65, 85), 2)
    cv2.putText(image, "x (m), east", (600, 850), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (31, 41, 55), 1, cv2.LINE_AA)
    y_label = np.full((32, 150, 3), 255, dtype=np.uint8)
    cv2.putText(y_label, "y (m), north", (3, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (31, 41, 55), 1, cv2.LINE_AA)
    y_label = cv2.rotate(y_label, cv2.ROTATE_90_COUNTERCLOCKWISE)
    image[395:545, 28:60] = y_label

    for edge in graph.edges:
        start = graph.node(edge.source)
        end = graph.node(edge.target)
        cv2.line(image, point(start.x_m, start.y_m), point(end.x_m, end.y_m), (203, 213, 225), 2, cv2.LINE_AA)

    truth_points = np.asarray([point(p.x_m, p.y_m) for p in trace.ground_truth], dtype=np.int32)
    dead_points = np.asarray([point(p.x_m, p.y_m) for p in noisy.estimates], dtype=np.int32)
    cv2.polylines(image, [truth_points], False, (22, 101, 52), 4, cv2.LINE_AA)
    cv2.polylines(image, [dead_points], False, (38, 38, 220), 3, cv2.LINE_AA)
    if corrected is not None:
        corrected_points = np.asarray(
            [point(p.x_m, p.y_m) for p in corrected.estimates], dtype=np.int32
        )
        cv2.polylines(image, [corrected_points], False, (220, 119, 37), 3, cv2.LINE_AA)
    for checkpoint in layout.checkpoints.values():
        center = point(checkpoint.x_m, checkpoint.y_m)
        cv2.circle(image, center, 8, (20, 165, 245), -1, cv2.LINE_AA)
        cv2.circle(image, center, 8, (44, 45, 125), 2, cv2.LINE_AA)
        cv2.putText(image, str(checkpoint.tag_id), (center[0] + 9, center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 50, 20), 1, cv2.LINE_AA)

    legend = [
        ("Ground truth", (22, 101, 52)),
        ("Noisy dead reckoning", (38, 38, 220)),
    ]
    if corrected is not None:
        legend.append(("Noisy + simulated checkpoint corrections", (220, 119, 37)))
    for index, (label, color) in enumerate(legend):
        y = 120 + index * 27
        cv2.line(image, (760, y), (800, y), color, 4, cv2.LINE_AA)
        cv2.putText(image, label, (810, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.circle(image, (1140, 120), 7, (20, 165, 245), -1, cv2.LINE_AA)
    cv2.putText(image, "AprilTag checkpoint", (1155, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (31, 41, 55), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"OpenCV failed to write trajectory figure: {path}")


def _write_error_png(
    path: Path,
    trace: SimulationTrace,
    ideal: ScenarioResult,
    noisy: ScenarioResult,
    corrected: ScenarioResult,
) -> None:
    """Render position error in metres over simulation time in seconds."""
    image = np.full((900, 1400, 3), 255, dtype=np.uint8)
    left, top, width, height = 120, 145, 1120, 650
    max_time = trace.ground_truth[-1].timestamp_s
    max_error = max(max(noisy.errors_m), max(corrected.errors_m), 0.05) * 1.08

    def point(timestamp_s: float, error_m: float) -> tuple[int, int]:
        return (
            round(left + timestamp_s / max_time * width),
            round(top + height - error_m / max_error * height),
        )

    cv2.putText(image, "Position error over time", (110, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (31, 41, 55), 2, cv2.LINE_AA)
    cv2.putText(image, "Euclidean position error (m); vertical markers are simulated checkpoint events", (110, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (71, 85, 105), 1, cv2.LINE_AA)
    for tick in range(6):
        error_value = max_error * tick / 5
        y = top + height - round(tick / 5 * height)
        cv2.line(image, (left, y), (left + width, y), (226, 232, 240), 1)
        cv2.putText(image, f"{error_value:.2f}", (left - 58, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (51, 65, 85), 1, cv2.LINE_AA)
        time_value = max_time * tick / 5
        x = left + round(tick / 5 * width)
        cv2.line(image, (x, top), (x, top + height), (226, 232, 240), 1)
        cv2.putText(image, f"{time_value:.1f}", (x - 18, top + height + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (51, 65, 85), 1, cv2.LINE_AA)
    cv2.line(image, (left, top + height), (left + width, top + height), (51, 65, 85), 2)
    cv2.line(image, (left, top), (left, top + height), (51, 65, 85), 2)
    cv2.putText(image, "Elapsed time (s)", (600, 850), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (31, 41, 55), 1, cv2.LINE_AA)
    y_label = np.full((32, 105, 3), 255, dtype=np.uint8)
    cv2.putText(y_label, "Error (m)", (3, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (31, 41, 55), 1, cv2.LINE_AA)
    y_label = cv2.rotate(y_label, cv2.ROTATE_90_COUNTERCLOCKWISE)
    image[407:512, 28:60] = y_label
    for result, color in (
        (ideal, (22, 101, 52)),
        (noisy, (38, 38, 220)),
        (corrected, (220, 119, 37)),
    ):
        points = np.asarray(
            [
                point(ground_truth.timestamp_s, error)
                for ground_truth, error in zip(trace.ground_truth, result.errors_m)
            ],
            dtype=np.int32,
        )
        cv2.polylines(image, [points], False, color, 3, cv2.LINE_AA)
    for event in trace.checkpoint_events:
        x, _ = point(trace.ground_truth[event.sample_index].timestamp_s, 0.0)
        cv2.line(image, (x, top), (x, top + height), (20, 165, 245), 1, cv2.LINE_AA)
    for index, (label, color) in enumerate(
        (
            ("Ideal measurements", (22, 101, 52)),
            ("Noisy, no corrections", (38, 38, 220)),
            ("Same noisy stream + corrections", (220, 119, 37)),
        )
    ):
        y = 120 + index * 27
        cv2.line(image, (770, y), (810, y), color, 4, cv2.LINE_AA)
        cv2.putText(image, label, (820, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (31, 41, 55), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"OpenCV failed to write error figure: {path}")


def run_evaluation(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
    config: SimulationConfig = SimulationConfig(),
) -> tuple[ScenarioMetrics, ...]:
    """Run three scenarios and write machine-readable outputs and SVG evidence."""
    graph = load_store_graph(DEFAULT_STORE_GRAPH_PATH)
    layout = _load_layout(DEFAULT_APRILTAG_LAYOUT_PATH, graph)
    trace = build_simulation_trace(graph, layout, config)
    ideal = run_scenario("ideal", trace.ideal_measurements, trace, layout, False)
    noisy = run_scenario("noisy_no_corrections", trace.noisy_measurements, trace, layout, False)
    corrected = run_scenario("noisy_checkpoint_corrected", trace.noisy_measurements, trace, layout, True)
    metrics = (
        calculate_metrics(ideal, "zero_noise_zero_bias"),
        calculate_metrics(noisy, "seeded_noise_and_bias"),
        calculate_metrics(corrected, "same_seeded_noise_and_bias"),
    )

    output_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "simulation_config.json", asdict(config))
    _write_trajectory_csv(
        output_root / "trajectory.csv", trace, ideal, noisy, corrected
    )
    _write_metrics_csv(output_root / "metrics.csv", metrics)
    _write_trajectory_svg(
        evidence_root / "C3-POS-001_ground_truth_vs_dead_reckoning.svg",
        graph,
        layout,
        trace,
        noisy,
        None,
        "Ground truth vs noisy dead reckoning",
    )
    _write_trajectory_svg(
        evidence_root / "C3-POS-002_checkpoint_corrected_trajectory.svg",
        graph,
        layout,
        trace,
        noisy,
        corrected,
        "Trajectory with simulated checkpoint corrections",
    )
    _write_error_svg(
        evidence_root / "C3-POS-003_position_error_comparison.svg",
        trace,
        ideal,
        noisy,
        corrected,
    )
    _write_trajectory_png(
        evidence_root / "C3-POS-001_ground_truth_vs_dead_reckoning.png",
        graph,
        layout,
        trace,
        noisy,
        None,
        "Ground truth vs noisy dead reckoning",
    )
    _write_trajectory_png(
        evidence_root / "C3-POS-002_checkpoint_corrected_trajectory.png",
        graph,
        layout,
        trace,
        noisy,
        corrected,
        "Trajectory with simulated checkpoint corrections",
    )
    _write_error_png(
        evidence_root / "C3-POS-003_position_error_comparison.png",
        trace,
        ideal,
        noisy,
        corrected,
    )
    (output_root / "reproducibility.log").write_text(
        "\n".join(
            [
                "Component 3 simulated position-tracking evaluation",
                "Ground truth, sensor streams, and checkpoint events generated deterministically.",
                "AprilTag events in this run are simulated map lookups, not OpenCV image detections.",
                f"Seed: {config.seed}",
                f"Route: {' -> '.join(trace.route_node_ids)}",
                f"Ground-truth samples: {len(trace.ground_truth)}",
                f"Checkpoint observations: {len(trace.checkpoint_events)}",
                "B and C scenarios use the same noisy measurement sequence and ground truth.",
                "All dimensions, speed, noise, and bias values are simulation assumptions, not measured sensor calibration.",
                "No physical-camera, wheel-encoder, or IMU accuracy claim is made.",
                "",
                "Metrics:",
                *[
                    (
                        f"{metric.scenario}: mean={metric.mean_position_error_m:.6f} m, "
                        f"RMSE={metric.rmse_position_error_m:.6f} m, "
                        f"max={metric.max_position_error_m:.6f} m, "
                        f"final={metric.final_position_error_m:.6f} m, "
                        f"checkpoint mean before/after="
                        f"{metric.mean_error_before_checkpoint_m:.6f}/"
                        f"{metric.mean_error_after_checkpoint_m:.6f} m"
                    )
                    for metric in metrics
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    """Execute the default deterministic evaluation."""
    metrics = run_evaluation()
    for metric in metrics:
        print(
            f"{metric.scenario}: mean={metric.mean_position_error_m:.6f} m, "
            f"RMSE={metric.rmse_position_error_m:.6f} m, "
            f"max={metric.max_position_error_m:.6f} m, "
            f"final={metric.final_position_error_m:.6f} m, "
            f"checkpoint corrections={metric.checkpoint_corrections}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
