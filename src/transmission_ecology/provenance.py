from __future__ import annotations

import subprocess
from pathlib import Path


EXPERIMENT_SURFACE_PATHS = (
    "pyproject.toml",
    "src/transmission_ecology/__init__.py",
    "src/transmission_ecology/graph.py",
    "src/transmission_ecology/state.py",
    "src/transmission_ecology/metrics.py",
    "src/transmission_ecology/cli.py",
    "src/transmission_ecology/receipt.py",
    "src/transmission_ecology/provenance.py",
    "src/transmission_ecology/models",
    "experiments/v0",
    "tools/run-v0",
)


def working_tree_paths_dirty(
    root: Path, paths: tuple[str, ...]
) -> tuple[bool | None, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *paths],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        return None, ""
    return bool(status.stdout.strip()), status.stdout
