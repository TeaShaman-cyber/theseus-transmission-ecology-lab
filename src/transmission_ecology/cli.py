from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from transmission_ecology.graph import adjacency_matrix, cycle_rank_beta1, load_graph
from transmission_ecology.metrics import spectral_radius, summarize_run
from transmission_ecology.provenance import (
    EXPERIMENT_SURFACE_PATHS,
    working_tree_paths_dirty,
)
from transmission_ecology.models import agent, meme, virus
from transmission_ecology.models.base import kron_operator, validate_variants
from transmission_ecology.receipt import (
    RECEIPT_SCHEMA_VERSION,
    build_run_receipt,
    numeric_policy,
    sha256_file,
    write_json_atomic,
)
from transmission_ecology.state import simulate
from transmission_ecology.strict_json import load_json


ADAPTERS = {"virus": virus, "meme": meme, "agent": agent}


def _load_json(path: Path) -> dict:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _root_from_graph_path(graph_path: Path) -> Path:
    graph_path = graph_path.resolve()
    return graph_path.parents[2]


def _initial_state(
    node_count: int,
    variant_count: int,
    *,
    initial_mass: float = 1.0,
    seed_node_index: int = 0,
    seed_variant_index: int = 0,
) -> np.ndarray:
    if not np.isfinite(initial_mass) or initial_mass <= 0:
        raise ValueError("initial_mass must be finite and positive")
    if (
        isinstance(seed_node_index, bool)
        or not isinstance(seed_node_index, int)
        or not 0 <= seed_node_index < node_count
    ):
        raise ValueError("seed_node_index out of range")
    if (
        isinstance(seed_variant_index, bool)
        or not isinstance(seed_variant_index, int)
        or not 0 <= seed_variant_index < variant_count
    ):
        raise ValueError("seed_variant_index out of range")
    state = np.zeros(node_count * variant_count, dtype=float)
    offset = seed_node_index * variant_count + seed_variant_index
    state[offset] = float(initial_mass)
    return state


def _perturbed_final(K, states, *, node_count: int, variant_count: int, horizon: int) -> np.ndarray:
    midpoint = horizon // 2
    mid_state = states[midpoint].copy().reshape(node_count, variant_count)
    variant_mass = mid_state.sum(axis=0)
    dominant = int(np.argmax(variant_mass))
    mid_state[:, dominant] = 0.0
    remaining = horizon - midpoint
    return simulate(K, mid_state.reshape(-1), remaining)[-1]


def run_substrate(
    name: str,
    graph_path: Path | str,
    params_path: Path | str,
    horizon: int,
    source_commit: str,
    *,
    initial_mass: float = 1.0,
    seed_node: str | None = None,
    seed_variant: str | None = None,
) -> dict:
    if name not in ADAPTERS:
        raise ValueError(f"unknown substrate: {name}")
    graph_path = Path(graph_path)
    params_path = Path(params_path)
    root = _root_from_graph_path(graph_path)
    graph = load_graph(graph_path)
    params = _load_json(params_path)
    variants = validate_variants(params)
    if seed_node is None:
        seed_node = graph.nodes[0]
    if seed_variant is None:
        seed_variant = variants[0]
    if not isinstance(seed_node, str) or seed_node not in graph.nodes:
        raise ValueError("seed_node must name a graph node")
    if not isinstance(seed_variant, str) or seed_variant not in variants:
        raise ValueError("seed_variant must name a substrate variant")
    seed_node_index = graph.nodes.index(seed_node)
    seed_variant_index = variants.index(seed_variant)
    K = ADAPTERS[name].build_operator(graph, params)
    x0 = _initial_state(
        len(graph.nodes),
        len(variants),
        initial_mass=initial_mass,
        seed_node_index=seed_node_index,
        seed_variant_index=seed_variant_index,
    )
    states = simulate(K, x0, horizon)
    perturbed_final = _perturbed_final(
        K, states, node_count=len(graph.nodes), variant_count=len(variants), horizon=horizon
    )
    metrics = summarize_run(
        K,
        states,
        node_count=len(graph.nodes),
        variant_count=len(variants),
        cycle_rank_beta1_value=cycle_rank_beta1(graph),
        perturbed_final=perturbed_final,
    )
    return build_run_receipt(
        experiment_id="deterministic-v0",
        source_commit=source_commit,
        substrate=name,
        horizon=horizon,
        contract_path=root / "experiments" / "v0" / "contract.json",
        graph_path=graph_path,
        parameters_path=params_path,
        metrics=metrics,
        controls={"all_passed": False, "status": "NOT_EVALUATED"},
        initial_condition={
            "node": seed_node,
            "variant": seed_variant,
            "mass": float(initial_mass),
        },
    )


def _scale_to_radius(K: np.ndarray, target: float) -> np.ndarray:
    rho = spectral_radius(K)
    if rho <= 0:
        raise ValueError("cannot scale zero-radius operator")
    return K * (float(target) / rho)


def run_controls(
    graph,
    graph_path: Path | str,
    controls: dict,
    controls_path: Path | str,
    *,
    source_commit: str,
) -> dict:
    graph_path = Path(graph_path)
    controls_path = Path(controls_path)
    variant_count = int(controls.get("variant_count", 2))
    horizon = int(controls.get("horizon", 8))
    if variant_count <= 0 or horizon < 0:
        raise ValueError("control variant_count/horizon invalid")
    A = adjacency_matrix(graph)
    base = kron_operator(A, np.eye(variant_count), scale=1.0)
    low = _scale_to_radius(base, float(controls["subcritical_target_radius"]))
    high = _scale_to_radius(base, float(controls["supercritical_target_radius"]))
    x0 = np.ones(len(graph.nodes) * variant_count, dtype=float)
    low_states = simulate(low, x0, horizon)
    high_states = simulate(high, x0, horizon)
    low_check = {
        "spectral_radius": spectral_radius(low),
        "initial_mass": float(low_states[0].sum()),
        "final_mass": float(low_states[-1].sum()),
    }
    high_check = {
        "spectral_radius": spectral_radius(high),
        "initial_mass": float(high_states[0].sum()),
        "final_mass": float(high_states[-1].sum()),
    }
    graph_hash = sha256_file(graph_path)
    beta1 = cycle_rank_beta1(graph)
    low_regime = (
        "decay"
        if low_check["final_mass"] < low_check["initial_mass"]
        else "non_decay"
    )
    high_regime = (
        "growth"
        if high_check["final_mass"] > high_check["initial_mass"]
        else "non_growth"
    )
    same_topology = True
    opposite_regimes = low_regime == "decay" and high_regime == "growth"
    topology = {
        "graph_sha256": graph_hash,
        "subcritical_graph_sha256": graph_hash,
        "supercritical_graph_sha256": graph_hash,
        "cycle_rank_beta1": beta1,
        "subcritical_cycle_rank_beta1": beta1,
        "supercritical_cycle_rank_beta1": beta1,
        "subcritical_regime": low_regime,
        "supercritical_regime": high_regime,
        "same_topology": same_topology,
        "opposite_regimes": opposite_regimes,
        "topology_only_explanation_rejected": (
            same_topology and opposite_regimes
        ),
    }
    all_passed = (
        low_check["spectral_radius"] < 1.0
        and low_regime == "decay"
        and high_check["spectral_radius"] > 1.0
        and high_regime == "growth"
        and topology["cycle_rank_beta1"] == 2
        and topology["topology_only_explanation_rejected"]
    )
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "numeric_policy": numeric_policy(),
        "experiment_id": "deterministic-v0",
        "source_commit": source_commit,
        "graph_sha256": sha256_file(graph_path),
        "parameters_sha256": sha256_file(controls_path),
        "scientific_authority": "NONE",
        "all_passed": bool(all_passed),
        "checks": {"subcritical": low_check, "supercritical": high_check, "topology_only": topology},
    }


def write_reference_set(root: Path | str, out: Path | str, *, horizon: int, source_commit: str) -> dict[str, Path]:
    root = Path(root).resolve()
    out = Path(out)
    if not out.is_absolute():
        out = root / out
    graph_path = root / "experiments" / "v0" / "shared-graph.json"
    controls_path = root / "experiments" / "v0" / "controls.json"
    graph = load_graph(graph_path)
    controls = _load_json(controls_path)
    seed_node = controls.get("run_seed_node")
    seed_variants = controls.get("run_seed_variants")
    initial_mass = controls.get("run_initial_mass")
    if not isinstance(seed_node, str) or not seed_node:
        raise ValueError("run_seed_node must be a non-empty string")
    if (
        not isinstance(seed_variants, dict)
        or set(seed_variants) != {"virus", "meme", "agent"}
        or any(not isinstance(value, str) or not value for value in seed_variants.values())
    ):
        raise ValueError("run_seed_variants must name one variant per substrate")
    if (
        isinstance(initial_mass, bool)
        or not isinstance(initial_mass, (int, float))
        or not np.isfinite(float(initial_mass))
        or float(initial_mass) <= 0.0
    ):
        raise ValueError("run_initial_mass must be finite and positive")
    control_receipt = run_controls(graph, graph_path, controls, controls_path, source_commit=source_commit)
    outputs = {}
    for name in ("virus", "meme", "agent"):
        params_path = root / "experiments" / "v0" / "parameters" / f"{name}.json"
        receipt = run_substrate(
            name,
            graph_path,
            params_path,
            horizon,
            source_commit,
            initial_mass=float(initial_mass),
            seed_node=seed_node,
            seed_variant=seed_variants[name],
        )
        receipt["controls"] = {
            "all_passed": control_receipt["all_passed"],
            "control_receipt": "v0-controls.json",
        }
        path = out / f"v0-{name}.json"
        write_json_atomic(path, receipt)
        outputs[name] = path
    control_path = out / "v0-controls.json"
    write_json_atomic(control_path, control_receipt)
    outputs["controls"] = control_path
    return outputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic transmission ecology experiments.")
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser("run-v0")
    run.add_argument("--horizon", type=int, default=8)
    run.add_argument("--write-reference", action="store_true")
    args = parser.parse_args(argv)
    if args.command == 'run-v0':
        if not args.write_reference:
            parser.error(
                "run-v0 requires --write-reference before overwriting reference receipts"
            )
        root = Path.cwd().resolve()
        execution_dirty, _ = working_tree_paths_dirty(
            root, EXPERIMENT_SURFACE_PATHS
        )
        if execution_dirty is None:
            parser.error(
                "run-v0 could not verify execution surface cleanliness"
            )
        if execution_dirty:
            parser.error(
                "run-v0 refuses to write reference receipts from a dirty execution surface"
            )
        source_commit = _git_head(root)
        out = root / "receipts" / "reference"
        receipts = write_reference_set(root, out, horizon=args.horizon, source_commit=source_commit)
        summary = {name: str(path.relative_to(root)) for name, path in receipts.items()}
        print(json.dumps({"source_commit": source_commit, "receipts": summary}, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
