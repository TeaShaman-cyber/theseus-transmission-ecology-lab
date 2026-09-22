from __future__ import annotations

import json
from pathlib import Path


def _reject_nonstandard_constant(value: str):
    raise ValueError(f"non-standard JSON constant: {value}")


def loads_strict(text: str):
    return json.loads(text, parse_constant=_reject_nonstandard_constant)


def load_json(path: Path | str):
    return loads_strict(Path(path).read_text(encoding="utf-8"))
