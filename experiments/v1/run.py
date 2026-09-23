from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from experiments.v1.receipt import (
    build_identity_control,
    build_step_receipt,
    evaluate_stage_attribution,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _surface_dirty(root: Path) -> bool:
    # The runner imports from both repository root and src. Include every local
    # Python import surface plus the explicit fixture/runner/docs contract, so
    # untracked shadow modules (for example numpy.py or sitecustomize.py) cannot
    # influence a durable receipt without being bound to source revision.
    result = subprocess.run(
        [
            "git", "status", "--porcelain", "--untracked-files=all", "--",
            ":(glob)**/*.py",
            "pyproject.toml",
            "experiments/v1/canonical-fixture.json",
            "tools/run-v1",
            "docs/v1-run.md",
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return bool(result.stdout.strip())


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
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


def build_canonical_receipt(root: Path) -> dict:
    fixture_path = root / "experiments" / "v1" / "canonical-fixture.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    head = _git_head(root)
    I = fixture["identity_gate"]
    W = fixture["selection_gate"]
    gates = {
        "target-only": (I, W),
        "source-only": (W, I),
        "two-stage": (W, W),
    }
    cases = {}
    for case_id in fixture["cases"]:
        source_gate, target_gate = gates[case_id]
        receipt = build_step_receipt(
            case_id=case_id,
            fixture_id=fixture["fixture_id"],
            source_revision=head,
            state=fixture["input_state"],
            variant_transition=fixture["variant_transition"],
            source_gate=source_gate,
            target_gate=target_gate,
        )
        controls = {
            stage: build_identity_control(receipt, stage)
            for stage in receipt["claimed_stages"]
        }
        verdict = evaluate_stage_attribution(receipt, controls)
        cases[case_id] = {
            "receipt": receipt,
            "identity_controls": controls,
            "verdict": verdict,
        }
    return {
        "schema_version": 1,
        "experiment_id": "deterministic-v1-two-stage",
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": _sha256(fixture_path),
        "source_revision": head,
        "scientific_authority": "NONE",
        "scientific_disposition": None,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.output is not None and _surface_dirty(root):
        parser.error("run-v1 refuses to write a durable receipt from a dirty v1 execution surface")
    payload = build_canonical_receipt(root)
    if args.output is None:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        output = args.output if args.output.is_absolute() else root / args.output
        _write_atomic(output, payload)
        print(str(output.relative_to(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
