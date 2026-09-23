from __future__ import annotations

import subprocess
from pathlib import Path


EXPERIMENT_SURFACE_PATHS = (
    "pyproject.toml",
    "src",
    ":(exclude)src/transmission_ecology/research_qa.py",
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
