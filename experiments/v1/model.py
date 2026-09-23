from __future__ import annotations

import math

import numpy as np


def _finite_nonnegative_scalar(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def validated_transition(variant_transition) -> np.ndarray:
    V = np.asarray(variant_transition, dtype=float)
    if V.ndim != 2 or V.shape[0] == 0 or V.shape[0] != V.shape[1]:
        raise ValueError("variant transition must be a non-empty square matrix")
    if not np.all(np.isfinite(V)) or np.any(V < 0):
        raise ValueError("variant transition must be finite and nonnegative")
    if not np.allclose(V.sum(axis=0), np.ones(V.shape[1]), rtol=0.0, atol=1e-12):
        raise ValueError("variant transition columns must sum to one")
    return V


def validated_gate(gate, variant_count: int, name: str) -> np.ndarray:
    W = np.asarray(gate, dtype=float)
    if W.shape != (variant_count, variant_count):
        raise ValueError(f"{name} shape must match variant count")
    if not np.all(np.isfinite(W)) or np.any(W < 0):
        raise ValueError(f"{name} must be finite and nonnegative")
    if not np.array_equal(W, np.diag(np.diag(W))):
        raise ValueError(f"{name} must be diagonal")
    return W


def two_stage_variant_operator(variant_transition, source_gate, target_gate) -> np.ndarray:
    V = validated_transition(variant_transition)
    W_source = validated_gate(source_gate, V.shape[0], "source_gate")
    W_target = validated_gate(target_gate, V.shape[0], "target_gate")
    return W_target @ V @ W_source


def two_stage_step(state, variant_transition, source_gate, target_gate) -> dict[str, np.ndarray]:
    V = validated_transition(variant_transition)
    W_source = validated_gate(source_gate, V.shape[0], "source_gate")
    W_target = validated_gate(target_gate, V.shape[0], "target_gate")
    x = np.asarray(state, dtype=float)
    if x.shape != (V.shape[0],):
        raise ValueError("state shape must match variant count")
    if not np.all(np.isfinite(x)) or np.any(x < 0):
        raise ValueError("state must be finite and nonnegative")
    source_ready = W_source @ x
    adapted = V @ source_ready
    persistent = W_target @ adapted
    return {
        "source_ready": source_ready,
        "adapted": adapted,
        "persistent": persistent,
        "next_state": persistent.copy(),
    }


def two_stage_kron_operator(
    graph_adjacency,
    variant_transition,
    source_gate,
    target_gate,
    *,
    scale,
) -> np.ndarray:
    A = np.asarray(graph_adjacency, dtype=float)
    if A.ndim != 2 or A.shape[0] == 0 or A.shape[0] != A.shape[1]:
        raise ValueError("graph adjacency must be a non-empty square matrix")
    if not np.all(np.isfinite(A)) or np.any(A < 0):
        raise ValueError("graph adjacency must be finite and nonnegative")
    scale = _finite_nonnegative_scalar(scale, "scale")
    B = two_stage_variant_operator(variant_transition, source_gate, target_gate)
    return np.kron(A, B) * scale
