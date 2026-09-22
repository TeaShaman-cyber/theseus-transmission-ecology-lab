from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import tempfile
from pathlib import Path

import numpy as np


RECEIPT_SCHEMA_VERSION = 2
FLOAT_SIGNIFICANT_DIGITS = 12


def numeric_policy() -> dict[str, int]:
    return {"float_significant_digits": FLOAT_SIGNIFICANT_DIGITS}


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonicalize_json(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON does not allow nonfinite floats")
        rounded = float(format(value, f".{FLOAT_SIGNIFICANT_DIGITS}g"))
        return 0.0 if rounded == 0.0 else rounded
    if isinstance(value, dict):
        return {key: _canonicalize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_json(item) for item in value]
    return value


def canonical_json_bytes(payload: dict) -> bytes:
    normalized = _canonicalize_json(payload)
    return (
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_json_atomic(path: Path | str, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(payload)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
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
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "numeric_policy": numeric_policy(),
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
