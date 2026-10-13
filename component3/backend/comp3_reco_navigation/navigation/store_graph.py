"""Load and validate the undirected weighted Component 3 store graph."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_STORE_GRAPH_PATH = REPOSITORY_ROOT / "component3/data/store_map/store_graph.json"


class GraphValidationError(ValueError):
    """Raised when graph data does not satisfy the routing invariants."""


@dataclass(frozen=True, slots=True)
class StoreNode:
    """One walkable point in the metric store coordinate system."""

    node_id: str
    name: str
    node_type: str
    x_m: float
    y_m: float
    aisle_ref: str | None = None


@dataclass(frozen=True, slots=True)
class StoreEdge:
    """One undirected walking connection with a distance in metres."""

    source: str
    target: str
    distance_m: float


class StoreGraph:
    """Read-only graph interface used by Component 3 routing algorithms."""

    def __init__(
        self,
        nodes: Mapping[str, StoreNode],
        edges: tuple[StoreEdge, ...],
        adjacency: Mapping[str, tuple[tuple[str, float], ...]],
    ) -> None:
        self._nodes = MappingProxyType(dict(nodes))
        self._edges = tuple(edges)
        self._adjacency = MappingProxyType(dict(adjacency))

    @property
    def nodes(self) -> Mapping[str, StoreNode]:
        """Return a read-only node-ID mapping."""
        return self._nodes

    @property
    def edges(self) -> tuple[StoreEdge, ...]:
        """Return immutable undirected edge records."""
        return self._edges

    @property
    def node_ids(self) -> tuple[str, ...]:
        """Return node IDs in deterministic lexical order."""
        return tuple(sorted(self._nodes))

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def node(self, node_id: str) -> StoreNode:
        """Return one node or raise ``KeyError`` for an unknown ID."""
        return self._nodes[node_id]

    def neighbors(self, node_id: str) -> tuple[tuple[str, float], ...]:
        """Return ``(neighbor_id, distance_m)`` pairs sorted by node ID."""
        return self._adjacency[node_id]

    def edge_weight(self, source: str, target: str) -> float:
        """Return an edge distance or raise ``KeyError`` if no edge exists."""
        for neighbor, distance_m in self.neighbors(source):
            if neighbor == target:
                return distance_m
        raise KeyError(f"No edge connects {source!r} and {target!r}")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StoreGraph":
        """Build a graph from the JSON-compatible store-map representation."""
        raw_nodes = data.get("nodes")
        raw_edges = data.get("edges")
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise GraphValidationError("Graph must contain 'nodes' and 'edges' lists")

        nodes: dict[str, StoreNode] = {}
        for index, raw_node in enumerate(raw_nodes):
            if not isinstance(raw_node, Mapping):
                raise GraphValidationError(f"Node at index {index} must be an object")
            node_id = raw_node.get("id")
            if not isinstance(node_id, str) or not node_id.strip():
                raise GraphValidationError(f"Node at index {index} has an invalid ID")
            if node_id in nodes:
                raise GraphValidationError(f"Duplicate node ID: {node_id}")
            try:
                name = raw_node["name"]
                node_type = raw_node["type"]
                x_m = float(raw_node["x_m"])
                y_m = float(raw_node["y_m"])
            except (KeyError, TypeError, ValueError) as exc:
                raise GraphValidationError(
                    f"Node {node_id!r} has invalid required fields"
                ) from exc
            if not isinstance(name, str) or not isinstance(node_type, str):
                raise GraphValidationError(
                    f"Node {node_id!r} name and type must be strings"
                )
            aisle_ref = raw_node.get("aisle_ref")
            if aisle_ref is not None and not isinstance(aisle_ref, str):
                raise GraphValidationError(
                    f"Node {node_id!r} aisle_ref must be a string when present"
                )
            nodes[node_id] = StoreNode(
                node_id=node_id,
                name=name,
                node_type=node_type,
                x_m=x_m,
                y_m=y_m,
                aisle_ref=aisle_ref,
            )

        adjacency_lists: dict[str, list[tuple[str, float]]] = {
            node_id: [] for node_id in nodes
        }
        edges: list[StoreEdge] = []
        seen_pairs: set[frozenset[str]] = set()
        for index, raw_edge in enumerate(raw_edges):
            if not isinstance(raw_edge, Mapping):
                raise GraphValidationError(f"Edge at index {index} must be an object")
            source = raw_edge.get("source")
            target = raw_edge.get("target")
            if source not in nodes or target not in nodes:
                raise GraphValidationError(
                    f"Edge at index {index} references unknown nodes: "
                    f"{source!r}, {target!r}"
                )
            if source == target:
                raise GraphValidationError(f"Self-loop is not allowed at node {source!r}")
            raw_distance = raw_edge.get("distance_m")
            if isinstance(raw_distance, bool):
                raise GraphValidationError(f"Edge {source!r}-{target!r} has invalid weight")
            try:
                distance_m = float(raw_distance)
            except (TypeError, ValueError) as exc:
                raise GraphValidationError(
                    f"Edge {source!r}-{target!r} has invalid weight"
                ) from exc
            if distance_m <= 0:
                raise GraphValidationError(
                    f"Edge {source!r}-{target!r} must have a positive distance"
                )
            pair = frozenset((source, target))
            if pair in seen_pairs:
                raise GraphValidationError(
                    f"Duplicate undirected edge: {source!r}-{target!r}"
                )
            seen_pairs.add(pair)
            edge = StoreEdge(source, target, distance_m)
            edges.append(edge)
            adjacency_lists[source].append((target, distance_m))
            adjacency_lists[target].append((source, distance_m))

        adjacency = {
            node_id: tuple(sorted(neighbors, key=lambda item: item[0]))
            for node_id, neighbors in adjacency_lists.items()
        }
        return cls(nodes, tuple(edges), adjacency)


def load_store_graph(path: str | Path = DEFAULT_STORE_GRAPH_PATH) -> StoreGraph:
    """Load and validate a store graph JSON file without mutating its data."""
    graph_path = Path(path)
    try:
        with graph_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise GraphValidationError(f"Unable to load store graph {graph_path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise GraphValidationError("Store graph JSON root must be an object")
    return StoreGraph.from_dict(data)
