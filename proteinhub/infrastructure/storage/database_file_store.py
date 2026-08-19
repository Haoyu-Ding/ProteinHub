from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from proteinhub.infrastructure.storage.local_file_store import StoredFile
from proteinhub.infrastructure.storage.paths import (
    artifact_relative_path,
    protein_structure_relative_path,
)


class DatabaseFileStore:
    backend = "database"

    def __init__(self, connection) -> None:
        self.connection = connection

    def save_artifact(
        self,
        *,
        project_id: int,
        protein_id: int,
        artifact_id: int,
        filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        content = _read_all(source)
        relative_path = artifact_relative_path(
            project_id=project_id,
            protein_id=protein_id,
            artifact_id=artifact_id,
            filename=filename,
        )
        digest = hashlib.sha256(content).hexdigest()
        self.connection.execute(
            """
            UPDATE artifacts
            SET
                storage_backend = 'database',
                content = ?,
                content_sha256 = ?
            WHERE id = ?
            """,
            (content, digest, artifact_id),
        )
        return StoredFile(
            relative_path=relative_path.as_posix(),
            absolute_path=Path(relative_path.as_posix()),
            size_bytes=len(content),
        )

    def save_protein_structure(
        self,
        *,
        project_id: int,
        protein_id: int,
        filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        content = _read_all(source)
        relative_path = protein_structure_relative_path(
            project_id=project_id,
            protein_id=protein_id,
            filename=filename,
        )
        digest = hashlib.sha256(content).hexdigest()
        self.connection.execute(
            """
            UPDATE proteins
            SET
                structure_storage_backend = 'database',
                structure_content = ?,
                structure_content_sha256 = ?
            WHERE id = ?
            """,
            (content, digest, protein_id),
        )
        return StoredFile(
            relative_path=relative_path.as_posix(),
            absolute_path=Path(relative_path.as_posix()),
            size_bytes=len(content),
        )

    def read_artifact(self, artifact_id: int) -> bytes | None:
        row = self.connection.execute(
            """
            SELECT content
            FROM artifacts
            WHERE id = ? AND is_deleted = 0
            """,
            (artifact_id,),
        ).fetchone()
        return row["content"] if row and row.get("content") is not None else None

    def read_protein_structure(self, protein_id: int) -> bytes | None:
        row = self.connection.execute(
            """
            SELECT structure_content
            FROM proteins
            WHERE id = ?
            """,
            (protein_id,),
        ).fetchone()
        if not row or row.get("structure_content") is None:
            return None
        return row["structure_content"]

    def replace_artifact(
        self,
        *,
        artifact_id: int,
        storage_path: str,
        content: bytes,
    ) -> StoredFile:
        digest = hashlib.sha256(content).hexdigest()
        self.connection.execute(
            """
            UPDATE artifacts
            SET
                size_bytes = ?,
                storage_path = ?,
                storage_backend = 'database',
                content = ?,
                content_sha256 = ?
            WHERE id = ?
            """,
            (len(content), storage_path, content, digest, artifact_id),
        )
        return StoredFile(
            relative_path=storage_path,
            absolute_path=Path(storage_path),
            size_bytes=len(content),
        )


def _read_all(source: BinaryIO) -> bytes:
    buffer = BytesIO()
    while chunk := source.read(1024 * 1024):
        buffer.write(chunk)
    return buffer.getvalue()
