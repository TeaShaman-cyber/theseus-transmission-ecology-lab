from __future__ import annotations

import json
from pathlib import Path


def _reject_nonstandard_constant(value: str):
    raise ValueError(f"non-standard JSON constant: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def loads_strict(text: str):
    return json.loads(
        text,
        parse_constant=_reject_nonstandard_constant,
        object_pairs_hook=_unique_object,
    )


def load_json(path: Path | str):
    return loads_strict(Path(path).read_text(encoding="utf-8"))
