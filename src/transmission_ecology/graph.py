from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    weight: float


@dataclass(frozen=True)
class GraphFixture:
    schema_version: int
    graph_id: str
    nodes: tuple[str, ...]
    edges: tuple[Edge, ...]


def _validate_node_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("node ids must be non-empty strings")
    return value


def load_graph(path: Path | str) -> GraphFixture:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported graph schema_version")
    graph_id = payload.get("graph_id")
    if not isinstance(graph_id, str) or not graph_id:
        raise ValueError("graph_id must be a non-empty string")
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("nodes must be a non-empty list")
    nodes = tuple(_validate_node_id(n) for n in raw_nodes)
    if len(set(nodes)) != len(nodes):
        raise ValueError("duplicate node id")
    node_set = set(nodes)
    raw_edges = payload.get("edges")
    if not isinstance(raw_edges, list):
        raise ValueError("edges must be a list")
    edges = []
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            raise ValueError(f"edge {index} must be an object")
        source = raw.get("source")
        target = raw.get("target")
        if source not in node_set or target not in node_set:
            raise ValueError(f"edge {index} references unknown node")
        weight = raw.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError(f"edge {index} weight must be numeric")
        weight = float(weight)
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError(f"edge {index} weight must be positive and finite")
        edges.append(Edge(source=source, target=target, weight=weight))
    return GraphFixture(
        schema_version=1,
        graph_id=graph_id,
        nodes=nodes,
        edges=tuple(edges),
    )


def adjacency_matrix(graph: GraphFixture) -> np.ndarray:
    index = {node: i for i, node in enumerate(graph.nodes)}
    matrix = np.zeros((len(graph.nodes), len(graph.nodes)), dtype=float)
    for edge in graph.edges:
        matrix[index[edge.target], index[edge.source]] += edge.weight
    return matrix


def weak_component_count(graph: GraphFixture) -> int:
    neighbors = {node: set() for node in graph.nodes}
    for edge in graph.edges:
        neighbors[edge.source].add(edge.target)
        neighbors[edge.target].add(edge.source)
    remaining = set(graph.nodes)
    count = 0
    while remaining:
        count += 1
        start = min(remaining)
        queue = deque([start])
        remaining.remove(start)
        while queue:
            node = queue.popleft()
            for neighbor in sorted(neighbors[node]):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
    return count


def cycle_rank_beta1(graph: GraphFixture) -> int:
    return len(graph.edges) - len(graph.nodes) + weak_component_count(graph)
