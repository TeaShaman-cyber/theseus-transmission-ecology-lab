#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import subprocess
import tempfile


def _reject_constant(value: str):
    raise ValueError(f"non-standard JSON constant: {value}")


def load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wl_string(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Wolfram string inputs must be non-empty strings")
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def finite_number(value, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or (value <= 0.0 if positive else value < 0.0):
        raise ValueError(f"{name} has invalid numeric value")
    return value


def render_wolfram_code(root: pathlib.Path) -> str:
    root = root.resolve()
    graph = load_json(root / "experiments/v0/shared-graph.json")
    controls = load_json(root / "experiments/v0/controls.json")
    template = (root / "experiments/v0/witness/wolfram-v0.wl").read_text(
        encoding="utf-8"
    )

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if (
        graph.get("schema_version") != 1
        or not isinstance(nodes, list)
        or not nodes
        or any(not isinstance(node, str) or not node for node in nodes)
        or len(set(nodes)) != len(nodes)
        or not isinstance(edges, list)
        or not edges
    ):
        raise ValueError("invalid witness graph input")
    node_set = set(nodes)
    rendered_edges = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"edge {index} must be an object")
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_set or target not in node_set:
            raise ValueError(f"edge {index} references unknown node")
        weight = finite_number(edge.get("weight"), f"edge {index} weight", positive=True)
        rendered_edges.append(
            "{" + ",".join((wl_string(source), wl_string(target), repr(weight))) + "}"
        )

    variant_count = controls.get("variant_count")
    if isinstance(variant_count, bool) or not isinstance(variant_count, int) or variant_count <= 0:
        raise ValueError("variant_count must be a positive integer")
    sub_target = finite_number(
        controls.get("subcritical_target_radius"),
        "subcritical_target_radius",
        positive=True,
    )
    super_target = finite_number(
        controls.get("supercritical_target_radius"),
        "supercritical_target_radius",
        positive=True,
    )
    if not sub_target < 1.0 or not super_target > 1.0:
        raise ValueError("control targets must straddle one")

    replacements = {
        "__NODES__": "{" + ",".join(wl_string(node) for node in nodes) + "}",
        "__EDGES__": "{" + ",".join(rendered_edges) + "}",
        "__VARIANT_COUNT__": str(variant_count),
        "__SUB_TARGET__": repr(sub_target),
        "__SUPER_TARGET__": repr(super_target),
    }
    code = template
    for marker, value in replacements.items():
        if marker not in code:
            raise ValueError(f"missing template marker: {marker}")
        code = code.replace(marker, value)
    if re.search(r"__[A-Z0-9_]+__", code):
        raise ValueError("unresolved Wolfram template marker")
    return code


def parse_wolfram_payload(raw: str):
    for line in raw.splitlines():
        match = re.match(r"^\s*Out\[\d+\]\s*=\s*(.+?)\s*$", line)
        if not match:
            continue
        try:
            value = json.loads(match.group(1))
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def canonical_number(value, digits: int):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("witness numeric result has invalid type")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("witness numeric result must be finite")
    rounded = float(format(value, f".{digits}g"))
    return 0.0 if rounded == 0.0 else rounded


def _run(cmd):
    try:
        return subprocess.run(cmd, text=True, capture_output=True, check=False)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", f"{type(exc).__name__}: {exc}")


def build_witness_receipt(
    *,
    root: pathlib.Path,
    source_commit: str,
    payload: dict,
    mcporter: pathlib.Path,
    config: pathlib.Path,
) -> dict:
    contract = load_json(root / "experiments/v0/contract.json")
    witness_contract = contract["independent_witness"]
    digits = contract["receipt_contract"]["float_significant_digits"]
    required_checks = witness_contract["required_checks"]

    observed = {}
    verified = True
    for key, expected in required_checks.items():
        if isinstance(expected, bool):
            verified = verified and payload.get(key) is expected
            continue
        try:
            observed_value = canonical_number(payload.get(key), digits)
            expected_value = canonical_number(expected, digits)
        except ValueError:
            verified = False
            continue
        observed[key] = observed_value
        verified = verified and observed_value == expected_value

    adapter_path = root / witness_contract["adapter_path"]
    recipe_path = root / witness_contract["recipe_path"]
    graph_path = root / "experiments/v0/shared-graph.json"
    controls_path = root / "experiments/v0/controls.json"
    version_proc = _run([str(mcporter), "--version"])
    mcporter_version = (
        version_proc.stdout.strip() if version_proc.returncode == 0 else "UNAVAILABLE"
    )
    return {
        "schema_version": witness_contract["witness_schema_version"],
        "experiment_id": contract["experiment_id"],
        "source_commit": source_commit,
        "status": "VERIFIED" if verified else "MISMATCH",
        "authority": "NONE",
        "scientific_authority": "NONE",
        "backend": witness_contract["expected_backend"],
        "kind": witness_contract["kind"],
        "recipe_sha256": sha256_file(recipe_path),
        "adapter_sha256": sha256_file(adapter_path),
        "inputs": {
            "graph_sha256": sha256_file(graph_path),
            "controls_sha256": sha256_file(controls_path),
        },
        "checks": required_checks,
        "observed": observed,
        "transport": {
            "mcporter_version": mcporter_version,
            "config_sha256": sha256_file(config),
            "tool": witness_contract["expected_backend"],
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--mcporter")
    parser.add_argument("--config")
    parser.add_argument("--out")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    code = render_wolfram_code(root)
    if args.render_only:
        print(code, end="" if code.endswith("\n") else "\n")
        return 0

    if not args.mcporter or not args.config or not args.out:
        parser.error("--mcporter, --config, and --out are required unless --render-only")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if head != args.source_commit:
        parser.error("source commit does not match witness checkout HEAD")
    if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", args.source_commit) is None:
        parser.error("source commit must be a full canonical object id")

    mcporter = pathlib.Path(args.mcporter).resolve()
    config = pathlib.Path(args.config).resolve()
    with tempfile.NamedTemporaryFile("w", suffix=".wl", encoding="utf-8") as handle:
        handle.write(code)
        handle.flush()
        proc = _run(
            [
                str(mcporter),
                "--config",
                str(config),
                "call",
                "wolfram.WolframLanguageEvaluator",
                f"code=@{handle.name}",
                "timeConstraint=60",
            ]
        )
    raw = (proc.stdout + "\n" + proc.stderr).strip()
    payload = parse_wolfram_payload(raw)
    if proc.returncode != 0 or not isinstance(payload, dict):
        print(raw)
        return 2

    receipt = build_witness_receipt(
        root=root,
        source_commit=args.source_commit,
        payload=payload,
        mcporter=mcporter,
        config=config,
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
