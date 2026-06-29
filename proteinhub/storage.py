from __future__ import annotations

import re
from pathlib import Path


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(filename: str) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", Path(filename).name).strip("._")
    return cleaned or "artifact.bin"


def artifact_relative_path(
    *,
    project_id: int,
    sequence_id: int,
    artifact_id: int,
    filename: str,
) -> Path:
    safe_name = safe_filename(filename)
    return Path("projects") / str(project_id) / "sequences" / str(sequence_id) / "artifacts" / str(artifact_id) / safe_name


def resolve_storage_path(storage_root: Path, relative_path: str | Path) -> Path:
    root = storage_root.resolve()
    path = (root / relative_path).resolve()
    path.relative_to(root)
    return path

