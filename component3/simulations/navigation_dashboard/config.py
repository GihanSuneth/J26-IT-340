"""Configuration and source paths for the offline navigation dashboard."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPONENT_ROOT = REPOSITORY_ROOT / "component3"
STORE_GRAPH_PATH = COMPONENT_ROOT / "data/store_map/store_graph.json"
APRILTAG_LAYOUT_PATH = COMPONENT_ROOT / "data/store_map/apriltag_layout.json"
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DEFAULT_DESTINATION_IDS = ("B1", "B3", "B5")
MAX_DESTINATIONS = 10
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
