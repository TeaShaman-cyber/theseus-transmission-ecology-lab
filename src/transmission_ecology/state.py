from __future__ import annotations

import numpy as np


def validate_operator(K, state_size: int) -> np.ndarray:
    if isinstance(state_size, bool) or not isinstance(state_size, int) or state_size <= 0:
        raise ValueError("state_size must be a positive integer")
    matrix = np.asarray(K, dtype=float)
    if matrix.ndim != 2 or matrix.shape != (state_size, state_size):
        raise ValueError(f"operator shape must be {(state_size, state_size)}, got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("operator entries must be finite")
    if np.any(matrix < 0):
        raise ValueError("operator entries must be nonnegative")
    return matrix


def simulate(K, x0, horizon: int) -> list[np.ndarray]:
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 0:
        raise ValueError("horizon must be a nonnegative integer")
    state = np.asarray(x0, dtype=float)
    if state.ndim != 1 or state.size == 0:
        raise ValueError("initial state must be a non-empty vector")
    if not np.all(np.isfinite(state)):
        raise ValueError("initial state must be finite")
    if np.any(state < 0):
        raise ValueError("initial state must be nonnegative")
    matrix = validate_operator(K, state_size=state.size)
    states = [state.copy()]
    for _ in range(horizon):
        state = matrix @ state
        states.append(state.copy())
    return states
