from __future__ import annotations

import math

import numpy as np

from transmission_ecology.graph import GraphFixture, adjacency_matrix


def validate_variants(params: dict) -> tuple[str, ...]:
    variants = params.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("variants must be a non-empty list")
    if any(not isinstance(v, str) or not v for v in variants):
        raise ValueError("variant ids must be non-empty strings")
    if len(set(variants)) != len(variants):
        raise ValueError("variant ids must be unique")
    return tuple(variants)


def _finite_nonnegative_scalar(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def kron_operator(
    graph_adjacency,
    variant_transition,
    scale,
    variant_fitness=None,
) -> np.ndarray:
    A = np.asarray(graph_adjacency, dtype=float)
    V = np.asarray(variant_transition, dtype=float)
    if A.ndim != 2 or A.shape[0] == 0 or A.shape[0] != A.shape[1]:
        raise ValueError("graph adjacency must be a non-empty square matrix")
    if V.ndim != 2 or V.shape[0] == 0 or V.shape[0] != V.shape[1]:
        raise ValueError("variant transition must be a non-empty square matrix")
    if not np.all(np.isfinite(A)) or np.any(A < 0):
        raise ValueError("graph adjacency must be finite and nonnegative")
    if not np.all(np.isfinite(V)) or np.any(V < 0):
        raise ValueError("variant transition must be finite and nonnegative")
    if not np.allclose(V.sum(axis=0), np.ones(V.shape[1]), rtol=0.0, atol=1e-12):
        raise ValueError("variant transition columns must sum to one")
    scale = _finite_nonnegative_scalar(scale, "scale")
    if variant_fitness is not None:
        fitness = np.asarray(variant_fitness, dtype=float)
        if fitness.shape != (V.shape[0],):
            raise ValueError("variant_fitness shape must match variant count")
        if not np.all(np.isfinite(fitness)) or np.any(fitness < 0):
            raise ValueError("variant_fitness must be finite and nonnegative")
        V = np.diag(fitness) @ V
    return np.kron(A, V) * scale


def build_from_graph(
    graph: GraphFixture,
    params: dict,
    *,
    effective_scale: float,
    variant_fitness=None,
) -> np.ndarray:
    variants = validate_variants(params)
    V = np.asarray(params.get("variant_transition"), dtype=float)
    if V.shape != (len(variants), len(variants)):
        raise ValueError("variant_transition shape must match variants")
    return kron_operator(
        adjacency_matrix(graph),
        V,
        scale=effective_scale,
        variant_fitness=variant_fitness,
    )
