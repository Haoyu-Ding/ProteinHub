from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from proteinhub.application.permissions import (
    project_for_artifact,
    project_for_protein,
    require_project_owner,
)
from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import ArtifactRepository
from proteinhub.infrastructure.storage.file_store import file_store_for


@dataclass(frozen=True)
class UploadedArtifact:
    artifact: dict
    absolute_path: Path


ARTIFACT_TYPES = {
    "design_output",
    "structure_model",
    "synthesis_protocol",
    "experimental_result",
    "analysis_report",
    "other",
    "file",
}


def list_artifacts(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    protein_id: int,
) -> list[dict]:
    project_id = project_for_protein(connection, protein_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    return ArtifactRepository(connection).list_for_protein(protein_id)


def create_artifact(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    user_id: int,
    filename: str,
    content_type: str,
    source: BinaryIO,
    protein_id: int,
    artifact_type: str = "file",
    file_store=None,
) -> UploadedArtifact:
    project_id = project_for_protein(connection, protein_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    file_name = required(filename, "Filename")
    mime_type = content_type or "application/octet-stream"
    normalized_type = artifact_type.strip() or "other"
    if normalized_type not in ARTIFACT_TYPES:
        raise DomainError("Artifact type is not supported")
    store = file_store or file_store_for(connection, storage_root)
    artifacts = ArtifactRepository(connection)

    with transaction(connection):
        artifact_id = artifacts.insert_pending(
            protein_id=protein_id,
            uploaded_by=user_id,
            filename=file_name,
            artifact_type=normalized_type,
            mime_type=mime_type,
            storage_backend=getattr(store, "backend", "filesystem"),
        )
        stored = store.save_artifact(
            project_id=project_id,
            protein_id=protein_id,
            artifact_id=artifact_id,
            filename=file_name,
            source=source,
        )
        artifacts.mark_stored(
            artifact_id=artifact_id,
            size_bytes=stored.size_bytes,
            storage_path=stored.relative_path,
            storage_backend=getattr(store, "backend", "filesystem"),
        )

    artifact = get_artifact(connection, artifact_id=artifact_id, user_id=user_id)
    return UploadedArtifact(artifact=artifact, absolute_path=stored.absolute_path)


def get_artifact(
    connection: sqlite3.Connection, *, artifact_id: int, user_id: int
) -> dict:
    project_id = project_for_artifact(connection, artifact_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    artifact = ArtifactRepository(connection).get(artifact_id)
    if not artifact:
        raise NotFoundError("Artifact not found")
    return artifact


def soft_delete_artifact(
    connection: sqlite3.Connection, *, artifact_id: int, user_id: int
) -> None:
    project_id = project_for_artifact(connection, artifact_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    with transaction(connection):
        ArtifactRepository(connection).soft_delete(artifact_id)
