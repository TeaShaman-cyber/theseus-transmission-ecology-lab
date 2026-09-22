from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from transmission_ecology.graph import adjacency_matrix, cycle_rank_beta1, load_graph
from transmission_ecology.metrics import spectral_radius, summarize_run
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


ADAPTERS = {"virus": virus, "meme": meme, "agent": agent}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _root_from_graph_path(graph_path: Path) -> Path:
    graph_path = graph_path.resolve()
    return graph_path.parents[2]


def _initial_state(node_count: int, variant_count: int) -> np.ndarray:
    state = np.zeros(node_count * variant_count, dtype=float)
    state[0] = 1.0
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
) -> dict:
    if name not in ADAPTERS:
        raise ValueError(f"unknown substrate: {name}")
    graph_path = Path(graph_path)
    params_path = Path(params_path)
    root = _root_from_graph_path(graph_path)
    graph = load_graph(graph_path)
    params = _load_json(params_path)
    variants = validate_variants(params)
    K = ADAPTERS[name].build_operator(graph, params)
    x0 = _initial_state(len(graph.nodes), len(variants))
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
    topology = {
        "cycle_rank_beta1": cycle_rank_beta1(graph),
        "same_graph": True,
        "graph_sha256": sha256_file(graph_path),
    }
    all_passed = (
        low_check["spectral_radius"] < 1.0
        and low_check["final_mass"] < low_check["initial_mass"]
        and high_check["spectral_radius"] > 1.0
        and high_check["final_mass"] > high_check["initial_mass"]
        and topology["cycle_rank_beta1"] == 2
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
    control_receipt = run_controls(graph, graph_path, controls, controls_path, source_commit=source_commit)
    outputs = {}
    for name in ("virus", "meme", "agent"):
        params_path = root / "experiments" / "v0" / "parameters" / f"{name}.json"
        receipt = run_substrate(name, graph_path, params_path, horizon, source_commit)
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
        root = Path.cwd().resolve()
        source_commit = _git_head(root)
        out = root / "receipts" / "reference"
        receipts = write_reference_set(root, out, horizon=args.horizon, source_commit=source_commit)
        summary = {name: str(path.relative_to(root)) for name, path in receipts.items()}
        print(json.dumps({"source_commit": source_commit, "receipts": summary}, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
