from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from proteinhub.db import transaction
from proteinhub.security import hash_password, verify_password
from proteinhub.storage import artifact_relative_path, resolve_storage_path


class DomainError(Exception):
    status_code = 400
    message = "Bad request"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = 404
    message = "Not found"


class PermissionDeniedError(DomainError):
    status_code = 403
    message = "Permission denied"


class ConflictError(DomainError):
    status_code = 409
    message = "Conflict"


class AuthenticationError(DomainError):
    status_code = 401
    message = "Invalid credentials"


@dataclass(frozen=True)
class UploadedArtifact:
    artifact: dict
    absolute_path: Path


def _required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise DomainError(f"{field_name} is required")
    return cleaned


def get_user(connection: sqlite3.Connection, user_id: int) -> dict:
    user = connection.execute(
        "SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not user:
        raise NotFoundError("User not found")
    return user


def register_user(connection: sqlite3.Connection, email: str, password: str) -> dict:
    normalized_email = _required(email, "Email").lower()
    if len(password) < 8:
        raise DomainError("Password must be at least 8 characters")
    try:
        with transaction(connection):
            cursor = connection.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (normalized_email, hash_password(password)),
            )
        return get_user(connection, int(cursor.lastrowid))
    except sqlite3.IntegrityError as exc:
        raise ConflictError("Email is already registered") from exc


def authenticate_user(connection: sqlite3.Connection, email: str, password: str) -> dict:
    user = connection.execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        raise AuthenticationError()
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


def get_project_role(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> str | None:
    row = connection.execute(
        """
        SELECT role
        FROM project_members
        WHERE project_id = ? AND user_id = ?
        """,
        (project_id, user_id),
    ).fetchone()
    return row["role"] if row else None


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
    row = connection.execute(
        "SELECT project_id FROM proteins WHERE id = ?", (protein_id,)
    ).fetchone()
    if not row:
        raise NotFoundError("Protein not found")
    return int(row["project_id"])


def protein_for_sequence(connection: sqlite3.Connection, sequence_id: int) -> dict:
    row = connection.execute(
        """
        SELECT proteins.id AS protein_id, proteins.project_id AS project_id
        FROM sequences
        JOIN proteins ON proteins.id = sequences.protein_id
        WHERE sequences.id = ?
        """,
        (sequence_id,),
    ).fetchone()
    if not row:
        raise NotFoundError("Sequence not found")
    return row


def project_for_artifact(connection: sqlite3.Connection, artifact_id: int) -> int:
    row = connection.execute(
        """
        SELECT proteins.project_id AS project_id
        FROM artifacts
        JOIN sequences ON sequences.id = artifacts.sequence_id
        JOIN proteins ON proteins.id = sequences.protein_id
        WHERE artifacts.id = ? AND artifacts.is_deleted = 0
        """,
        (artifact_id,),
    ).fetchone()
    if not row:
        raise NotFoundError("Artifact not found")
    return int(row["project_id"])


def list_projects(connection: sqlite3.Connection, user_id: int) -> list[dict]:
    return connection.execute(
        """
        SELECT projects.*, project_members.role
        FROM projects
        JOIN project_members ON project_members.project_id = projects.id
        WHERE project_members.user_id = ?
        ORDER BY projects.created_at DESC, projects.id DESC
        """,
        (user_id,),
    ).fetchall()


def create_project(
    connection: sqlite3.Connection, *, user_id: int, name: str, description: str = ""
) -> dict:
    project_name = _required(name, "Project name")
    with transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO projects (name, description, owner_id)
            VALUES (?, ?, ?)
            """,
            (project_name, description.strip(), user_id),
        )
        project_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (?, ?, 'owner')
            """,
            (project_id, user_id),
        )
    return get_project(connection, project_id=project_id, user_id=user_id)


def get_project(connection: sqlite3.Connection, *, project_id: int, user_id: int) -> dict:
    role = require_project_role(connection, project_id=project_id, user_id=user_id)
    project = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not project:
        raise NotFoundError("Project not found")
    project["role"] = role
    return project


def list_project_members(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return connection.execute(
        """
        SELECT users.id, users.email, project_members.role, project_members.created_at
        FROM project_members
        JOIN users ON users.id = project_members.user_id
        WHERE project_members.project_id = ?
        ORDER BY project_members.role DESC, users.email
        """,
        (project_id,),
    ).fetchall()


def add_project_member(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    owner_user_id: int,
    email: str,
    role: str = "member",
) -> dict:
    require_project_role(
        connection, project_id=project_id, user_id=owner_user_id, owner_only=True
    )
    if role not in {"owner", "member"}:
        raise DomainError("Role must be owner or member")
    user = connection.execute(
        "SELECT id, email, created_at FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    if not user:
        raise NotFoundError("User not found")
    try:
        with transaction(connection):
            connection.execute(
                """
                INSERT INTO project_members (project_id, user_id, role)
                VALUES (?, ?, ?)
                """,
                (project_id, user["id"], role),
            )
    except sqlite3.IntegrityError as exc:
        raise ConflictError("User is already a project member") from exc
    return user | {"role": role}


def list_proteins(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return connection.execute(
        """
        SELECT *
        FROM proteins
        WHERE project_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (project_id,),
    ).fetchall()


def create_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    name: str,
    description: str = "",
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein_name = _required(name, "Protein name")
    with transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO proteins (project_id, name, description)
            VALUES (?, ?, ?)
            """,
            (project_id, protein_name, description.strip()),
        )
    return get_protein(connection, protein_id=int(cursor.lastrowid), user_id=user_id)


def get_protein(connection: sqlite3.Connection, *, protein_id: int, user_id: int) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein = connection.execute(
        "SELECT * FROM proteins WHERE id = ?", (protein_id,)
    ).fetchone()
    if not protein:
        raise NotFoundError("Protein not found")
    return protein


def list_sequences(
    connection: sqlite3.Connection, *, protein_id: int, user_id: int
) -> list[dict]:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return connection.execute(
        """
        SELECT *
        FROM sequences
        WHERE protein_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (protein_id,),
    ).fetchall()


def create_sequence(
    connection: sqlite3.Connection,
    *,
    protein_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str = "",
    version_tag: str = "",
) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    sequence_name = _required(name, "Sequence name")
    sequence_text = _required(sequence, "Sequence").upper().replace(" ", "").replace("\n", "")
    with transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO sequences (protein_id, name, sequence, description, version_tag)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                protein_id,
                sequence_name,
                sequence_text,
                description.strip(),
                version_tag.strip(),
            ),
        )
    return get_sequence(connection, sequence_id=int(cursor.lastrowid), user_id=user_id)


def get_sequence(
    connection: sqlite3.Connection, *, sequence_id: int, user_id: int
) -> dict:
    relation = protein_for_sequence(connection, sequence_id)
    require_project_role(connection, project_id=relation["project_id"], user_id=user_id)
    sequence = connection.execute(
        """
        SELECT sequences.*, proteins.project_id
        FROM sequences
        JOIN proteins ON proteins.id = sequences.protein_id
        WHERE sequences.id = ?
        """,
        (sequence_id,),
    ).fetchone()
    if not sequence:
        raise NotFoundError("Sequence not found")
    return sequence


def list_artifacts(
    connection: sqlite3.Connection, *, sequence_id: int, user_id: int
) -> list[dict]:
    relation = protein_for_sequence(connection, sequence_id)
    require_project_role(connection, project_id=relation["project_id"], user_id=user_id)
    return connection.execute(
        """
        SELECT artifacts.*, users.email AS uploaded_by_email
        FROM artifacts
        JOIN users ON users.id = artifacts.uploaded_by
        WHERE artifacts.sequence_id = ? AND artifacts.is_deleted = 0
        ORDER BY artifacts.created_at DESC, artifacts.id DESC
        """,
        (sequence_id,),
    ).fetchall()


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
) -> UploadedArtifact:
    relation = protein_for_sequence(connection, sequence_id)
    project_id = int(relation["project_id"])
    require_project_role(connection, project_id=project_id, user_id=user_id)
    file_name = _required(filename, "Filename")
    mime_type = content_type or "application/octet-stream"

    with transaction(connection):
        cursor = connection.execute(
            """
            INSERT INTO artifacts (
                sequence_id, uploaded_by, filename, artifact_type,
                mime_type, size_bytes, storage_path
            )
            VALUES (?, ?, ?, ?, ?, 0, '')
            """,
            (sequence_id, user_id, file_name, artifact_type.strip() or "file", mime_type),
        )
        artifact_id = int(cursor.lastrowid)
        relative_path = artifact_relative_path(
            project_id=project_id,
            sequence_id=sequence_id,
            artifact_id=artifact_id,
            filename=file_name,
        )
        absolute_path = resolve_storage_path(storage_root, relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with absolute_path.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                output.write(chunk)
        connection.execute(
            """
            UPDATE artifacts
            SET size_bytes = ?, storage_path = ?
            WHERE id = ?
            """,
            (size, relative_path.as_posix(), artifact_id),
        )
    artifact = get_artifact(connection, artifact_id=artifact_id, user_id=user_id)
    return UploadedArtifact(artifact=artifact, absolute_path=absolute_path)


def get_artifact(
    connection: sqlite3.Connection, *, artifact_id: int, user_id: int
) -> dict:
    project_id = project_for_artifact(connection, artifact_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    artifact = connection.execute(
        """
        SELECT artifacts.*, users.email AS uploaded_by_email
        FROM artifacts
        JOIN users ON users.id = artifacts.uploaded_by
        WHERE artifacts.id = ? AND artifacts.is_deleted = 0
        """,
        (artifact_id,),
    ).fetchone()
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
        connection.execute(
            """
            UPDATE artifacts
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (artifact_id,),
        )

