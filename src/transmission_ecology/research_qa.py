from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

from transmission_ecology.metrics import SURVIVAL_TOLERANCE
from transmission_ecology.strict_json import load_json, loads_strict
from transmission_ecology.provenance import (
    EXPERIMENT_SURFACE_PATHS,
    working_tree_paths_dirty,
)

REQUIRED_RUNS = ("virus", "meme", "agent")
RESEARCH_EVIDENCE_PATHS = (
    "receipts/reference",
    "receipts/independent/wolfram-v0.json",
)
RESEARCH_QA_SURFACE_PATHS = (
    "src/transmission_ecology/research_qa.py",
    "tools/research/check",
)


def _status(status: str, reason: str, **extra):
    payload = {"contract_status": status, "authority": "NONE", "reason": reason}
    payload.update(extra)
    return payload


def _validate_receipt_policy(receipt: dict, receipt_contract: dict) -> bool:
    return (
        receipt.get("schema_version") == receipt_contract.get("schema_version")
        and receipt.get("numeric_policy", {}).get("float_significant_digits")
        == receipt_contract.get("float_significant_digits")
    )


def _finite_nonnegative_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _nonnegative_int(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _significant_rounding_half_step(
    value: float, digits: int, *, bounded_unit_interval_lower: bool = False
) -> float:
    if value <= 0.0:
        return 0.0
    if bounded_unit_interval_lower and value == 1.0:
        exponent = -1
    else:
        exponent = math.floor(math.log10(abs(value)))
    return 0.5 * (10.0 ** (exponent - digits + 1))


def _validate_metric_values(
    metrics: dict,
    declared_metrics: list[str],
    *,
    expected_cycle_rank_beta1: int | None,
    expected_variant_count: int,
    expected_horizon: int,
    expected_initial_mass: float,
    expected_float_digits: int,
    expected_perturbation_recovery_ratio: float,
) -> list[str]:
    mismatches: list[str] = []

    horizon = expected_horizon
    horizon_valid = _nonnegative_int(horizon)

    validators = {
        "spectral_radius",
        "cycle_rank_beta1",
        "total_mass_by_step",
        "variant_shannon_entropy",
        "surviving_variant_count",
        "dominant_variant_share",
        "time_to_extinction_or_horizon",
        "perturbation_recovery_ratio",
    }

    for metric in declared_metrics:
        if metric not in validators:
            mismatches.append(metric)
            continue
        if metric not in metrics:
            mismatches.append(metric)
            continue

        value = metrics.get(metric)
        valid = False

        if metric in ("spectral_radius", "variant_shannon_entropy"):
            valid = _finite_nonnegative_number(value)
        elif metric == "cycle_rank_beta1":
            valid = _nonnegative_int(value)
            if valid and expected_cycle_rank_beta1 is not None:
                valid = value == expected_cycle_rank_beta1
        elif metric == "total_mass_by_step":
            valid = (
                horizon_valid
                and isinstance(value, list)
                and len(value) == horizon + 1
                and all(_finite_nonnegative_number(item) for item in value)
            )
        elif metric == "surviving_variant_count":
            valid = _nonnegative_int(value) and value <= expected_variant_count
        elif metric in ("dominant_variant_share", "perturbation_recovery_ratio"):
            valid = _finite_nonnegative_number(value) and float(value) <= 1.0
        elif metric == "time_to_extinction_or_horizon":
            valid = horizon_valid and _nonnegative_int(value) and value <= horizon

        if not valid:
            mismatches.append(metric)

    mass_trace = metrics.get("total_mass_by_step")
    extinction = metrics.get("time_to_extinction_or_horizon")
    if (
        horizon_valid
        and isinstance(mass_trace, list)
        and len(mass_trace) == horizon + 1
        and all(_finite_nonnegative_number(item) for item in mass_trace)
        and _nonnegative_int(extinction)
    ):
        if not math.isclose(
            float(mass_trace[0]),
            float(expected_initial_mass),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            mismatches.append("total_mass_by_step")
        expected_extinction = horizon
        for index, mass in enumerate(mass_trace):
            if float(mass) <= SURVIVAL_TOLERANCE:
                expected_extinction = index
                break
        if extinction != expected_extinction:
            mismatches.append("time_to_extinction_or_horizon")

        dominant = metrics.get("dominant_variant_share")
        surviving = metrics.get("surviving_variant_count")
        entropy = metrics.get("variant_shannon_entropy")
        final_mass = float(mass_trace[-1])
        if (
            _finite_nonnegative_number(dominant)
            and _nonnegative_int(surviving)
            and _finite_nonnegative_number(entropy)
        ):
            pmax = float(dominant)
            entropy_value = float(entropy)
            compare_tol = 1e-10

            if final_mass == 0.0:
                if pmax != 0.0:
                    mismatches.append("dominant_variant_share")
                if surviving != 0:
                    mismatches.append("surviving_variant_count")
                if entropy_value != 0.0:
                    mismatches.append("variant_shannon_entropy")
            else:
                if surviving == 0:
                    if final_mass > expected_variant_count * SURVIVAL_TOLERANCE:
                        mismatches.append("surviving_variant_count")
                    if pmax * final_mass > SURVIVAL_TOLERANCE:
                        mismatches.append("surviving_variant_count")
                else:
                    if final_mass <= SURVIVAL_TOLERANCE:
                        mismatches.append("surviving_variant_count")
                    nonsurvivor_budget = (
                        expected_variant_count - surviving
                    ) * SURVIVAL_TOLERANCE
                    share_rounding = _significant_rounding_half_step(
                        pmax,
                        expected_float_digits,
                        bounded_unit_interval_lower=True,
                    )
                    mass_rounding = _significant_rounding_half_step(
                        final_mass, expected_float_digits
                    )
                    pmax_upper = min(1.0, pmax + share_rounding)
                    mass_lower = max(0.0, final_mass - mass_rounding)
                    if mass_lower > 0.0:
                        survivor_mass_floor = max(
                            0.0, mass_lower - nonsurvivor_budget
                        )
                        survivor_share_floor = (
                            survivor_mass_floor / (surviving * mass_lower)
                        )
                        if (
                            math.nextafter(pmax_upper, math.inf)
                            < survivor_share_floor
                        ):
                            mismatches.append("dominant_variant_share")

                    if surviving > 1:
                        pmax_lower = max(0.0, pmax - share_rounding)
                        mass_upper = final_mass + mass_rounding
                        max_non_dominant_mass = (1.0 - pmax_lower) * mass_upper
                        required_non_dominant_mass = (
                            surviving - 1
                        ) * SURVIVAL_TOLERANCE
                        if max_non_dominant_mass <= required_non_dominant_mass:
                            mismatches.append("dominant_variant_share")

                if pmax <= 0.0:
                    mismatches.append("dominant_variant_share")
                else:
                    inverse = 1.0 / pmax
                    full_bins = min(
                        expected_variant_count,
                        max(1, int(math.floor(inverse + 1e-12))),
                    )
                    remainder = max(0.0, 1.0 - full_bins * pmax)
                    entropy_min = -full_bins * pmax * math.log(pmax)
                    if remainder > 0.0:
                        entropy_min -= remainder * math.log(remainder)

                    if expected_variant_count == 1:
                        entropy_max = 0.0
                    elif pmax >= 1.0:
                        entropy_max = 0.0
                    else:
                        remainder_each = (1.0 - pmax) / (
                            expected_variant_count - 1
                        )
                        entropy_max = -pmax * math.log(pmax)
                        if remainder_each > 0.0:
                            entropy_max -= (
                                expected_variant_count - 1
                            ) * remainder_each * math.log(remainder_each)

                    if entropy_value + compare_tol < entropy_min:
                        mismatches.append("variant_shannon_entropy")
                    if entropy_value > entropy_max + compare_tol:
                        mismatches.append("variant_shannon_entropy")

    recovery_ratio = metrics.get("perturbation_recovery_ratio")
    if (
        _finite_nonnegative_number(recovery_ratio)
        and _finite_nonnegative_number(expected_perturbation_recovery_ratio)
    ):
        observed = float(recovery_ratio)
        expected = float(expected_perturbation_recovery_ratio)
        expected_rounded = float(format(expected, f".{expected_float_digits}g"))
        interval = (
            _significant_rounding_half_step(observed, expected_float_digits)
            + _significant_rounding_half_step(expected_rounded, expected_float_digits)
            + math.ulp(expected_rounded if expected_rounded != 0.0 else 1.0)
        )
        if abs(observed - expected_rounded) > interval:
            mismatches.append("perturbation_recovery_ratio")

    rho = metrics.get("spectral_radius")
    regime = metrics.get("subcritical_or_supercritical")
    if _finite_nonnegative_number(rho) and regime is not None:
        expected_regime = (
            "subcritical" if float(rho) < 1.0
            else "supercritical" if float(rho) > 1.0
            else "critical"
        )
        if regime != expected_regime:
            mismatches.append("subcritical_or_supercritical")

    return mismatches


def evaluate_research_contract(
    contract,
    run_receipts,
    control_receipt,
    witness,
    *,
    source_commit,
    evidence_bindings,
):
    required = (
        "experiment_id",
        "question",
        "hypothesis",
        "falsifiers",
        "declared_metrics",
        "required_controls",
        "limitations",
        "independent_witness",
        "receipt_contract",
        "metric_semantics",
    )
    missing = [key for key in required if not contract.get(key)]
    if missing:
        return _status("FAIL", "missing_contract_fields", missing=missing)

    if (
        not isinstance(source_commit, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source_commit) is None
    ):
        return _status("FAIL", "invalid_source_commit")

    metadata_mismatches = []
    if (
        not isinstance(contract.get("experiment_id"), str)
        or not contract.get("experiment_id").strip()
    ):
        metadata_mismatches.append("experiment_id")
    for field in ("question", "hypothesis"):
        if not isinstance(contract.get(field), str) or not contract.get(field).strip():
            metadata_mismatches.append(field)
    for field in ("falsifiers", "limitations"):
        values = contract.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(item, str) or not item.strip() for item in values)
        ):
            metadata_mismatches.append(field)
    if metadata_mismatches:
        return _status(
            "FAIL",
            "invalid_contract_metadata",
            mismatched=sorted(metadata_mismatches),
        )

    absent = [name for name in REQUIRED_RUNS if name not in run_receipts]
    if absent:
        return _status("UNKNOWN", "missing_run_receipts", missing=absent)

    if any(r.get("source_commit") != source_commit for r in run_receipts.values()):
        return _status("FAIL", "source_commit_mismatch")

    metric_semantics = contract.get("metric_semantics")
    if not isinstance(metric_semantics, dict):
        return _status(
            "FAIL",
            "metric_semantics_mismatch",
            mismatched=["metric_semantics"],
        )
    declared_survival_tolerance = metric_semantics.get("survival_tolerance")
    if (
        not _finite_nonnegative_number(declared_survival_tolerance)
        or float(declared_survival_tolerance) <= 0.0
        or float(declared_survival_tolerance) != SURVIVAL_TOLERANCE
    ):
        return _status(
            "FAIL",
            "metric_semantics_mismatch",
            mismatched=["survival_tolerance"],
        )

    receipt_contract = contract.get("receipt_contract", {})
    expected_schema = receipt_contract.get("schema_version")
    expected_digits = receipt_contract.get("float_significant_digits")
    if (
        isinstance(expected_schema, bool)
        or not isinstance(expected_schema, int)
        or expected_schema <= 0
        or isinstance(expected_digits, bool)
        or not isinstance(expected_digits, int)
        or expected_digits <= 0
    ):
        return _status("FAIL", "invalid_receipt_contract")

    mismatched_policy = [
        name
        for name, receipt in run_receipts.items()
        if not _validate_receipt_policy(receipt, receipt_contract)
    ]
    if mismatched_policy:
        return _status(
            "FAIL",
            "receipt_contract_mismatch",
            mismatched=sorted(mismatched_policy),
        )

    if not isinstance(evidence_bindings, dict):
        return _status("FAIL", "invalid_evidence_binding_contract")
    expected_runs = evidence_bindings.get("runs")
    expected_control = evidence_bindings.get("control")
    expected_witness = evidence_bindings.get("witness")
    if (
        not isinstance(expected_runs, dict)
        or not isinstance(expected_control, dict)
        or not isinstance(expected_witness, dict)
    ):
        return _status("FAIL", "invalid_evidence_binding_contract")

    declared_metrics = contract.get("declared_metrics")
    if (
        not isinstance(declared_metrics, list)
        or not declared_metrics
        or any(not isinstance(name, str) or not name for name in declared_metrics)
    ):
        return _status("FAIL", "invalid_declared_metrics")

    witness_contract = contract.get("independent_witness")
    if not isinstance(witness_contract, dict):
        return _status("FAIL", "invalid_independent_witness_contract")
    required_witness_checks = witness_contract.get("required_checks")
    if not isinstance(required_witness_checks, dict) or not required_witness_checks:
        return _status("FAIL", "invalid_independent_witness_contract")
    expected_cycle_rank_beta1 = required_witness_checks.get("cycle_rank_beta1")
    if expected_cycle_rank_beta1 is not None and not _nonnegative_int(
        expected_cycle_rank_beta1
    ):
        return _status("FAIL", "invalid_independent_witness_contract")
    expected_backend = witness_contract.get("expected_backend")
    recipe_path = witness_contract.get("recipe_path")
    adapter_path = witness_contract.get("adapter_path")
    witness_schema_version = witness_contract.get("witness_schema_version")
    if (
        not isinstance(expected_backend, str)
        or not expected_backend
        or not isinstance(recipe_path, str)
        or not recipe_path
        or not isinstance(adapter_path, str)
        or not adapter_path
        or isinstance(witness_schema_version, bool)
        or not isinstance(witness_schema_version, int)
        or witness_schema_version <= 0
        or expected_witness.get("recipe_path") != recipe_path
        or expected_witness.get("adapter_path") != adapter_path
        or not isinstance(expected_witness.get("recipe_sha256"), str)
        or not expected_witness.get("recipe_sha256")
        or not isinstance(expected_witness.get("adapter_sha256"), str)
        or not expected_witness.get("adapter_sha256")
    ):
        return _status("FAIL", "invalid_independent_witness_contract")

    expected_horizon = expected_control.get("horizon")
    expected_initial_mass = expected_control.get("run_initial_mass")
    expected_seed_node = expected_control.get("run_seed_node")
    if (
        not _nonnegative_int(expected_horizon)
        or not _finite_nonnegative_number(expected_initial_mass)
        or float(expected_initial_mass) <= 0.0
        or not isinstance(expected_seed_node, str)
        or not expected_seed_node
    ):
        return _status("FAIL", "invalid_evidence_binding_contract")

    run_mismatches = []
    for name in REQUIRED_RUNS:
        receipt = run_receipts[name]
        expected = expected_runs.get(name)
        if not isinstance(expected, dict):
            return _status("FAIL", "invalid_evidence_binding_contract")

        if receipt.get("experiment_id") != contract.get("experiment_id"):
            run_mismatches.append(f"{name}.experiment_id")
        if receipt.get("substrate") != name:
            run_mismatches.append(f"{name}.substrate")
        if receipt.get("scientific_authority") != "NONE":
            run_mismatches.append(f"{name}.scientific_authority")

        for field in ("contract_sha256", "graph_sha256", "parameters_sha256"):
            if receipt.get(field) != expected.get(field):
                run_mismatches.append(f"{name}.{field}")

        expected_variant_count = expected.get("variant_count")
        expected_variants = expected.get("variants")
        expected_seed_variant = expected.get("seed_variant")
        if (
            isinstance(expected_variant_count, bool)
            or not isinstance(expected_variant_count, int)
            or expected_variant_count <= 0
            or not isinstance(expected_variants, list)
            or len(expected_variants) != expected_variant_count
            or any(not isinstance(item, str) or not item for item in expected_variants)
            or len(set(expected_variants)) != len(expected_variants)
            or not isinstance(expected_seed_variant, str)
            or expected_seed_variant not in expected_variants
            or not _finite_nonnegative_number(
                expected.get("perturbation_recovery_ratio")
            )
            or float(expected.get("perturbation_recovery_ratio")) > 1.0
        ):
            return _status("FAIL", "invalid_evidence_binding_contract")
        if receipt.get("horizon") != expected_horizon:
            run_mismatches.append(f"{name}.horizon")

        initial_condition = receipt.get("initial_condition")
        if not isinstance(initial_condition, dict):
            run_mismatches.append(f"{name}.initial_condition")
        else:
            if initial_condition.get("node") != expected_seed_node:
                run_mismatches.append(f"{name}.initial_condition.node")
            if initial_condition.get("variant") != expected_seed_variant:
                run_mismatches.append(f"{name}.initial_condition.variant")
            observed_initial_mass = initial_condition.get("mass")
            if (
                not _finite_nonnegative_number(observed_initial_mass)
                or not math.isclose(
                    float(observed_initial_mass),
                    float(expected_initial_mass),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
            ):
                run_mismatches.append(f"{name}.initial_condition.mass")

        metrics = receipt.get("metrics")
        if not isinstance(metrics, dict):
            run_mismatches.append(f"{name}.metrics")
        else:
            for metric in _validate_metric_values(
                metrics,
                declared_metrics,
                expected_cycle_rank_beta1=expected_cycle_rank_beta1,
                expected_variant_count=expected_variant_count,
                expected_horizon=expected_horizon,
                expected_initial_mass=float(expected_initial_mass),
                expected_float_digits=expected_digits,
                expected_perturbation_recovery_ratio=expected.get(
                    "perturbation_recovery_ratio"
                ),
            ):
                run_mismatches.append(f"{name}.metrics.{metric}")

        controls = receipt.get("controls")
        if not isinstance(controls, dict):
            run_mismatches.append(f"{name}.controls")
        else:
            if controls.get("all_passed") is not True:
                run_mismatches.append(f"{name}.controls.all_passed")
            if controls.get("control_receipt") != "v0-controls.json":
                run_mismatches.append(f"{name}.controls.control_receipt")

    if run_mismatches:
        return _status(
            "FAIL",
            "run_receipt_binding_mismatch",
            mismatched=sorted(set(run_mismatches)),
        )

    if control_receipt is None:
        return _status("UNKNOWN", "control_receipt_missing")
    if not isinstance(control_receipt, dict):
        return _status("FAIL", "control_receipt_binding_mismatch", mismatched=["receipt"])

    control_mismatches = []
    if not _validate_receipt_policy(control_receipt, receipt_contract):
        control_mismatches.append("receipt_contract")
    if control_receipt.get("experiment_id") != contract.get("experiment_id"):
        control_mismatches.append("experiment_id")
    if control_receipt.get("source_commit") != source_commit:
        control_mismatches.append("source_commit")
    if control_receipt.get("scientific_authority") != "NONE":
        control_mismatches.append("scientific_authority")
    for field in ("graph_sha256", "parameters_sha256"):
        if control_receipt.get(field) != expected_control.get(field):
            control_mismatches.append(field)

    expected_subcritical_radius = expected_control.get("subcritical_target_radius")
    expected_supercritical_radius = expected_control.get("supercritical_target_radius")
    expected_control_variant_count = expected_control.get("variant_count")
    expected_control_horizon = expected_control.get("horizon")
    if (
        not _finite_nonnegative_number(expected_subcritical_radius)
        or not _finite_nonnegative_number(expected_supercritical_radius)
        or not float(expected_subcritical_radius) < 1.0
        or not float(expected_supercritical_radius) > 1.0
        or isinstance(expected_control_variant_count, bool)
        or not isinstance(expected_control_variant_count, int)
        or expected_control_variant_count <= 0
        or not _nonnegative_int(expected_control_horizon)
    ):
        return _status("FAIL", "invalid_evidence_binding_contract")

    required_controls = contract.get("required_controls")
    if (
        not isinstance(required_controls, list)
        or not required_controls
        or any(not isinstance(name, str) or not name for name in required_controls)
    ):
        return _status("FAIL", "invalid_required_controls")

    observed_checks = control_receipt.get("checks")
    if not isinstance(observed_checks, dict):
        control_mismatches.append("checks")
        observed_checks = {}
    else:
        for name in required_controls:
            if name not in observed_checks:
                control_mismatches.append(f"checks.{name}")

    def numeric_fields(check_name: str, fields: tuple[str, ...]):
        check = observed_checks.get(check_name)
        if not isinstance(check, dict):
            if check_name in required_controls:
                control_mismatches.append(f"checks.{check_name}")
            return None
        values = {}
        for field in fields:
            value = check.get(field)
            if not _finite_nonnegative_number(value):
                control_mismatches.append(f"checks.{check_name}.{field}")
            else:
                values[field] = float(value)
        return values if len(values) == len(fields) else None

    low = numeric_fields(
        "subcritical",
        ("spectral_radius", "initial_mass", "final_mass"),
    )
    high = numeric_fields(
        "supercritical",
        ("spectral_radius", "initial_mass", "final_mass"),
    )

    radius_tolerance = 10.0 ** (-expected_digits)

    low_pass = False
    if low is not None:
        if not math.isclose(
            low["spectral_radius"],
            float(expected_subcritical_radius),
            rel_tol=radius_tolerance,
            abs_tol=radius_tolerance,
        ):
            control_mismatches.append(
                "checks.subcritical.spectral_radius_target"
            )
        if not low["spectral_radius"] < 1.0:
            control_mismatches.append(
                "checks.subcritical.spectral_radius_lt_1"
            )
        if not low["final_mass"] < low["initial_mass"]:
            control_mismatches.append("checks.subcritical.decay")
        low_pass = (
            low["spectral_radius"] < 1.0
            and low["final_mass"] < low["initial_mass"]
        )

    high_pass = False
    if high is not None:
        if not math.isclose(
            high["spectral_radius"],
            float(expected_supercritical_radius),
            rel_tol=radius_tolerance,
            abs_tol=radius_tolerance,
        ):
            control_mismatches.append(
                "checks.supercritical.spectral_radius_target"
            )
        if not high["spectral_radius"] > 1.0:
            control_mismatches.append(
                "checks.supercritical.spectral_radius_gt_1"
            )
        if not high["final_mass"] > high["initial_mass"]:
            control_mismatches.append("checks.supercritical.growth")
        high_pass = (
            high["spectral_radius"] > 1.0
            and high["final_mass"] > high["initial_mass"]
        )

    topology = observed_checks.get("topology_only")
    topology_pass = False
    if not isinstance(topology, dict):
        if "topology_only" in required_controls:
            control_mismatches.append("checks.topology_only")
    else:
        expected_graph = expected_control.get("graph_sha256")
        for field in (
            "graph_sha256",
            "subcritical_graph_sha256",
            "supercritical_graph_sha256",
        ):
            if topology.get(field) != expected_graph:
                control_mismatches.append(
                    f"checks.topology_only.{field}"
                )

        beta_fields = (
            "cycle_rank_beta1",
            "subcritical_cycle_rank_beta1",
            "supercritical_cycle_rank_beta1",
        )
        beta_values = {}
        for field in beta_fields:
            value = topology.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                control_mismatches.append(
                    f"checks.topology_only.{field}"
                )
            else:
                beta_values[field] = value

        beta_consistent = (
            len(beta_values) == len(beta_fields)
            and len(set(beta_values.values())) == 1
        )
        if not beta_consistent:
            control_mismatches.append(
                "checks.topology_only.beta1_consistency"
            )

        if beta_consistent:
            observed_beta = beta_values["cycle_rank_beta1"]
            if (
                expected_cycle_rank_beta1 is not None
                and observed_beta != expected_cycle_rank_beta1
            ):
                control_mismatches.append(
                    "checks.topology_only.cycle_rank_beta1_independent"
                )
            for name, receipt in run_receipts.items():
                if (
                    receipt.get("metrics", {}).get("cycle_rank_beta1")
                    != observed_beta
                ):
                    control_mismatches.append(
                        f"{name}.metrics.cycle_rank_beta1_consistency"
                    )

        same_topology = (
            topology.get("subcritical_graph_sha256") == expected_graph
            and topology.get("supercritical_graph_sha256")
            == expected_graph
            and beta_consistent
        )
        low_regime = "decay" if low_pass else "non_decay"
        high_regime = "growth" if high_pass else "non_growth"
        opposite_regimes = low_pass and high_pass

        if topology.get("subcritical_regime") != low_regime:
            control_mismatches.append(
                "checks.topology_only.subcritical_regime"
            )
        if topology.get("supercritical_regime") != high_regime:
            control_mismatches.append(
                "checks.topology_only.supercritical_regime"
            )
        if topology.get("same_topology") is not same_topology:
            control_mismatches.append(
                "checks.topology_only.same_topology"
            )
        if topology.get("opposite_regimes") is not opposite_regimes:
            control_mismatches.append(
                "checks.topology_only.opposite_regimes"
            )

        rejected = same_topology and opposite_regimes
        if (
            topology.get("topology_only_explanation_rejected")
            is not rejected
        ):
            control_mismatches.append(
                "checks.topology_only.topology_only_explanation_rejected"
            )
        topology_pass = rejected

    derived_all_passed = low_pass and high_pass and topology_pass
    if control_receipt.get("all_passed") is not derived_all_passed:
        control_mismatches.append("all_passed")
    if not derived_all_passed:
        control_mismatches.append("required_control_failed")

    if control_mismatches:
        return _status(
            "FAIL",
            "control_receipt_binding_mismatch",
            mismatched=sorted(set(control_mismatches)),
        )

    if witness_contract.get("required"):
        if witness is None:
            return _status("UNKNOWN", "independent_witness_missing")
        if witness.get("source_commit") != source_commit:
            return _status("FAIL", "witness_commit_mismatch")
        if witness.get("status") != "VERIFIED":
            return _status("DEGRADED", "witness_not_verified")

        expected_inputs = witness_contract.get("expected_inputs")
        required_checks = required_witness_checks
        if not isinstance(expected_inputs, dict) or not expected_inputs:
            return _status("FAIL", "invalid_independent_witness_contract")

        witness_mismatches = []
        if witness.get("experiment_id") != contract.get("experiment_id"):
            witness_mismatches.append("experiment_id")
        if witness.get("authority") != "NONE":
            witness_mismatches.append("authority")
        if witness.get("scientific_authority") != "NONE":
            witness_mismatches.append("scientific_authority")
        if witness.get("schema_version") != witness_schema_version:
            witness_mismatches.append("schema_version")
        if witness.get("backend") != expected_backend:
            witness_mismatches.append("backend")
        if witness.get("recipe_sha256") != expected_witness.get("recipe_sha256"):
            witness_mismatches.append("recipe_sha256")
        if witness.get("adapter_sha256") != expected_witness.get("adapter_sha256"):
            witness_mismatches.append("adapter_sha256")
        if witness.get("kind") != witness_contract.get("kind"):
            witness_mismatches.append("kind")

        observed_inputs = witness.get("inputs")
        if not isinstance(observed_inputs, dict):
            witness_mismatches.append("inputs")
        else:
            source_bound_inputs = {
                "graph_sha256": expected_control.get("graph_sha256"),
                "controls_sha256": expected_control.get(
                    "parameters_sha256"
                ),
            }
            for key, source_expected in source_bound_inputs.items():
                if expected_inputs.get(key) != source_expected:
                    witness_mismatches.append(
                        f"contract.expected_inputs.{key}.source_binding"
                    )
                if observed_inputs.get(key) != source_expected:
                    witness_mismatches.append(
                        f"inputs.{key}.source_binding"
                    )
            for key, expected in expected_inputs.items():
                if observed_inputs.get(key) != expected:
                    witness_mismatches.append(f"inputs.{key}")

        observed_checks = witness.get("checks")
        if not isinstance(observed_checks, dict):
            witness_mismatches.append("checks")
        else:
            for key, expected in required_checks.items():
                if observed_checks.get(key) != expected:
                    witness_mismatches.append(f"checks.{key}")

        witness_observed = witness.get("observed")
        if not isinstance(witness_observed, dict):
            witness_mismatches.append("observed")
        elif isinstance(observed_checks, dict):
            for key, expected in required_checks.items():
                if isinstance(expected, bool):
                    continue
                if key not in witness_observed:
                    witness_mismatches.append(f"observed.{key}")
                    continue
                observed_value = witness_observed.get(key)
                if not (
                    isinstance(observed_value, (int, float))
                    and not isinstance(observed_value, bool)
                    and math.isfinite(float(observed_value))
                ):
                    witness_mismatches.append(f"observed.{key}")
                    continue
                if observed_value != observed_checks.get(key):
                    witness_mismatches.append(f"observed.{key}")

            sub_rho = witness_observed.get("subcritical_spectral_radius")
            if _finite_nonnegative_number(sub_rho):
                if observed_checks.get("subcritical_below_one") is not (
                    float(sub_rho) < 1.0
                ):
                    witness_mismatches.append("observed.subcritical_below_one")
            elif "subcritical_below_one" in required_checks:
                witness_mismatches.append("observed.subcritical_spectral_radius")

            super_rho = witness_observed.get("supercritical_spectral_radius")
            if _finite_nonnegative_number(super_rho):
                if observed_checks.get("supercritical_above_one") is not (
                    float(super_rho) > 1.0
                ):
                    witness_mismatches.append("observed.supercritical_above_one")
            elif "supercritical_above_one" in required_checks:
                witness_mismatches.append("observed.supercritical_spectral_radius")

        if witness_mismatches:
            return _status(
                "FAIL",
                "witness_content_mismatch",
                mismatched=sorted(set(witness_mismatches)),
            )

    return {
        "contract_status": "PASS",
        "epistemic_state": "HYPOTHESIS",
        "scientific_disposition": "UNKNOWN_WITHIN_CURRENT_CONTRACT",
        "authority": "NONE",
        "source_commit": source_commit,
    }


def _load_json(path: Path):
    return load_json(path)


def _maybe_load(path: Path):
    if not path.is_file():
        return None
    return _load_json(path)


def _git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def _git_blob_sha256(root: Path, commit: str, relpath: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relpath}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def _git_blob_json(root: Path, commit: str, relpath: str) -> dict | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relpath}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        value = loads_strict(result.stdout.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _dense_matvec(matrix: list[list[float]], state: list[float]) -> list[float]:
    return [
        math.fsum(coefficient * value for coefficient, value in zip(row, state))
        for row in matrix
    ]


def _dense_simulate(
    matrix: list[list[float]], initial: list[float], horizon: int
) -> list[list[float]]:
    states = [list(initial)]
    state = list(initial)
    for _ in range(horizon):
        state = _dense_matvec(matrix, state)
        states.append(state)
    return states


def _source_expected_perturbation_ratio(
    graph_data: dict,
    parameters_data: dict,
    controls_data: dict,
    substrate: str,
) -> float | None:
    nodes = graph_data.get("nodes")
    edges = graph_data.get("edges")
    variants = parameters_data.get("variants")
    transition = parameters_data.get("variant_transition")
    horizon = controls_data.get("horizon")
    initial_mass = controls_data.get("run_initial_mass")
    seed_node = controls_data.get("run_seed_node")
    seed_variants = controls_data.get("run_seed_variants")
    if (
        not isinstance(nodes, list)
        or not nodes
        or any(not isinstance(node, str) or not node for node in nodes)
        or len(set(nodes)) != len(nodes)
        or not isinstance(edges, list)
        or not isinstance(variants, list)
        or not variants
        or any(not isinstance(variant, str) or not variant for variant in variants)
        or len(set(variants)) != len(variants)
        or not _nonnegative_int(horizon)
        or not _finite_nonnegative_number(initial_mass)
        or float(initial_mass) <= 0.0
        or not isinstance(seed_node, str)
        or seed_node not in nodes
        or not isinstance(seed_variants, dict)
        or not isinstance(seed_variants.get(substrate), str)
        or seed_variants.get(substrate) not in variants
    ):
        return None

    node_index = {node: index for index, node in enumerate(nodes)}
    node_count = len(nodes)
    variant_count = len(variants)
    adjacency = [[0.0 for _ in range(node_count)] for _ in range(node_count)]
    for edge in edges:
        if not isinstance(edge, dict):
            return None
        source = edge.get("source")
        target = edge.get("target")
        weight = edge.get("weight")
        if (
            source not in node_index
            or target not in node_index
            or not _finite_nonnegative_number(weight)
            or float(weight) <= 0.0
        ):
            return None
        adjacency[node_index[target]][node_index[source]] += float(weight)

    if (
        not isinstance(transition, list)
        or len(transition) != variant_count
        or any(not isinstance(row, list) or len(row) != variant_count for row in transition)
    ):
        return None
    variant_matrix: list[list[float]] = []
    for row in transition:
        converted = []
        for value in row:
            if not _finite_nonnegative_number(value):
                return None
            converted.append(float(value))
        variant_matrix.append(converted)
    for column in range(variant_count):
        if not math.isclose(
            math.fsum(variant_matrix[row][column] for row in range(variant_count)),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            return None

    transmission = parameters_data.get("transmission_scale")
    if not _finite_nonnegative_number(transmission):
        return None
    scale = float(transmission)
    if substrate == "virus":
        loss = parameters_data.get("recovery_loss", 0.0)
        if (
            not _finite_nonnegative_number(loss)
            or float(loss) > 1.0
        ):
            return None
        scale *= 1.0 - float(loss)
    elif substrate == "meme":
        retention = parameters_data.get("attention_retention", 1.0)
        if not _finite_nonnegative_number(retention):
            return None
        scale *= float(retention)
    elif substrate == "agent":
        weights = parameters_data.get("evaluator_weights")
        if (
            not isinstance(weights, list)
            or len(weights) != variant_count
            or any(not _finite_nonnegative_number(value) for value in weights)
        ):
            return None
        variant_matrix = [
            [float(weights[row]) * value for value in variant_matrix[row]]
            for row in range(variant_count)
        ]
    else:
        return None

    size = node_count * variant_count
    operator = [[0.0 for _ in range(size)] for _ in range(size)]
    for target_node in range(node_count):
        for source_node in range(node_count):
            graph_weight = adjacency[target_node][source_node]
            if graph_weight == 0.0:
                continue
            for target_variant in range(variant_count):
                target_index = target_node * variant_count + target_variant
                for source_variant in range(variant_count):
                    source_index = source_node * variant_count + source_variant
                    operator[target_index][source_index] = (
                        graph_weight
                        * variant_matrix[target_variant][source_variant]
                        * scale
                    )

    initial = [0.0 for _ in range(size)]
    seed_index = (
        node_index[seed_node] * variant_count
        + variants.index(seed_variants[substrate])
    )
    initial[seed_index] = float(initial_mass)
    baseline_states = _dense_simulate(operator, initial, horizon)
    midpoint = horizon // 2
    midpoint_state = list(baseline_states[midpoint])
    variant_masses = [
        math.fsum(
            midpoint_state[node * variant_count + variant]
            for node in range(node_count)
        )
        for variant in range(variant_count)
    ]
    dominant_variant = max(range(variant_count), key=variant_masses.__getitem__)
    for node in range(node_count):
        midpoint_state[node * variant_count + dominant_variant] = 0.0
    perturbed_states = _dense_simulate(
        operator, midpoint_state, horizon - midpoint
    )
    baseline_total = math.fsum(baseline_states[-1])
    if baseline_total == 0.0:
        return 0.0
    perturbed_total = math.fsum(perturbed_states[-1])
    ratio = perturbed_total / baseline_total
    if not math.isfinite(ratio):
        return None
    return max(0.0, min(1.0, ratio))


def _expected_evidence_bindings(root: Path, source_commit: str) -> dict | None:
    contract_sha256 = _git_blob_sha256(
        root, source_commit, "experiments/v0/contract.json"
    )
    contract_data = _git_blob_json(
        root, source_commit, "experiments/v0/contract.json"
    )
    graph_sha256 = _git_blob_sha256(
        root, source_commit, "experiments/v0/shared-graph.json"
    )
    graph_data = _git_blob_json(
        root, source_commit, "experiments/v0/shared-graph.json"
    )
    controls_sha256 = _git_blob_sha256(
        root, source_commit, "experiments/v0/controls.json"
    )
    controls_data = _git_blob_json(
        root, source_commit, "experiments/v0/controls.json"
    )
    if (
        None in (contract_sha256, graph_sha256, controls_sha256)
        or contract_data is None
        or graph_data is None
        or controls_data is None
    ):
        return None

    graph_nodes = graph_data.get("nodes")
    seed_node = controls_data.get("run_seed_node")
    seed_variants = controls_data.get("run_seed_variants")
    if (
        not isinstance(graph_nodes, list)
        or not graph_nodes
        or any(not isinstance(node, str) or not node for node in graph_nodes)
        or len(set(graph_nodes)) != len(graph_nodes)
        or not isinstance(seed_node, str)
        or seed_node not in graph_nodes
        or not isinstance(seed_variants, dict)
        or set(seed_variants) != set(REQUIRED_RUNS)
    ):
        return None

    witness_contract = contract_data.get("independent_witness")
    if not isinstance(witness_contract, dict):
        return None
    recipe_path = witness_contract.get("recipe_path")
    adapter_path = witness_contract.get("adapter_path")
    for witness_path in (recipe_path, adapter_path):
        if (
            not isinstance(witness_path, str)
            or not witness_path.startswith("experiments/v0/")
            or ".." in Path(witness_path).parts
        ):
            return None
    recipe_sha256 = _git_blob_sha256(root, source_commit, recipe_path)
    adapter_sha256 = _git_blob_sha256(root, source_commit, adapter_path)
    if recipe_sha256 is None or adapter_sha256 is None:
        return None

    runs = {}
    for name in REQUIRED_RUNS:
        parameters_path = f"experiments/v0/parameters/{name}.json"
        parameters_sha256 = _git_blob_sha256(
            root,
            source_commit,
            parameters_path,
        )
        parameters_data = _git_blob_json(root, source_commit, parameters_path)
        variants = None if parameters_data is None else parameters_data.get("variants")
        seed_variant = seed_variants.get(name)
        if (
            parameters_sha256 is None
            or not isinstance(variants, list)
            or not variants
            or any(not isinstance(item, str) or not item for item in variants)
            or len(set(variants)) != len(variants)
            or not isinstance(seed_variant, str)
            or seed_variant not in variants
        ):
            return None
        expected_recovery_ratio = _source_expected_perturbation_ratio(
            graph_data, parameters_data, controls_data, name
        )
        if expected_recovery_ratio is None:
            return None
        runs[name] = {
            "contract_sha256": contract_sha256,
            "graph_sha256": graph_sha256,
            "parameters_sha256": parameters_sha256,
            "variant_count": len(variants),
            "variants": variants,
            "seed_variant": seed_variant,
            "perturbation_recovery_ratio": expected_recovery_ratio,
        }

    return {
        "runs": runs,
        "witness": {
            "recipe_path": recipe_path,
            "recipe_sha256": recipe_sha256,
            "adapter_path": adapter_path,
            "adapter_sha256": adapter_sha256,
        },
        "control": {
            "graph_sha256": graph_sha256,
            "parameters_sha256": controls_sha256,
            "subcritical_target_radius": controls_data.get("subcritical_target_radius"),
            "supercritical_target_radius": controls_data.get("supercritical_target_radius"),
            "variant_count": controls_data.get("variant_count"),
            "horizon": controls_data.get("horizon"),
            "run_initial_mass": controls_data.get("run_initial_mass"),
            "run_seed_node": seed_node,
        },
    }


def _source_currentness(
    root: Path, source_commit: str, head: str
) -> tuple[str, str | None]:
    experiment_dirty, _ = working_tree_paths_dirty(root, EXPERIMENT_SURFACE_PATHS)
    if experiment_dirty is None:
        return "UNKNOWN", "working_tree_status_unavailable"
    if experiment_dirty:
        return "STALE", "working_tree_experiment_surface_dirty"

    evidence_dirty, _ = working_tree_paths_dirty(root, RESEARCH_EVIDENCE_PATHS)
    if evidence_dirty is None:
        return "UNKNOWN", "working_tree_status_unavailable"
    if evidence_dirty:
        return "STALE", "working_tree_research_input_dirty"

    qa_dirty, _ = working_tree_paths_dirty(root, RESEARCH_QA_SURFACE_PATHS)
    if qa_dirty is None:
        return "UNKNOWN", "working_tree_status_unavailable"
    if qa_dirty:
        return "STALE", "working_tree_research_qa_surface_dirty"

    if source_commit == head:
        return "CURRENT", None

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode == 1:
        return "INVALID", "source_commit_not_ancestor"
    if ancestor.returncode != 0:
        return "UNKNOWN", "source_ancestry_unavailable"

    diff = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            f"{source_commit}..{head}",
            "--",
            *EXPERIMENT_SURFACE_PATHS,
        ],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if diff.returncode == 0:
        return "BOUND_UNCHANGED_SURFACE", None
    if diff.returncode == 1:
        return "STALE", "reference_receipts_stale_for_current_surface"
    return "UNKNOWN", "surface_currentness_unavailable"


def build_current_receipt(root: Path) -> dict:
    contract = _load_json(root / "experiments" / "v0" / "contract.json")
    runs = {}
    for name in REQUIRED_RUNS:
        receipt = _maybe_load(root / "receipts" / "reference" / f"v0-{name}.json")
        if receipt is not None:
            runs[name] = receipt

    control_receipt = _maybe_load(
        root / "receipts" / "reference" / "v0-controls.json"
    )
    witness = _maybe_load(
        root / "receipts" / "independent" / "wolfram-v0.json"
    )
    head = _git_head(root)

    if runs:
        source_commits = {r.get("source_commit") for r in runs.values()}
        if None in source_commits or len(source_commits) != 1:
            payload = _status("FAIL", "mixed_or_missing_run_source_commits")
            source_commit = head
        else:
            source_commit = next(iter(source_commits))
            bindings = _expected_evidence_bindings(root, source_commit)
            payload = evaluate_research_contract(
                contract,
                runs,
                control_receipt,
                witness,
                source_commit=source_commit,
                evidence_bindings=bindings,
            )
    else:
        source_commit = head
        bindings = _expected_evidence_bindings(root, source_commit)
        payload = evaluate_research_contract(
            contract,
            runs,
            control_receipt,
            witness,
            source_commit=source_commit,
            evidence_bindings=bindings,
        )

    currentness, currentness_reason = _source_currentness(
        root, source_commit, head
    )
    if currentness == "INVALID":
        payload = _status(
            "FAIL", currentness_reason or "source_currentness_invalid"
        )
    elif currentness == "STALE":
        payload = _status(
            "UNKNOWN", currentness_reason or "reference_receipts_stale"
        )
    elif currentness == "UNKNOWN":
        payload = _status(
            "UNKNOWN", currentness_reason or "source_currentness_unknown"
        )

    return {
        "schema_version": 1,
        "experiment_id": contract.get("experiment_id"),
        "source_commit": source_commit,
        "storage_head": head,
        "source_currentness": currentness,
        **payload,
    }


DURABLE_RESEARCH_EVIDENCE_PATHS = (
    "receipts/reference/v0-virus.json",
    "receipts/reference/v0-meme.json",
    "receipts/reference/v0-agent.json",
    "receipts/reference/v0-controls.json",
    "receipts/independent/wolfram-v0.json",
)


def verify_stored_receipt(root: Path, path: Path) -> dict:
    root = root.resolve()
    stored_path = path if path.is_absolute() else root / path
    try:
        stored = _load_json(stored_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "verification_status": "FAIL",
            "reason": "stored_receipt_unreadable",
            "mismatched": ["stored_receipt"],
        }
    if not isinstance(stored, dict):
        return {
            "verification_status": "FAIL",
            "reason": "stored_receipt_invalid",
            "mismatched": ["stored_receipt"],
        }

    expected = build_current_receipt(root)
    mismatched = []
    semantic_keys = (set(stored) | set(expected)) - {"storage_head"}
    for key in sorted(semantic_keys):
        if stored.get(key) != expected.get(key):
            mismatched.append(key)

    if expected.get("contract_status") != "PASS":
        if "contract_status" not in mismatched:
            mismatched.append("contract_status")

    storage_head = stored.get("storage_head")
    source_commit = stored.get("source_commit")
    current_head = _git_head(root)
    if (
        not isinstance(storage_head, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", storage_head) is None
    ):
        mismatched.append("storage_head")
    else:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", storage_head, current_head],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if ancestor.returncode != 0:
            mismatched.append("storage_head")
        elif not isinstance(source_commit, str):
            mismatched.append("source_commit")
        else:
            for relpath in DURABLE_RESEARCH_EVIDENCE_PATHS:
                evidence = _git_blob_json(root, storage_head, relpath)
                if (
                    evidence is None
                    or evidence.get("source_commit") != source_commit
                ):
                    mismatched.append("storage_head")
                    break

    mismatched = sorted(set(mismatched))
    if mismatched:
        return {
            "verification_status": "FAIL",
            "reason": "stored_receipt_mismatch",
            "mismatched": mismatched,
            "source_commit": source_commit,
            "storage_head": storage_head,
            "current_head": current_head,
        }
    return {
        "verification_status": "PASS",
        "source_commit": source_commit,
        "storage_head": storage_head,
        "current_head": current_head,
    }


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the deterministic v0 research contract."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-stored", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.output and args.verify_stored:
        parser.error("--output and --verify-stored are mutually exclusive")
    if args.verify_stored:
        verification = verify_stored_receipt(root, args.verify_stored)
        print(
            json.dumps(verification, sort_keys=True, separators=(",", ":"))
            + "\n",
            end="",
        )
        return 0 if verification["verification_status"] == "PASS" else 1
    payload = build_current_receipt(root)
    text = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ) + "\n"
    if args.output:
        output = (
            args.output
            if args.output.is_absolute()
            else root / args.output
        )
        _write_atomic(output, payload)
    print(text, end="")
    if payload["contract_status"] == "PASS":
        return 0
    if payload["contract_status"] == "FAIL":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
