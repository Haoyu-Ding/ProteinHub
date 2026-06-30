from __future__ import annotations

import sqlite3

from proteinhub.domain.errors import NotFoundError, PermissionDeniedError
from proteinhub.infrastructure.sqlite.repositories import (
    ArtifactRepository,
    ProjectRepository,
    ProteinRepository,
    SequenceRepository,
)


def get_project_role(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> str | None:
    return ProjectRepository(connection).get_role(project_id=project_id, user_id=user_id)


def require_project_role(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    owner_only: bool = False,
) -> str:
    role = get_project_role(connection, project_id=project_id, user_id=user_id)
    if role is None:
        raise PermissionDeniedError("You are not a member of this project")
    if owner_only and role != "owner":
        raise PermissionDeniedError("Only project owners can perform this action")
    return role


def project_for_protein(connection: sqlite3.Connection, protein_id: int) -> int:
    project_id = ProteinRepository(connection).project_id_for(protein_id)
    if project_id is None:
        raise NotFoundError("Protein not found")
    return project_id


def protein_for_sequence(connection: sqlite3.Connection, sequence_id: int) -> dict:
    relation = SequenceRepository(connection).protein_relation_for(sequence_id)
    if not relation:
        raise NotFoundError("Sequence not found")
    return relation


def project_for_artifact(connection: sqlite3.Connection, artifact_id: int) -> int:
    project_id = ArtifactRepository(connection).project_id_for(artifact_id)
    if project_id is None:
        raise NotFoundError("Artifact not found")
    return project_id

