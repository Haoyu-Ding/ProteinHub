from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import (
    is_admin,
    require_admin,
    require_project_owner,
    require_project_read,
)
from proteinhub.application.validation import required
from proteinhub.domain.errors import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import (
    BatchRepository,
    ProjectRepository,
    UserRepository,
)


PROJECT_STATUSES = {"active", "archived", "trash"}


def list_projects(
    connection: sqlite3.Connection, user_id: int, status: str = "active"
) -> list[dict]:
    project_status = _normalize_project_status(status)
    projects = ProjectRepository(connection)
    if is_admin(connection, user_id=user_id):
        rows = projects.list_all_as_owner(project_status)
    else:
        if project_status == "trash":
            raise PermissionDeniedError("Only administrators can view trash projects")
        rows = projects.list_for_user(user_id, project_status)
    return _with_project_member_summary(projects, rows)


def create_project(
    connection: sqlite3.Connection, *, user_id: int, name: str, description: str = ""
) -> dict:
    project_name = required(name, "Project name")
    projects = ProjectRepository(connection)

    with transaction(connection):
        project_id = projects.insert(
            name=project_name,
            description=description.strip(),
            owner_id=user_id,
        )
        projects.insert_member(
            project_id=project_id,
            user_id=user_id,
            role="owner",
        )

    return get_project(connection, project_id=project_id, user_id=user_id)


def update_project_status(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    status: str,
) -> dict:
    require_admin(connection, user_id=user_id)
    project_status = _normalize_project_status(status)
    projects = ProjectRepository(connection)
    if not projects.get(project_id):
        raise NotFoundError("Project not found")

    with transaction(connection):
        projects.update_status(project_id=project_id, status=project_status)

    return get_project(connection, project_id=project_id, user_id=user_id)


def get_project(connection: sqlite3.Connection, *, project_id: int, user_id: int) -> dict:
    role = require_project_read(connection, project_id=project_id, user_id=user_id)
    project = ProjectRepository(connection).get(project_id)
    if not project:
        raise NotFoundError("Project not found")
    project["role"] = role
    return project


def _with_project_member_summary(
    projects: ProjectRepository, project_rows: list[dict]
) -> list[dict]:
    member_rows = projects.list_members_for_projects(
        [int(project["id"]) for project in project_rows]
    )
    members_by_project_id: dict[int, list[dict]] = {}
    for member in member_rows:
        project_id = int(member["project_id"])
        members_by_project_id.setdefault(project_id, []).append(
            {
                "id": member["id"],
                "name": member["name"],
                "email": member["email"],
            }
        )
    for project in project_rows:
        members = members_by_project_id.get(int(project["id"]), [])
        project["members"] = members
        project["member_count"] = len(members)
    return project_rows


def _normalize_project_status(status: str) -> str:
    normalized = required(status, "Project status").strip().lower()
    if normalized not in PROJECT_STATUSES:
        raise DomainError("Project status must be active, archived, or trash")
    return normalized


def list_project_members(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_read(connection, project_id=project_id, user_id=user_id)
    return ProjectRepository(connection).list_members(project_id)


def search_project_member_candidates(
    connection: sqlite3.Connection, *, project_id: int, owner_user_id: int, query: str
) -> list[dict]:
    require_project_owner(connection, project_id=project_id, user_id=owner_user_id)
    search_text = query.strip()
    if not search_text:
        return []
    return UserRepository(connection).search_available_for_project(
        project_id=project_id, query=search_text
    )


def add_project_member(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    owner_user_id: int,
    email: str,
    role: str = "member",
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=owner_user_id)
    if role != "member":
        raise DomainError("Projects have exactly one owner")

    user = UserRepository(connection).get_by_email(email.strip().lower())
    if not user:
        raise NotFoundError("User not found")
    if not user.get("is_active", 1):
        raise DomainError("User account is disabled")
    projects = ProjectRepository(connection)
    project = projects.get(project_id)
    if not project:
        raise NotFoundError("Project not found")
    if user["id"] == project["owner_id"]:
        raise ConflictError("User is already the project owner")

    try:
        with transaction(connection):
            projects.insert_member(
                project_id=project_id,
                user_id=user["id"],
                role="member",
            )
    except sqlite3.IntegrityError as exc:
        raise ConflictError("User is already a project member") from exc

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "created_at": user["created_at"],
        "role": "member",
    }


def update_project_member(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    owner_user_id: int,
    member_user_id: int,
    role: str,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=owner_user_id)
    if role not in {"owner", "member"}:
        raise DomainError("Role must be owner or member")

    projects = ProjectRepository(connection)
    member = projects.get_member(project_id=project_id, user_id=member_user_id)
    if not member:
        raise NotFoundError("Project member not found")
    if member["role"] == "owner" and role != "owner":
        raise DomainError("Project owner cannot be demoted")
    if member["role"] != "owner" and role == "owner":
        raise DomainError("Projects have exactly one owner")

    with transaction(connection):
        projects.update_member(
            project_id=project_id,
            user_id=member_user_id,
            role=member["role"],
        )

    updated = projects.get_member(project_id=project_id, user_id=member_user_id)
    if not updated:
        raise NotFoundError("Project member not found")
    return updated


def get_project_member_batch_access(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    owner_user_id: int,
    member_user_id: int,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=owner_user_id)
    projects = ProjectRepository(connection)
    project = projects.get(project_id)
    if not project:
        raise NotFoundError("Project not found")
    member = projects.get_member(project_id=project_id, user_id=member_user_id)
    if not member or member["role"] != "member":
        raise NotFoundError("Project member not found")
    return {
        "batch_ids": projects.list_member_batch_access_ids(
            project_id=project_id,
            user_id=member_user_id,
        )
    }


def update_project_member_batch_access(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    owner_user_id: int,
    member_user_id: int,
    batch_ids: list[int],
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=owner_user_id)
    projects = ProjectRepository(connection)
    project = projects.get(project_id)
    if not project:
        raise NotFoundError("Project not found")
    member = projects.get_member(project_id=project_id, user_id=member_user_id)
    if not member or member["role"] != "member":
        raise NotFoundError("Project member not found")

    normalized_batch_ids = []
    for batch_id in batch_ids:
        normalized_batch_id = int(batch_id)
        if normalized_batch_id not in normalized_batch_ids:
            normalized_batch_ids.append(normalized_batch_id)

    valid_batch_ids = {
        int(batch["id"])
        for batch in BatchRepository(connection).list_for_project(project_id)
    }
    invalid_batch_ids = [
        batch_id
        for batch_id in normalized_batch_ids
        if batch_id not in valid_batch_ids
    ]
    if invalid_batch_ids:
        raise DomainError("Batch does not belong to this project")

    with transaction(connection):
        projects.replace_member_batch_access(
            project_id=project_id,
            user_id=member_user_id,
            batch_ids=normalized_batch_ids,
        )

    return {
        "batch_ids": normalized_batch_ids,
    }
