from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from proteinhub.application.permissions import (
    project_for_artifact,
    protein_for_sequence,
    require_project_role,
)
from proteinhub.application.validation import required
from proteinhub.domain.errors import NotFoundError
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import ArtifactRepository
from proteinhub.infrastructure.storage.local_file_store import LocalFileStore


@dataclass(frozen=True)
class UploadedArtifact:
    artifact: dict
    absolute_path: Path


def list_artifacts(
    connection: sqlite3.Connection, *, sequence_id: int, user_id: int
) -> list[dict]:
    relation = protein_for_sequence(connection, sequence_id)
    require_project_role(connection, project_id=relation["project_id"], user_id=user_id)
    return ArtifactRepository(connection).list_for_sequence(sequence_id)


def create_artifact(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    sequence_id: int,
    user_id: int,
    filename: str,
    content_type: str,
    source: BinaryIO,
    artifact_type: str = "file",
    file_store: LocalFileStore | None = None,
) -> UploadedArtifact:
    relation = protein_for_sequence(connection, sequence_id)
    project_id = int(relation["project_id"])
    require_project_role(connection, project_id=project_id, user_id=user_id)
    file_name = required(filename, "Filename")
    mime_type = content_type or "application/octet-stream"
    store = file_store or LocalFileStore(storage_root)
    artifacts = ArtifactRepository(connection)

    with transaction(connection):
        artifact_id = artifacts.insert_pending(
            sequence_id=sequence_id,
            uploaded_by=user_id,
            filename=file_name,
            artifact_type=artifact_type.strip() or "file",
            mime_type=mime_type,
        )
        stored = store.save_artifact(
            project_id=project_id,
            sequence_id=sequence_id,
            artifact_id=artifact_id,
            filename=file_name,
            source=source,
        )
        artifacts.mark_stored(
            artifact_id=artifact_id,
            size_bytes=stored.size_bytes,
            storage_path=stored.relative_path,
        )

    artifact = get_artifact(connection, artifact_id=artifact_id, user_id=user_id)
    return UploadedArtifact(artifact=artifact, absolute_path=stored.absolute_path)


def get_artifact(
    connection: sqlite3.Connection, *, artifact_id: int, user_id: int
) -> dict:
    project_id = project_for_artifact(connection, artifact_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    artifact = ArtifactRepository(connection).get(artifact_id)
    if not artifact:
        raise NotFoundError("Artifact not found")
    return artifact


def soft_delete_artifact(
    connection: sqlite3.Connection, *, artifact_id: int, user_id: int
) -> None:
    project_id = project_for_artifact(connection, artifact_id)
    require_project_role(
        connection, project_id=project_id, user_id=user_id, owner_only=True
    )
    with transaction(connection):
        ArtifactRepository(connection).soft_delete(artifact_id)
