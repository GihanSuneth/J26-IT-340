"""Run reproducible labeled route-deviation scenarios and save evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
import math
from pathlib import Path
import random
from typing import Sequence
import xml.sax.saxutils as xml_utils

import cv2
import numpy as np

from .deviation import DeviationState, RouteDeviationMonitor
from .dead_reckoning import PositionEstimate
from .held_karp import held_karp_route
from .store_graph import DEFAULT_STORE_GRAPH_PATH, StoreGraph, load_store_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "component3/evaluation/route_deviation"
DEFAULT_EVIDENCE_ROOT = (
    REPOSITORY_ROOT
    / "component3/docs/research_evidence/05_position_tracking/screenshots"
)


@dataclass(frozen=True, slots=True)
class DeviationSimulationConfig:
    """Explicit deterministic synthetic-observation and detector assumptions."""

    seed: int = 5041
    sample_interval_s: float = 0.5
    position_noise_std_m: float = 0.04
    off_route_offset_m: float = 1.5
    base_threshold_m: float = 0.3
    threshold_slope_per_m: float = 0.02
    hysteresis_m: float = 0.15
    enter_confirmations: int = 3
    recovery_confirmations: int = 2
    start_node_id: str = "ENT"
    checkout_node_id: str = "CHK"
    shopping_stop_ids: tuple[str, ...] = ("B1", "B3", "B5")

    def __post_init__(self) -> None:
        """Reject assumptions that cannot produce a deterministic evaluation."""
        positive = (self.sample_interval_s, self.off_route_offset_m)
        nonnegative = (
            self.position_noise_std_m,
            self.base_threshold_m,
            self.threshold_slope_per_m,
            self.hysteresis_m,
        )
        if any(not math.isfinite(item) or item <= 0 for item in positive):
            raise ValueError("sample interval and off-route offset must be positive")
        if any(not math.isfinite(item) or item < 0 for item in nonnegative):
            raise ValueError("noise, thresholds, and hysteresis must be nonnegative")
        if self.enter_confirmations < 1 or self.recovery_confirmations < 1:
            raise ValueError("confirmation counts must be positive")


@dataclass(frozen=True, slots=True)
class SyntheticSample:
    """One independent ground-truth label and estimated position sample."""

    scenario: str
    sample_index: int
    timestamp_s: float
    ground_truth_x_m: float
    ground_truth_y_m: float
    estimate_x_m: float
    estimate_y_m: float
    ground_truth_off_route: bool


@dataclass(frozen=True, slots=True)
class DeviationObservation:
    """Detector response paired with an independent synthetic truth label."""

    sample: SyntheticSample
    valid_position: bool
    distance_m: float | None
    threshold_m: float | None
    exit_threshold_m: float | None
    instantaneous_deviation: bool | None
    detected_deviation: bool | None
    entered_deviation: bool
    recovered: bool
    classification_included: bool


@dataclass(frozen=True, slots=True)
class ScenarioMetrics:
    """Confusion counts, alarm events, and confirmed-deviation delays."""

    scenario: str
    scenario_count: int
    total_observations: int
    valid_observations: int
    invalid_observations: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    detection_delay_samples_mean: float
    detection_delay_seconds_mean: float
    detected_off_route_episodes: int
    missed_off_route_episodes: int
    false_alarm_events: int


def _route_geometry(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
) -> tuple[float, tuple[float, ...]]:
    """Return coordinate-polyline length and cumulative node distances."""
    cumulative = [0.0]
    for start_id, end_id in zip(route_node_ids, route_node_ids[1:]):
        start = graph.node(start_id)
        end = graph.node(end_id)
        cumulative.append(
            cumulative[-1] + math.hypot(end.x_m - start.x_m, end.y_m - start.y_m)
        )
    return cumulative[-1], tuple(cumulative)


def _point_at_progress(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    cumulative: Sequence[float],
    progress_m: float,
) -> tuple[float, float, float, float]:
    """Interpolate route x/y and return its local unit tangent."""
    if len(route_node_ids) == 1:
        node = graph.node(route_node_ids[0])
        return node.x_m, node.y_m, 1.0, 0.0
    bounded = min(cumulative[-1], max(0.0, progress_m))
    for index, (start_id, end_id) in enumerate(zip(route_node_ids, route_node_ids[1:])):
        start = graph.node(start_id)
        end = graph.node(end_id)
        length = cumulative[index + 1] - cumulative[index]
        if bounded <= cumulative[index + 1] or index == len(route_node_ids) - 2:
            if length == 0.0:
                return start.x_m, start.y_m, 1.0, 0.0
            fraction = (bounded - cumulative[index]) / length
            tangent_x = (end.x_m - start.x_m) / length
            tangent_y = (end.y_m - start.y_m) / length
            return (
                start.x_m + fraction * (end.x_m - start.x_m),
                start.y_m + fraction * (end.y_m - start.y_m),
                tangent_x,
                tangent_y,
            )
    end = graph.node(route_node_ids[-1])
    return end.x_m, end.y_m, 1.0, 0.0


def _sample(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    cumulative: Sequence[float],
    rng: random.Random,
    config: DeviationSimulationConfig,
    scenario: str,
    sample_index: int,
    progress_m: float,
    *,
    off_route: bool = False,
    noise: bool = True,
    invalid: str | None = None,
) -> SyntheticSample:
    """Create a controlled truth/estimate pair without sharing truth with detection."""
    x_m, y_m, tangent_x, tangent_y = _point_at_progress(
        graph, route_node_ids, cumulative, progress_m
    )
    if off_route:
        x_m += -tangent_y * config.off_route_offset_m
        y_m += tangent_x * config.off_route_offset_m
    estimate_x = x_m + (rng.gauss(0, config.position_noise_std_m) if noise else 0.0)
    estimate_y = y_m + (rng.gauss(0, config.position_noise_std_m) if noise else 0.0)
    if invalid == "nan":
        estimate_x = math.nan
    elif invalid == "infinity":
        estimate_y = math.inf
    return SyntheticSample(
        scenario=scenario,
        sample_index=sample_index,
        timestamp_s=sample_index * config.sample_interval_s,
        ground_truth_x_m=x_m,
        ground_truth_y_m=y_m,
        estimate_x_m=estimate_x,
        estimate_y_m=estimate_y,
        ground_truth_off_route=off_route,
    )


def build_scenarios(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    config: DeviationSimulationConfig,
) -> tuple[tuple[str, tuple[SyntheticSample, ...]], ...]:
    """Build eight seeded, labeled scenarios from the planned graph route."""
    if not route_node_ids:
        raise ValueError("route_node_ids must not be empty")
    rng = random.Random(config.seed)
    total_length, cumulative = _route_geometry(graph, route_node_ids)
    if total_length <= 0:
        raise ValueError("planned route must have positive coordinate length")

    def group(
        name: str,
        progresses: Sequence[float],
        off_flags: Sequence[bool] | None = None,
        *,
        noise: bool = True,
        invalids: dict[int, str] | None = None,
    ) -> tuple[str, tuple[SyntheticSample, ...]]:
        flags = off_flags or (False,) * len(progresses)
        rows = tuple(
            _sample(
                graph,
                route_node_ids,
                cumulative,
                rng,
                config,
                name,
                index,
                progress,
                off_route=flags[index],
                noise=noise,
                invalid=(invalids or {}).get(index),
            )
            for index, progress in enumerate(progresses)
        )
        return name, rows

    baseline = [total_length * i / 7 for i in range(8)]
    brief_flags = [False, False, True, False, False, False]
    sustained_progress = [total_length * (0.48 + i * 0.005) for i in range(8)]
    corner_index = min(2, len(route_node_ids) - 2)
    corner_progress = cumulative[corner_index]
    corner = [
        max(0.0, corner_progress - 0.2),
        max(0.0, corner_progress - 0.1),
        corner_progress,
        min(total_length, corner_progress + 0.1),
        min(total_length, corner_progress + 0.2),
        min(total_length, corner_progress + 0.3),
    ]
    endpoint = [
        max(0.0, total_length - 0.8),
        max(0.0, total_length - 0.5),
        max(0.0, total_length - 0.2),
        total_length,
        total_length,
        total_length,
    ]
    invalid_rows = group(
        "invalid_position_data",
        [total_length * 0.2, total_length * 0.25, total_length * 0.3, total_length * 0.35],
        invalids={2: "nan", 3: "infinity"},
    )
    return (
        group("following_planned_route", baseline, noise=False),
        group("small_position_noise", baseline),
        group("brief_single_sample_deviation", [total_length * 0.5] * 6, brief_flags),
        group("sustained_off_route_movement", sustained_progress, [True] * 8),
        group(
            "return_to_route",
            [total_length * 0.55] * 5 + [total_length * 0.55] * 5,
            [True] * 5 + [False] * 5,
        ),
        group("near_route_corner", corner),
        group("near_route_endpoint", endpoint),
        invalid_rows,
    )


def _process_scenario(
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    samples: Sequence[SyntheticSample],
    config: DeviationSimulationConfig,
) -> tuple[DeviationObservation, ...]:
    """Run estimates through a fresh monitor, isolating truth labels."""
    monitor = RouteDeviationMonitor(
        graph,
        route_node_ids,
        base_threshold_m=config.base_threshold_m,
        threshold_slope_per_m=config.threshold_slope_per_m,
        hysteresis_m=config.hysteresis_m,
        enter_confirmations=config.enter_confirmations,
        recovery_confirmations=config.recovery_confirmations,
    )
    observations: list[DeviationObservation] = []
    for sample in samples:
        try:
            estimate = PositionEstimate(
                sample.estimate_x_m, sample.estimate_y_m, 0.0, sample.timestamp_s
            )
        except ValueError:
            observations.append(
                DeviationObservation(sample, False, None, None, None, None, None, False, False, False)
            )
            continue
        state: DeviationState = monitor.update(estimate)
        observations.append(
            DeviationObservation(
                sample=sample,
                valid_position=True,
                distance_m=state.measurement.distance_m,
                threshold_m=state.measurement.threshold_m,
                exit_threshold_m=state.exit_threshold_m,
                instantaneous_deviation=state.measurement.is_deviating,
                detected_deviation=state.is_deviated,
                entered_deviation=state.entered_deviation,
                recovered=state.recovered,
                classification_included=True,
            )
        )
    return tuple(observations)


def _classification_metrics(
    scenario: str,
    observations: Sequence[DeviationObservation],
    sample_interval_s: float,
) -> ScenarioMetrics:
    """Compute scenario/aggregate metrics and detected episode delays."""
    valid = [item for item in observations if item.classification_included]
    tp = sum(item.sample.ground_truth_off_route and item.detected_deviation for item in valid)
    fp = sum((not item.sample.ground_truth_off_route) and item.detected_deviation for item in valid)
    tn = sum((not item.sample.ground_truth_off_route) and (not item.detected_deviation) for item in valid)
    fn = sum(item.sample.ground_truth_off_route and (not item.detected_deviation) for item in valid)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    delays: list[int] = []
    episode_start: int | None = None
    detected_in_episode = False
    missed_episodes = 0
    for index, observation in enumerate(observations):
        is_off = observation.classification_included and observation.sample.ground_truth_off_route
        if is_off and episode_start is None:
            episode_start = index
            detected_in_episode = False
        if episode_start is not None and is_off and observation.entered_deviation:
            delays.append(index - episode_start)
            detected_in_episode = True
        episode_ended = episode_start is not None and (
            not is_off or index == len(observations) - 1
        )
        if episode_ended:
            if not detected_in_episode:
                missed_episodes += 1
            episode_start = None
            detected_in_episode = False
    false_alarm_events = sum(
        item.entered_deviation
        and item.classification_included
        and not item.sample.ground_truth_off_route
        for item in observations
    )
    return ScenarioMetrics(
        scenario=scenario,
        scenario_count=1,
        total_observations=len(observations),
        valid_observations=len(valid),
        invalid_observations=len(observations) - len(valid),
        true_positives=int(tp),
        false_positives=int(fp),
        true_negatives=int(tn),
        false_negatives=int(fn),
        precision=precision,
        recall=recall,
        f1_score=f1,
        detection_delay_samples_mean=(sum(delays) / len(delays) if delays else 0.0),
        detection_delay_seconds_mean=(
            sum(delays) * sample_interval_s / len(delays) if delays else 0.0
        ),
        detected_off_route_episodes=len(delays),
        missed_off_route_episodes=missed_episodes,
        false_alarm_events=false_alarm_events,
    )


def _aggregate_metrics(
    grouped: Sequence[tuple[str, tuple[DeviationObservation, ...]]],
    sample_interval_s: float,
) -> tuple[ScenarioMetrics, ...]:
    """Return per-scenario and micro-averaged overall evaluation rows."""
    rows = [
        _classification_metrics(name, observations, sample_interval_s)
        for name, observations in grouped
    ]
    tp = sum(row.true_positives for row in rows)
    fp = sum(row.false_positives for row in rows)
    tn = sum(row.true_negatives for row in rows)
    fn = sum(row.false_negatives for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    detected_episodes = sum(row.detected_off_route_episodes for row in rows)
    delay_samples = (
        sum(
            row.detection_delay_samples_mean * row.detected_off_route_episodes
            for row in rows
        )
        / detected_episodes
        if detected_episodes
        else 0.0
    )
    aggregate = ScenarioMetrics(
        scenario="overall",
        scenario_count=len(grouped),
        total_observations=sum(row.total_observations for row in rows),
        valid_observations=sum(row.valid_observations for row in rows),
        invalid_observations=sum(row.invalid_observations for row in rows),
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        detection_delay_samples_mean=delay_samples,
        detection_delay_seconds_mean=delay_samples * sample_interval_s,
        detected_off_route_episodes=detected_episodes,
        missed_off_route_episodes=sum(row.missed_off_route_episodes for row in rows),
        false_alarm_events=sum(row.false_alarm_events for row in rows),
    )
    return tuple(rows + [aggregate])


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    """Write dictionaries with consistent field order and newline handling."""
    if not rows:
        raise ValueError(f"cannot write an empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def _observation_rows(
    grouped: Sequence[tuple[str, tuple[DeviationObservation, ...]]],
) -> list[dict[str, object]]:
    """Flatten scenarios while retaining truth and estimate as separate fields."""
    rows: list[dict[str, object]] = []
    for scenario, observations in grouped:
        for item in observations:
            sample = item.sample
            rows.append(
                {
                    "scenario": scenario,
                    "sample_index": sample.sample_index,
                    "timestamp_s": f"{sample.timestamp_s:.3f}",
                    "ground_truth_x_m": sample.ground_truth_x_m,
                    "ground_truth_y_m": sample.ground_truth_y_m,
                    "ground_truth_off_route": sample.ground_truth_off_route,
                    "estimated_x_m": sample.estimate_x_m,
                    "estimated_y_m": sample.estimate_y_m,
                    "valid_position": item.valid_position,
                    "distance_to_route_m": item.distance_m,
                    "enter_threshold_m": item.threshold_m,
                    "exit_threshold_m": item.exit_threshold_m,
                    "instantaneous_deviation": item.instantaneous_deviation,
                    "detected_deviation": item.detected_deviation,
                    "entered_deviation": item.entered_deviation,
                    "recovered": item.recovered,
                    "classification_included": item.classification_included,
                }
            )
    return rows


def _metrics_rows(metrics: Sequence[ScenarioMetrics]) -> list[dict[str, object]]:
    """Format metrics for CSV without changing computed values."""
    result: list[dict[str, object]] = []
    for metric in metrics:
        row = asdict(metric)
        for key, value in row.items():
            if isinstance(value, float):
                row[key] = f"{value:.6f}"
        result.append(row)
    return result


def _write_route_figure(
    path: Path,
    graph: StoreGraph,
    route_node_ids: Sequence[str],
    observations: Sequence[DeviationObservation],
) -> None:
    """Render planned route and sampled actual/detected off-route positions."""
    width, height = 1400, 900
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    left, top, plot_w, plot_h = 100, 135, 1120, 650
    scale = min(plot_w / 24.0, plot_h / 18.0)
    map_w, map_h = 24.0 * scale, 18.0 * scale
    map_left = left + (plot_w - map_w) / 2.0
    map_top = top + (plot_h - map_h) / 2.0

    def pixel(x_m: float, y_m: float) -> tuple[int, int]:
        return (
            round(map_left + x_m * scale),
            round(map_top + map_h - y_m * scale),
        )

    cv2.putText(image, "Route-deviation scenarios", (85, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (31, 41, 55), 2, cv2.LINE_AA)
    cv2.putText(image, "Synthetic estimates and independently labeled truth; distances in metres", (85, 91), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (71, 85, 105), 1, cv2.LINE_AA)
    for x_tick in range(0, 25, 4):
        x, _ = pixel(float(x_tick), 0.0)
        cv2.line(image, (x, round(map_top)), (x, round(map_top + map_h)), (235, 238, 242), 1, cv2.LINE_AA)
        cv2.putText(image, str(x_tick), (x - 7, round(map_top + map_h + 21)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (71, 85, 105), 1, cv2.LINE_AA)
    for y_tick in range(0, 19, 3):
        _, y = pixel(0.0, float(y_tick))
        cv2.line(image, (round(map_left), y), (round(map_left + map_w), y), (235, 238, 242), 1, cv2.LINE_AA)
        cv2.putText(image, str(y_tick), (round(map_left - 24), y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (71, 85, 105), 1, cv2.LINE_AA)
    for edge in graph.edges:
        a, b = graph.node(edge.source), graph.node(edge.target)
        cv2.line(image, pixel(a.x_m, a.y_m), pixel(b.x_m, b.y_m), (221, 226, 233), 2, cv2.LINE_AA)
    route_points = np.array(
        [pixel(graph.node(node_id).x_m, graph.node(node_id).y_m) for node_id in route_node_ids],
        dtype=np.int32,
    )
    cv2.polylines(image, [route_points], False, (34, 86, 164), 5, cv2.LINE_AA)
    route_set = {"sustained_off_route_movement", "return_to_route", "brief_single_sample_deviation"}
    for observation in observations:
        sample = observation.sample
        if sample.scenario not in route_set or not observation.valid_position:
            continue
        location = pixel(sample.estimate_x_m, sample.estimate_y_m)
        if sample.ground_truth_off_route and observation.detected_deviation:
            color = (30, 30, 220)
        elif sample.ground_truth_off_route:
            color = (0, 165, 255)
        elif observation.detected_deviation:
            color = (180, 40, 180)
        else:
            color = (45, 155, 65)
        cv2.circle(image, location, 8, color, -1, cv2.LINE_AA)
        if observation.entered_deviation:
            cv2.circle(image, location, 14, (10, 10, 10), 2, cv2.LINE_AA)
    for node_id in route_node_ids:
        node = graph.node(node_id)
        center = pixel(node.x_m, node.y_m)
        cv2.circle(image, center, 6, (34, 86, 164), -1, cv2.LINE_AA)
        cv2.putText(image, node_id, (center[0] + 7, center[1] - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (31, 41, 55), 1, cv2.LINE_AA)
    cv2.putText(image, "x (m), east", (580, 813), cv2.FONT_HERSHEY_SIMPLEX, 0.47, (51, 65, 85), 1, cv2.LINE_AA)
    cv2.putText(image, "y (m), north", (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (51, 65, 85), 1, cv2.LINE_AA)
    legend = [
        ("Planned route", (34, 86, 164)),
        ("Labeled on-route sample", (45, 155, 65)),
        ("Off-route, not confirmed", (0, 165, 255)),
        ("Confirmed true deviation", (30, 30, 220)),
        ("False alarm sample", (180, 40, 180)),
        ("Deviation entry event (ring)", (10, 10, 10)),
    ]
    for index, (label, color) in enumerate(legend):
        column = index // 3
        row = index % 3
        x = 130 + column * 560
        y = 820 + row * 28
        cv2.circle(image, (x, y), 7, color, -1, cv2.LINE_AA)
        cv2.putText(image, label, (x + 16, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (31, 41, 55), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"OpenCV could not write route figure: {path}")


def _write_distance_figure(
    path: Path,
    observations: Sequence[DeviationObservation],
    sample_interval_s: float,
) -> None:
    """Plot route-distance samples with changing enter/exit boundaries."""
    usable = [item for item in observations if item.classification_included]
    width, height = 1400, 900
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    left, top, plot_w, plot_h = 110, 145, 1140, 610
    max_distance = max((item.distance_m or 0.0 for item in usable), default=1.0)
    max_threshold = max((item.threshold_m or 0.0 for item in usable), default=1.0)
    max_y = max(0.5, max_distance, max_threshold) * 1.15

    def point(index: int, value: float) -> tuple[int, int]:
        x = left + int(index / max(1, len(usable) - 1) * plot_w)
        y = top + plot_h - int(value / max_y * plot_h)
        return x, y

    cv2.putText(image, "Distance to planned route and hysteresis", (85, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (31, 41, 55), 2, cv2.LINE_AA)
    cv2.putText(image, "Observed Euclidean distance, progress-scaled enter threshold, and lower exit threshold", (85, 91), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (71, 85, 105), 1, cv2.LINE_AA)
    for tick in range(6):
        y_value = max_y * tick / 5
        y = top + plot_h - int(tick / 5 * plot_h)
        cv2.line(image, (left, y), (left + plot_w, y), (226, 232, 240), 1, cv2.LINE_AA)
        cv2.putText(image, f"{y_value:.2f}", (left - 62, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (51, 65, 85), 1, cv2.LINE_AA)
    cv2.line(image, (left, top + plot_h), (left + plot_w, top + plot_h), (51, 65, 85), 2, cv2.LINE_AA)
    scenario_ranges: list[tuple[str, int, int]] = []
    for index, item in enumerate(usable):
        if not scenario_ranges or scenario_ranges[-1][0] != item.sample.scenario:
            scenario_ranges.append((item.sample.scenario, index, index))
        else:
            name, first, _ = scenario_ranges[-1]
            scenario_ranges[-1] = (name, first, index)
    for scenario_index, (_, first, last) in enumerate(scenario_ranges):
        if scenario_index:
            x, _ = point(first, 0.0)
            cv2.line(image, (x, top), (x, top + plot_h), (150, 150, 150), 1, cv2.LINE_AA)
        midpoint = (first + last) // 2
        x, _ = point(midpoint, 0.0)
        cv2.putText(image, f"S{scenario_index + 1}", (x - 10, top + plot_h + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (51, 65, 85), 1, cv2.LINE_AA)
    series = (
        ("distance", [item.distance_m or 0.0 for item in usable], (35, 75, 205)),
        ("enter threshold", [item.threshold_m or 0.0 for item in usable], (40, 150, 55)),
        ("exit threshold", [item.exit_threshold_m or 0.0 for item in usable], (220, 130, 20)),
    )
    for _, values, color in series:
        for _, first, last in scenario_ranges:
            points = np.array(
                [point(index, values[index]) for index in range(first, last + 1)],
                dtype=np.int32,
            )
            if len(points) > 1:
                cv2.polylines(image, [points], False, color, 3, cv2.LINE_AA)
    for index, observation in enumerate(usable):
        if observation.entered_deviation:
            x, _ = point(index, 0.0)
            cv2.line(image, (x, top), (x, top + plot_h), (40, 40, 40), 1, cv2.LINE_AA)
    tick_count = 5
    for tick in range(tick_count + 1):
        sample_index = round(tick / tick_count * (len(usable) - 1))
        x, _ = point(sample_index, 0.0)
        elapsed_s = sample_index * sample_interval_s
        cv2.putText(image, f"{elapsed_s:.1f}", (x - 16, top + plot_h + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (51, 65, 85), 1, cv2.LINE_AA)
    cv2.putText(image, "Concatenated sample time (s); vertical separators mark independent scenario resets", (left, 812), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (51, 65, 85), 1, cv2.LINE_AA)
    for index, (label, _, color) in enumerate(series):
        x = 170 + index * 350
        cv2.line(image, (x, 850), (x + 48, 850), color, 4, cv2.LINE_AA)
        cv2.putText(image, label, (x + 60, 856), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (31, 41, 55), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"OpenCV could not write distance figure: {path}")


def _svg_wrapper(path: Path, title: str, description: str, png_name: str) -> None:
    """Save a portable SVG evidence sheet with the generated raster figure."""
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">\n'
        f"<title>{xml_utils.escape(title)}</title>\n"
        f"<desc>{xml_utils.escape(description)}</desc>\n"
        f'<image href="{xml_utils.escape(png_name)}" width="1400" height="900"/>\n'
        "</svg>\n"
    )
    path.write_text(svg, encoding="utf-8")


def run_evaluation(
    graph: StoreGraph | None = None,
    config: DeviationSimulationConfig = DeviationSimulationConfig(),
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
) -> tuple[ScenarioMetrics, ...]:
    """Run eight seeded scenarios and persist metrics, observations, and figures."""
    graph = graph or load_store_graph(DEFAULT_STORE_GRAPH_PATH)
    route = held_karp_route(
        graph,
        config.start_node_id,
        config.shopping_stop_ids,
        config.checkout_node_id,
    ).route_node_ids
    scenarios = build_scenarios(graph, route, config)
    grouped = tuple(
        (name, _process_scenario(graph, route, samples, config))
        for name, samples in scenarios
    )
    metrics = _aggregate_metrics(grouped, config.sample_interval_s)
    output_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "observations.csv", _observation_rows(grouped))
    _write_csv(output_root / "metrics.csv", _metrics_rows(metrics))
    config_document = {
        **asdict(config),
        "planned_route_node_ids": list(route),
        "coordinate_units": "metres; east is +x and north is +y",
        "threshold_model": "epsilon(d) = base_threshold_m + threshold_slope_per_m * route_progress_m",
        "truth_source": "explicit synthetic scenario labels, independent of detector output",
        "physical_calibration": False,
    }
    (output_root / "simulation_config.json").write_text(
        json.dumps(config_document, indent=2) + "\n", encoding="utf-8"
    )
    overall = metrics[-1]
    log = [
        "Component 3 Phase 5A route-deviation simulation",
        f"Seed: {config.seed}",
        f"Route: {' -> '.join(route)}",
        f"Scenarios: {overall.scenario_count}",
        f"Observations: {overall.total_observations} total; {overall.valid_observations} valid; {overall.invalid_observations} invalid",
        f"Confusion: TP={overall.true_positives}, FP={overall.false_positives}, TN={overall.true_negatives}, FN={overall.false_negatives}",
        f"Precision={overall.precision:.6f}; recall={overall.recall:.6f}; F1={overall.f1_score:.6f}",
        f"Mean detection delay={overall.detection_delay_samples_mean:.6f} samples; {overall.detection_delay_seconds_mean:.6f} s",
        f"Detected off-route episodes={overall.detected_off_route_episodes}; missed episodes={overall.missed_off_route_episodes}; false alarm events={overall.false_alarm_events}",
        "Truth labels are controlled synthetic scenario inputs and are not detector outputs.",
        "No automatic rerouting or physical sensor validation was performed.",
    ]
    (output_root / "reproducibility.log").write_text(
        "\n".join(log) + "\n", encoding="utf-8"
    )
    all_observations = tuple(item for _, values in grouped for item in values)
    route_png = evidence_root / "C3-POS-006_route_deviation_scenarios.png"
    distance_png = evidence_root / "C3-POS-007_distance_hysteresis.png"
    _write_route_figure(route_png, graph, route, all_observations)
    _write_distance_figure(
        distance_png, all_observations, config.sample_interval_s
    )
    _svg_wrapper(
        evidence_root / "C3-POS-006_route_deviation_scenarios.svg",
        "Route-deviation scenarios",
        "Planned route and synthetic on/off-route estimates with detector events.",
        route_png.name,
    )
    _svg_wrapper(
        evidence_root / "C3-POS-007_distance_hysteresis.svg",
        "Distance to planned route and hysteresis",
        "Observed route distance and progress-scaled enter/exit thresholds.",
        distance_png.name,
    )
    print("\n".join(log))
    print(f"Metrics: {output_root / 'metrics.csv'}")
    print(f"Observations: {output_root / 'observations.csv'}")
    return metrics


def main() -> int:
    """Run the default deterministic route-deviation evaluation."""
    run_evaluation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
