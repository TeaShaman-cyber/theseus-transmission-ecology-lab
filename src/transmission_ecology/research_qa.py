from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

REQUIRED_RUNS = ("virus", "meme", "agent")


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
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def build_current_receipt(root: Path) -> dict:
    contract = _load_json(root / "experiments" / "v0" / "contract.json")
    runs = {}
    for name in REQUIRED_RUNS:
        receipt = _maybe_load(root / "receipts" / "reference" / f"v0-{name}.json")
        if receipt is not None:
            runs[name] = receipt
    witness = _maybe_load(root / "receipts" / "independent" / "wolfram-v0.json")
    head = _git_head(root)
    payload = evaluate_research_contract(contract, runs, witness, source_commit=head)
    return {"schema_version": 1, "experiment_id": contract.get("experiment_id"), **payload}


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
    status = payload["contract_status"]
    if status == "PASS":
        return 0
    if status == "FAIL":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
