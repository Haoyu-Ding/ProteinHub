from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import (
    is_admin,
    require_admin,
    require_project_owner,
    require_project_read,
)
from proteinhub.application.validation import required
from proteinhub.domain.errors import ConflictError, DomainError, NotFoundError
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import ProjectRepository, UserRepository


def list_projects(connection: sqlite3.Connection, user_id: int) -> list[dict]:
    projects = ProjectRepository(connection)
    if is_admin(connection, user_id=user_id):
        return projects.list_all_as_owner()
    return projects.list_for_user(user_id)


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


def delete_project(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> None:
    require_admin(connection, user_id=user_id)
    projects = ProjectRepository(connection)
    if not projects.get(project_id):
        raise NotFoundError("Project not found")

    with transaction(connection):
        projects.delete(project_id)


def get_project(connection: sqlite3.Connection, *, project_id: int, user_id: int) -> dict:
    role = require_project_read(connection, project_id=project_id, user_id=user_id)
    project = ProjectRepository(connection).get(project_id)
    if not project:
        raise NotFoundError("Project not found")
    project["role"] = role
    return project


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
