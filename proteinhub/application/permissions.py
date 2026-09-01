from __future__ import annotations

import sqlite3

from proteinhub.domain.errors import NotFoundError, PermissionDeniedError
from proteinhub.infrastructure.sqlite.repositories import (
    ArtifactRepository,
    BatchRepository,
    ProjectRepository,
    ProteinRepository,
    UserRepository,
)


def get_project_role(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> str | None:
    return ProjectRepository(connection).get_role(project_id=project_id, user_id=user_id)


def is_admin(connection: sqlite3.Connection, *, user_id: int) -> bool:
    user = UserRepository(connection).get_public(user_id)
    return bool(
        user
        and user.get("global_role") == "admin"
        and bool(user.get("is_active", 1))
    )


def require_admin(connection: sqlite3.Connection, *, user_id: int) -> None:
    if not is_admin(connection, user_id=user_id):
        raise PermissionDeniedError("Only administrators can perform this action")


def require_project_read(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
) -> str:
    if is_admin(connection, user_id=user_id):
        return "owner"
    role = get_project_role(connection, project_id=project_id, user_id=user_id)
    if role is None:
        raise PermissionDeniedError("You are not a member of this project")
    _require_project_visible_to_user(connection, project_id=project_id)
    return role


def require_project_write(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
) -> str:
    if is_admin(connection, user_id=user_id):
        return "owner"
    role = get_project_role(connection, project_id=project_id, user_id=user_id)
    if role is None:
        raise PermissionDeniedError("You are not a member of this project")
    _require_project_visible_to_user(connection, project_id=project_id)
    return role


def require_project_owner(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
) -> str:
    if is_admin(connection, user_id=user_id):
        return "owner"
    role = get_project_role(connection, project_id=project_id, user_id=user_id)
    if role != "owner":
        raise PermissionDeniedError("Only project owners can perform this action")
    _require_project_visible_to_user(connection, project_id=project_id)
    return role


def _require_project_visible_to_user(
    connection: sqlite3.Connection, *, project_id: int
) -> None:
    project = ProjectRepository(connection).get(project_id)
    if project and project.get("status", "active") == "trash":
        raise PermissionDeniedError("You cannot access projects in the trash")


def require_project_role(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    owner_only: bool = False,
    allow_admin_read: bool = False,
) -> str:
    if owner_only:
        return require_project_owner(
            connection,
            project_id=project_id,
            user_id=user_id,
        )
    if allow_admin_read:
        return require_project_read(
            connection,
            project_id=project_id,
            user_id=user_id,
        )
    return require_project_write(
        connection,
        project_id=project_id,
        user_id=user_id,
    )


def list_visible_batch_ids_for_project(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
) -> set[int] | None:
    role = require_project_read(connection, project_id=project_id, user_id=user_id)
    if role == "owner":
        return None
    return set(
        ProjectRepository(connection).list_member_batch_access_ids(
            project_id=project_id,
            user_id=user_id,
        )
    )


def require_batch_visibility(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
) -> str:
    batch = BatchRepository(connection).get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    project_id = int(batch["project_id"])
    role = require_project_read(connection, project_id=project_id, user_id=user_id)
    if role == "owner":
        return role
    if not ProjectRepository(connection).member_has_batch_access(
        project_id=project_id,
        user_id=user_id,
        batch_id=batch_id,
    ):
        raise PermissionDeniedError("You are not allowed to access this batch")
    return "member"


def project_for_protein(connection: sqlite3.Connection, protein_id: int) -> int:
    project_id = ProteinRepository(connection).project_id_for(protein_id)
    if project_id is None:
        raise NotFoundError("Protein not found")
    return project_id


def project_for_artifact(connection: sqlite3.Connection, artifact_id: int) -> int:
    project_id = ArtifactRepository(connection).project_id_for(artifact_id)
    if project_id is None:
        raise NotFoundError("Artifact not found")
    return project_id
