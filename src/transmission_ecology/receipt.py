from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path

import numpy as np


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_json_atomic(path: Path | str, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(payload)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def build_run_receipt(
    *,
    experiment_id: str,
    source_commit: str,
    substrate: str,
    horizon: int,
    contract_path: Path,
    graph_path: Path,
    parameters_path: Path,
    metrics: dict,
    controls: dict,
) -> dict:
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "source_commit": source_commit,
        "contract_sha256": sha256_file(contract_path),
        "graph_sha256": sha256_file(graph_path),
        "parameters_sha256": sha256_file(parameters_path),
        "substrate": substrate,
        "horizon": int(horizon),
        "metrics": metrics,
        "controls": controls,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "scientific_authority": "NONE",
    }
