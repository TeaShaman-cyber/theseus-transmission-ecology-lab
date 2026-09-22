from __future__ import annotations

import math

import numpy as np


def _as_nonnegative_state(state, *, node_count: int, variant_count: int) -> np.ndarray:
    if isinstance(node_count, bool) or not isinstance(node_count, int) or node_count <= 0:
        raise ValueError("node_count must be a positive integer")
    if isinstance(variant_count, bool) or not isinstance(variant_count, int) or variant_count <= 0:
        raise ValueError("variant_count must be a positive integer")
    arr = np.asarray(state, dtype=float)
    expected = node_count * variant_count
    if arr.ndim != 1 or arr.size != expected:
        raise ValueError(f"state shape must be ({expected},), got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("state entries must be finite")
    if np.any(arr < 0):
        raise ValueError("state entries must be nonnegative")
    return arr


def _variant_masses(state, node_count: int, variant_count: int) -> np.ndarray:
    arr = _as_nonnegative_state(state, node_count=node_count, variant_count=variant_count)
    return arr.reshape(node_count, variant_count).sum(axis=0)


def spectral_radius(K) -> float:
    matrix = np.asarray(K, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("K must be a non-empty square matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("K entries must be finite")
    values = np.linalg.eigvals(matrix)
    return float(np.max(np.abs(values)))


def variant_shannon_entropy(state, node_count: int, variant_count: int) -> float:
    masses = _variant_masses(state, node_count, variant_count)
    total = float(masses.sum())
    if total == 0.0:
        return 0.0
    probabilities = masses[masses > 0.0] / total
    return float(-sum(float(p) * math.log(float(p)) for p in probabilities))


def dominant_variant_share(state, node_count: int, variant_count: int) -> float:
    masses = _variant_masses(state, node_count, variant_count)
    total = float(masses.sum())
    if total == 0.0:
        return 0.0
    return float(masses.max() / total)


def surviving_variant_count(state, node_count: int, variant_count: int, *, tolerance: float = 1e-12) -> int:
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    masses = _variant_masses(state, node_count, variant_count)
    return int(np.count_nonzero(masses > tolerance))


def perturbation_recovery_ratio(baseline_final, perturbed_final) -> float:
    baseline = np.asarray(baseline_final, dtype=float)
    perturbed = np.asarray(perturbed_final, dtype=float)
    if baseline.ndim != 1 or perturbed.ndim != 1 or baseline.shape != perturbed.shape:
        raise ValueError("baseline and perturbed states must be same-shape vectors")
    if not np.all(np.isfinite(baseline)) or not np.all(np.isfinite(perturbed)):
        raise ValueError("recovery states must be finite")
    if np.any(baseline < 0) or np.any(perturbed < 0):
        raise ValueError("recovery states must be nonnegative")
    baseline_total = float(baseline.sum())
    if baseline_total == 0.0:
        return 0.0
    ratio = float(perturbed.sum()) / baseline_total
    return max(0.0, min(1.0, ratio))


def time_to_extinction_or_horizon(states, *, tolerance: float = 1e-12) -> int:
    if not states:
        raise ValueError("states must be non-empty")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    for index, state in enumerate(states):
        arr = np.asarray(state, dtype=float)
        if arr.ndim != 1 or not np.all(np.isfinite(arr)) or np.any(arr < 0):
            raise ValueError("states must be finite nonnegative vectors")
        if float(arr.sum()) <= tolerance:
            return index
    return len(states) - 1


def summarize_run(
    K,
    states,
    *,
    node_count: int,
    variant_count: int,
    cycle_rank_beta1_value: int,
    perturbed_final,
) -> dict[str, object]:
    if not states:
        raise ValueError("states must be non-empty")
    rho = spectral_radius(K)
    final = states[-1]
    totals = [float(np.asarray(state, dtype=float).sum()) for state in states]
    return {
        "spectral_radius": rho,
        "subcritical_or_supercritical": "subcritical" if rho < 1.0 else "supercritical" if rho > 1.0 else "critical",
        "cycle_rank_beta1": int(cycle_rank_beta1_value),
        "total_mass_by_step": totals,
        "variant_shannon_entropy": variant_shannon_entropy(final, node_count, variant_count),
        "surviving_variant_count": surviving_variant_count(final, node_count, variant_count),
        "dominant_variant_share": dominant_variant_share(final, node_count, variant_count),
        "time_to_extinction_or_horizon": time_to_extinction_or_horizon(states),
        "perturbation_recovery_ratio": perturbation_recovery_ratio(final, perturbed_final),
    }
