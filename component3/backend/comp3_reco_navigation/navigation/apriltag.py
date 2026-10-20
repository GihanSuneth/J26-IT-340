"""Offline AprilTag detection and checkpoint-to-store-node localization."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .store_graph import DEFAULT_STORE_GRAPH_PATH, StoreGraph, load_store_graph


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_APRILTAG_LAYOUT_PATH = REPOSITORY_ROOT / "component3/data/store_map/apriltag_layout.json"
EXPECTED_FAMILY = "tag36h11"


class AprilTagLayoutError(ValueError):
    """Raised when checkpoint-layout data violates localization invariants."""


class OpenCVUnavailableError(RuntimeError):
    """Raised when the optional OpenCV ArUco detector is unavailable."""


class ImageReadError(ValueError):
    """Raised when an input image does not exist or cannot be decoded."""


@dataclass(frozen=True, slots=True)
class AprilTagCheckpoint:
    """One known marker and its simulated store-graph location."""

    tag_id: int
    node_id: str
    x_m: float
    y_m: float
    orientation_deg: float
    size_m: float
    location_name: str


class AprilTagLayout:
    """Read-only checkpoint lookup independent of image processing."""

    def __init__(self, family: str, checkpoints: Mapping[int, AprilTagCheckpoint]) -> None:
        self.family = family
        self._checkpoints = MappingProxyType(dict(checkpoints))

    @property
    def checkpoints(self) -> Mapping[int, AprilTagCheckpoint]:
        return self._checkpoints

    @property
    def tag_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._checkpoints))

    def checkpoint_for(self, tag_id: int) -> AprilTagCheckpoint | None:
        """Return a known checkpoint, or ``None`` for an unknown marker ID."""
        return self._checkpoints.get(tag_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], graph: StoreGraph) -> "AprilTagLayout":
        family = data.get("family")
        if family != EXPECTED_FAMILY:
            raise AprilTagLayoutError(
                f"AprilTag family must be {EXPECTED_FAMILY!r}; received {family!r}"
            )
        raw_tags = data.get("tags")
        if not isinstance(raw_tags, list):
            raise AprilTagLayoutError("AprilTag layout must contain a 'tags' list")

        checkpoints: dict[int, AprilTagCheckpoint] = {}
        mapped_nodes: set[str] = set()
        for index, raw_tag in enumerate(raw_tags):
            if not isinstance(raw_tag, Mapping):
                raise AprilTagLayoutError(f"Tag at index {index} must be an object")
            tag_id = raw_tag.get("tag_id")
            if isinstance(tag_id, bool) or not isinstance(tag_id, int) or tag_id < 0:
                raise AprilTagLayoutError(f"Tag at index {index} has an invalid ID")
            if tag_id in checkpoints:
                raise AprilTagLayoutError(f"Duplicate AprilTag ID: {tag_id}")
            node_id = raw_tag.get("node_id")
            if not isinstance(node_id, str) or node_id not in graph:
                raise AprilTagLayoutError(
                    f"AprilTag {tag_id} references unknown graph node {node_id!r}"
                )
            if node_id in mapped_nodes:
                raise AprilTagLayoutError(
                    f"Graph node {node_id!r} has more than one AprilTag checkpoint"
                )
            try:
                x_m = _finite_number(raw_tag["x_m"], "x_m", tag_id)
                y_m = _finite_number(raw_tag["y_m"], "y_m", tag_id)
                orientation_deg = _finite_number(raw_tag["orientation_deg"], "orientation_deg", tag_id)
                size_m = _finite_number(raw_tag["size_m"], "size_m", tag_id)
            except KeyError as exc:
                raise AprilTagLayoutError(
                    f"AprilTag {tag_id} is missing field {exc.args[0]!r}"
                ) from exc
            location_name = raw_tag.get("location_name")
            if not isinstance(location_name, str) or not location_name.strip():
                raise AprilTagLayoutError(f"AprilTag {tag_id} has an invalid location_name")
            if not 0 <= orientation_deg < 360:
                raise AprilTagLayoutError(f"AprilTag {tag_id} orientation must be in [0, 360)")
            if size_m <= 0:
                raise AprilTagLayoutError(f"AprilTag {tag_id} size_m must be positive")

            node = graph.node(node_id)
            if not (
                math.isclose(x_m, node.x_m, abs_tol=1e-9)
                and math.isclose(y_m, node.y_m, abs_tol=1e-9)
            ):
                raise AprilTagLayoutError(
                    f"AprilTag {tag_id} coordinates do not match graph node {node_id!r}"
                )
            checkpoints[tag_id] = AprilTagCheckpoint(
                tag_id, node_id, x_m, y_m, orientation_deg, size_m, location_name
            )
            mapped_nodes.add(node_id)
        return cls(family, checkpoints)


@dataclass(frozen=True, slots=True)
class AprilTagDetection:
    """One detector observation in image pixel coordinates."""

    marker_id: int
    corners_px: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class CheckpointLocalization:
    """A detected ID with an optional known checkpoint assignment."""

    marker_id: int
    checkpoint: AprilTagCheckpoint | None

    @property
    def is_known_checkpoint(self) -> bool:
        return self.checkpoint is not None


def _finite_number(value: object, field: str, tag_id: int) -> float:
    if isinstance(value, bool):
        raise AprilTagLayoutError(f"AprilTag {tag_id} has invalid {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AprilTagLayoutError(f"AprilTag {tag_id} has invalid {field}") from exc
    if not math.isfinite(number):
        raise AprilTagLayoutError(f"AprilTag {tag_id} has non-finite {field}")
    return number


def load_apriltag_layout(
    path: str | Path = DEFAULT_APRILTAG_LAYOUT_PATH,
    graph: StoreGraph | None = None,
) -> AprilTagLayout:
    """Load and validate the eight-checkpoint JSON layout against the graph."""
    layout_path = Path(path)
    try:
        with layout_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AprilTagLayoutError(f"Unable to load AprilTag layout {layout_path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise AprilTagLayoutError("AprilTag layout JSON root must be an object")
    return AprilTagLayout.from_dict(
        data,
        graph if graph is not None else load_store_graph(DEFAULT_STORE_GRAPH_PATH),
    )


def localize_marker_ids(
    marker_ids: Sequence[int], layout: AprilTagLayout
) -> tuple[CheckpointLocalization, ...]:
    """Map unique IDs to checkpoints while retaining unknown IDs explicitly."""
    seen: set[int] = set()
    results: list[CheckpointLocalization] = []
    for marker_id in marker_ids:
        if isinstance(marker_id, bool) or not isinstance(marker_id, int):
            raise TypeError("Detected marker IDs must be integers")
        if marker_id in seen:
            continue
        seen.add(marker_id)
        results.append(CheckpointLocalization(marker_id, layout.checkpoint_for(marker_id)))
    return tuple(results)


def localize_detections(
    detections: Sequence[AprilTagDetection], layout: AprilTagLayout
) -> tuple[CheckpointLocalization, ...]:
    """Map detector observations without coupling lookup to image processing."""
    return localize_marker_ids([item.marker_id for item in detections], layout)


def _load_aruco() -> tuple[Any, Any]:
    try:
        cv2 = importlib.import_module("cv2")
    except ModuleNotFoundError as exc:
        raise OpenCVUnavailableError(
            "OpenCV ArUco support is unavailable; install opencv-contrib-python "
            "in a Python-compatible environment"
        ) from exc
    aruco = getattr(cv2, "aruco", None)
    if aruco is None or not hasattr(aruco, "DICT_APRILTAG_36h11"):
        raise OpenCVUnavailableError(
            "Installed OpenCV does not provide cv2.aruco.DICT_APRILTAG_36h11; "
            "install a compatible opencv-contrib-python build"
        )
    return cv2, aruco


def detect_apriltags_frame(image: Any) -> tuple[AprilTagDetection, ...]:
    """Detect tag36h11 markers in an OpenCV image array without side effects."""
    cv2, aruco = _load_aruco()
    if image is None:
        raise ImageReadError("OpenCV image array is empty")
    if not hasattr(image, "ndim") or image.ndim not in (2, 3):
        raise ImageReadError("OpenCV image array must be grayscale or BGR/BGRA")
    if image.ndim == 3:
        conversion = cv2.COLOR_BGRA2GRAY if image.shape[2] == 4 else cv2.COLOR_BGR2GRAY
        image = cv2.cvtColor(image, conversion)
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
    if hasattr(aruco, "DetectorParameters"):
        parameters = aruco.DetectorParameters()
    elif hasattr(aruco, "DetectorParameters_create"):
        parameters = aruco.DetectorParameters_create()
    else:
        raise OpenCVUnavailableError("OpenCV ArUco has no detector-parameters API")

    if hasattr(aruco, "ArucoDetector"):
        corners, ids, _ = aruco.ArucoDetector(dictionary, parameters).detectMarkers(image)
    elif hasattr(aruco, "detectMarkers"):
        corners, ids, _ = aruco.detectMarkers(image, dictionary, parameters=parameters)
    else:
        raise OpenCVUnavailableError("OpenCV ArUco has no supported detection API")
    if ids is None:
        return ()
    detections = [
        AprilTagDetection(
            int(marker_id),
            tuple((float(point[0]), float(point[1])) for point in marker_corners.reshape(-1, 2)),
        )
        for marker_corners, marker_id in zip(corners, ids.reshape(-1))
    ]
    return tuple(sorted(detections, key=lambda item: item.marker_id))


def detect_apriltags(image_path: str | Path) -> tuple[AprilTagDetection, ...]:
    """Decode an image file and pass it to the reusable array detector."""
    path = Path(image_path)
    if not path.is_file():
        raise ImageReadError(f"Image file does not exist: {path}")
    cv2, _ = _load_aruco()
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ImageReadError(f"OpenCV could not decode image: {path}")
    return detect_apriltags_frame(image)
