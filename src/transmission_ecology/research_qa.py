from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

REQUIRED_RUNS = ("virus", "meme", "agent")
EXPERIMENT_SURFACE_PATHS = (
    "pyproject.toml",
    "src/transmission_ecology/graph.py",
    "src/transmission_ecology/state.py",
    "src/transmission_ecology/metrics.py",
    "src/transmission_ecology/cli.py",
    "src/transmission_ecology/receipt.py",
    "src/transmission_ecology/models",
    "experiments/v0",
    "tools/run-v0",
)


def _status(status: str, reason: str, **extra):
    payload = {"contract_status": status, "authority": "NONE", "reason": reason}
    payload.update(extra)
    return payload


def evaluate_research_contract(contract, run_receipts, witness, *, source_commit):
    required = ("question", "hypothesis", "falsifiers", "declared_metrics",
                "required_controls", "limitations", "independent_witness")
    missing = [key for key in required if not contract.get(key)]
    if missing:
        return _status("FAIL", "missing_contract_fields", missing=missing)
    absent = [name for name in REQUIRED_RUNS if name not in run_receipts]
    if absent:
        return _status("UNKNOWN", "missing_run_receipts", missing=absent)
    if any(r.get("source_commit") != source_commit for r in run_receipts.values()):
        return _status("FAIL", "source_commit_mismatch")
    if any(not r.get("controls", {}).get("all_passed") for r in run_receipts.values()):
        return _status("FAIL", "required_control_failed")
    if contract["independent_witness"].get("required"):
        if witness is None:
            return _status("UNKNOWN", "independent_witness_missing")
        if witness.get("source_commit") != source_commit:
            return _status("FAIL", "witness_commit_mismatch")
        if witness.get("status") != "VERIFIED":
            return _status("DEGRADED", "witness_not_verified")
    return {
        "contract_status": "PASS",
        "epistemic_state": "HYPOTHESIS",
        "scientific_disposition": "UNKNOWN_WITHIN_CURRENT_CONTRACT",
        "authority": "NONE",
        "source_commit": source_commit,
    }


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _maybe_load(path: Path):
    if not path.is_file():
        return None
    return _load_json(path)


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _source_currentness(root: Path, source_commit: str, head: str) -> tuple[str, str | None]:
    if source_commit == head:
        return "CURRENT", None
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if ancestor.returncode == 1:
        return "INVALID", "source_commit_not_ancestor"
    if ancestor.returncode != 0:
        return "UNKNOWN", "source_ancestry_unavailable"
    diff = subprocess.run(
        ["git", "diff", "--quiet", f"{source_commit}..{head}", "--", *EXPERIMENT_SURFACE_PATHS],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
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
    witness = _maybe_load(root / "receipts" / "independent" / "wolfram-v0.json")
    head = _git_head(root)
    if runs:
        source_commits = {r.get("source_commit") for r in runs.values()}
        if None in source_commits or len(source_commits) != 1:
            payload = _status("FAIL", "mixed_or_missing_run_source_commits")
            source_commit = head
        else:
            source_commit = next(iter(source_commits))
            payload = evaluate_research_contract(contract, runs, witness, source_commit=source_commit)
    else:
        source_commit = head
        payload = evaluate_research_contract(contract, runs, witness, source_commit=source_commit)
    currentness, currentness_reason = _source_currentness(root, source_commit, head)
    if currentness == "INVALID":
        payload = _status("FAIL", currentness_reason or "source_currentness_invalid")
    elif currentness == "STALE":
        payload = _status("UNKNOWN", currentness_reason or "reference_receipts_stale")
    elif currentness == "UNKNOWN":
        payload = _status("UNKNOWN", currentness_reason or "source_currentness_unknown")
    result = {
        "schema_version": 1,
        "experiment_id": contract.get("experiment_id"),
        "source_commit": source_commit,
        "storage_head": head,
        "source_currentness": currentness,
        **payload,
    }
    return result


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate the deterministic v0 research contract.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    payload = build_current_receipt(root)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        _write_atomic(output, payload)
    print(text, end='')
    if payload["contract_status"] == "PASS": return 0
    if payload["contract_status"] == "FAIL": return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
