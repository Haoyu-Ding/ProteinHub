from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from proteinhub.infrastructure.storage.paths import (
    artifact_relative_path,
    protein_structure_relative_path,
    resolve_storage_path,
)


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    absolute_path: Path
    size_bytes: int


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save_artifact(
        self,
        *,
        project_id: int,
        protein_id: int,
        artifact_id: int,
        filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        relative_path = artifact_relative_path(
            project_id=project_id,
            protein_id=protein_id,
            artifact_id=artifact_id,
            filename=filename,
        )
        absolute_path = resolve_storage_path(self.root, relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        size = 0
        with absolute_path.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                output.write(chunk)

        return StoredFile(
            relative_path=relative_path.as_posix(),
            absolute_path=absolute_path,
            size_bytes=size,
        )

    def save_protein_structure(
        self,
        *,
        project_id: int,
        protein_id: int,
        filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        relative_path = protein_structure_relative_path(
            project_id=project_id,
            protein_id=protein_id,
            filename=filename,
        )
        absolute_path = resolve_storage_path(self.root, relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        size = 0
        with absolute_path.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                output.write(chunk)

        return StoredFile(
            relative_path=relative_path.as_posix(),
            absolute_path=absolute_path,
            size_bytes=size,
        )

    def resolve(self, relative_path: str | Path) -> Path:
        return resolve_storage_path(self.root, relative_path)
