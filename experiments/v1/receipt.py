from __future__ import annotations

from copy import deepcopy

import numpy as np

from experiments.v1.model import two_stage_step, validated_gate, validated_transition

ATOL = 1e-12
PRE = "pre_adaptation"
POST = "post_adaptation"
CANONICAL_STAGES = (PRE, POST)


def _as_list(values) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float)]


def _identity(size: int) -> np.ndarray:
    return np.eye(size, dtype=float)


def _is_identity(matrix: np.ndarray) -> bool:
    return np.allclose(matrix, _identity(matrix.shape[0]), rtol=0.0, atol=ATOL)


def claimed_stages(variant_transition, source_gate, target_gate) -> list[str]:
    V = validated_transition(variant_transition)
    W_source = validated_gate(source_gate, V.shape[0], "source_gate")
    W_target = validated_gate(target_gate, V.shape[0], "target_gate")
    stages = []
    if not _is_identity(W_source):
        stages.append(PRE)
    if not _is_identity(W_target):
        stages.append(POST)
    return stages


def build_step_receipt(
    *,
    case_id: str,
    fixture_id: str,
    source_revision: str,
    state,
    variant_transition,
    source_gate,
    target_gate,
    transmission_scale: float = 1.0,
    graph_binding: str = "local",
    horizon: int = 1,
    step: int = 0,
    numeric_policy: str = "float64-atol-1e-12",
    intervention: str | None = None,
) -> dict:
    V = validated_transition(variant_transition)
    W_source = validated_gate(source_gate, V.shape[0], "source_gate")
    W_target = validated_gate(target_gate, V.shape[0], "target_gate")
    witnesses = two_stage_step(state, V, W_source, W_target)
    return {
        "schema_version": 1,
        "experiment_id": "deterministic-v1-two-stage",
        "case_id": case_id,
        "fixture_id": fixture_id,
        "source_revision": source_revision,
        "scientific_authority": "NONE",
        "input_state": _as_list(state),
        "variant_transition": V.tolist(),
        "source_gate": W_source.tolist(),
        "target_gate": W_target.tolist(),
        "graph_binding": graph_binding,
        "transmission_scale": float(transmission_scale),
        "node_count": 1,
        "variant_count": int(V.shape[0]),
        "horizon": int(horizon),
        "step": int(step),
        "numeric_policy": numeric_policy,
        "intervention": intervention,
        "claimed_stages": claimed_stages(V, W_source, W_target),
        "source_ready": _as_list(witnesses["source_ready"]),
        "adapted": _as_list(witnesses["adapted"]),
        "persistent": _as_list(witnesses["persistent"]),
        "next_state": _as_list(witnesses["next_state"]),
    }


def build_identity_control(receipt: dict, stage: str) -> dict:
    if stage not in CANONICAL_STAGES:
        raise ValueError("unknown stage")
    clone = deepcopy(receipt)
    V = np.asarray(clone["variant_transition"], dtype=float)
    identity = _identity(V.shape[0]).tolist()
    if stage == PRE:
        clone["source_gate"] = identity
    else:
        clone["target_gate"] = identity
    clone["intervention"] = f"identity:{stage}"
    witnesses = two_stage_step(
        clone["input_state"],
        clone["variant_transition"],
        clone["source_gate"],
        clone["target_gate"],
    )
    clone["claimed_stages"] = claimed_stages(
        clone["variant_transition"], clone["source_gate"], clone["target_gate"]
    )
    for name in ("source_ready", "adapted", "persistent", "next_state"):
        clone[name] = _as_list(witnesses[name])
    return clone


def _same_vector(left, right) -> bool:
    try:
        a = np.asarray(left, dtype=float)
        b = np.asarray(right, dtype=float)
    except (TypeError, ValueError):
        return False
    return (
        a.shape == b.shape
        and a.ndim == 1
        and np.all(np.isfinite(a))
        and np.all(np.isfinite(b))
        and np.all(a >= 0)
        and np.all(b >= 0)
        and np.allclose(a, b, rtol=0.0, atol=ATOL)
    )


BASE_RECEIPT_FIELDS = {
    "schema_version", "experiment_id", "case_id", "fixture_id", "source_revision",
    "scientific_authority", "input_state", "variant_transition", "source_gate",
    "target_gate", "graph_binding", "transmission_scale", "node_count",
    "variant_count", "horizon", "step", "numeric_policy", "claimed_stages",
    "next_state",
}
STAGE_WITNESS_FIELDS = ("source_ready", "adapted", "persistent")


def _validated_receipt_core(receipt: dict):
    if not isinstance(receipt, dict) or not BASE_RECEIPT_FIELDS.issubset(receipt):
        return None
    if receipt.get("scientific_authority") != "NONE":
        return None
    try:
        V = validated_transition(receipt["variant_transition"])
        W_source = validated_gate(receipt["source_gate"], V.shape[0], "source_gate")
        W_target = validated_gate(receipt["target_gate"], V.shape[0], "target_gate")
        expected = two_stage_step(receipt["input_state"], V, W_source, W_target)
    except (TypeError, ValueError):
        return None
    if receipt.get("claimed_stages") != claimed_stages(V, W_source, W_target):
        return None
    if not _same_vector(receipt.get("next_state"), expected["next_state"]):
        return None
    return expected


def _valid_receipt_shape(receipt: dict) -> bool:
    expected = _validated_receipt_core(receipt)
    if expected is None or any(name not in receipt for name in STAGE_WITNESS_FIELDS):
        return False
    return all(
        _same_vector(receipt.get(name), expected[name])
        for name in STAGE_WITNESS_FIELDS
    )


def _matched_control(test: dict, control: dict, stage: str) -> bool:
    if not _valid_receipt_shape(control):
        return False
    if control.get("intervention") != f"identity:{stage}":
        return False
    same_fields = (
        "experiment_id", "fixture_id", "source_revision", "input_state",
        "variant_transition", "graph_binding", "transmission_scale", "node_count",
        "variant_count", "horizon", "step", "numeric_policy",
    )
    if any(control.get(field) != test.get(field) for field in same_fields):
        return False
    if stage == PRE:
        return (
            control.get("target_gate") == test.get("target_gate")
            and _is_identity(np.asarray(control.get("source_gate"), dtype=float))
        )
    return (
        control.get("source_gate") == test.get("source_gate")
        and _is_identity(np.asarray(control.get("target_gate"), dtype=float))
    )


def evaluate_stage_attribution(receipt: dict, controls: dict | None) -> dict:
    expected = _validated_receipt_core(receipt)
    if expected is None:
        return {"stage_attribution": "FAIL", "reason": "invalid_receipt"}
    missing_witnesses = [name for name in STAGE_WITNESS_FIELDS if name not in receipt]
    if missing_witnesses:
        return {
            "stage_attribution": "UNKNOWN",
            "reason": "stage_witness_missing",
            "missing": missing_witnesses,
            "scientific_authority": "NONE",
        }
    if any(not _same_vector(receipt.get(name), expected[name]) for name in STAGE_WITNESS_FIELDS):
        return {"stage_attribution": "FAIL", "reason": "invalid_receipt"}
    stages = receipt["claimed_stages"]
    if not stages:
        return {"stage_attribution": "UNKNOWN", "reason": "no_nonidentity_stage"}
    if controls is None:
        return {"stage_attribution": "UNKNOWN", "reason": "identity_control_missing"}
    if not isinstance(controls, dict):
        return {"stage_attribution": "FAIL", "reason": "invalid_control_set"}

    per_stage = {}
    for stage in stages:
        control = controls.get(stage)
        if control is None:
            per_stage[stage] = "UNKNOWN"
            continue
        if not _matched_control(receipt, control, stage):
            return {"stage_attribution": "FAIL", "reason": f"control_mismatch:{stage}"}
        if stage == PRE:
            stage_input = receipt["input_state"]
            witness_name = "source_ready"
        else:
            stage_input = receipt["adapted"]
            witness_name = "persistent"
        if np.allclose(np.asarray(stage_input, dtype=float), 0.0, rtol=0.0, atol=ATOL):
            per_stage[stage] = "UNKNOWN"
        elif _same_vector(receipt[witness_name], control[witness_name]):
            per_stage[stage] = "UNKNOWN"
        else:
            per_stage[stage] = "PASS"

    aggregate = "PASS" if all(per_stage.get(stage) == "PASS" for stage in stages) else "UNKNOWN"
    return {
        "stage_attribution": aggregate,
        "per_stage": per_stage,
        "scientific_authority": "NONE",
    }
