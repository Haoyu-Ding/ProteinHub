from __future__ import annotations

import sqlite3


class UserRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_public(self, user_id: int) -> dict | None:
        return self.connection.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    def get_by_email(self, email: str) -> dict | None:
        return self.connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    def insert(self, *, email: str, password_hash: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        return int(cursor.lastrowid)


class ProjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_role(self, *, project_id: int, user_id: int) -> str | None:
        row = self.connection.execute(
            """
            SELECT role
            FROM project_members
            WHERE project_id = ? AND user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()
        return row["role"] if row else None

    def list_for_user(self, user_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT projects.*, project_members.role
            FROM projects
            JOIN project_members ON project_members.project_id = projects.id
            WHERE project_members.user_id = ?
            ORDER BY projects.created_at DESC, projects.id DESC
            """,
            (user_id,),
        ).fetchall()

    def insert(self, *, name: str, description: str, owner_id: int) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO projects (name, description, owner_id)
            VALUES (?, ?, ?)
            """,
            (name, description, owner_id),
        )
        return int(cursor.lastrowid)

    def get(self, project_id: int) -> dict | None:
        return self.connection.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    def insert_member(self, *, project_id: int, user_id: int, role: str) -> None:
        self.connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (?, ?, ?)
            """,
            (project_id, user_id, role),
        )

    def list_members(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT users.id, users.email, project_members.role, project_members.created_at
            FROM project_members
            JOIN users ON users.id = project_members.user_id
            WHERE project_members.project_id = ?
            ORDER BY project_members.role DESC, users.email
            """,
            (project_id,),
        ).fetchall()


class ProteinRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, protein_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT project_id FROM proteins WHERE id = ?", (protein_id,)
        ).fetchone()
        return int(row["project_id"]) if row else None

    def list_for_project(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT *
            FROM proteins
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()

    def insert(self, *, project_id: int, name: str, description: str) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO proteins (project_id, name, description)
            VALUES (?, ?, ?)
            """,
            (project_id, name, description),
        )
        return int(cursor.lastrowid)

    def get(self, protein_id: int) -> dict | None:
        return self.connection.execute(
            "SELECT * FROM proteins WHERE id = ?", (protein_id,)
        ).fetchone()


class SequenceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def protein_relation_for(self, sequence_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT proteins.id AS protein_id, proteins.project_id AS project_id
            FROM sequences
            JOIN proteins ON proteins.id = sequences.protein_id
            WHERE sequences.id = ?
            """,
            (sequence_id,),
        ).fetchone()

    def list_for_protein(self, protein_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT *
            FROM sequences
            WHERE protein_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (protein_id,),
        ).fetchall()

    def insert(
        self,
        *,
        protein_id: int,
        name: str,
        sequence: str,
        description: str,
        version_tag: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO sequences (protein_id, name, sequence, description, version_tag)
            VALUES (?, ?, ?, ?, ?)
            """,
            (protein_id, name, sequence, description, version_tag),
        )
        return int(cursor.lastrowid)

    def get_with_project(self, sequence_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT sequences.*, proteins.project_id
            FROM sequences
            JOIN proteins ON proteins.id = sequences.protein_id
            WHERE sequences.id = ?
            """,
            (sequence_id,),
        ).fetchone()


class ArtifactRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, artifact_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT proteins.project_id AS project_id
            FROM artifacts
            JOIN sequences ON sequences.id = artifacts.sequence_id
            JOIN proteins ON proteins.id = sequences.protein_id
            WHERE artifacts.id = ? AND artifacts.is_deleted = 0
            """,
            (artifact_id,),
        ).fetchone()
        return int(row["project_id"]) if row else None

    def list_for_sequence(self, sequence_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT artifacts.*, users.email AS uploaded_by_email
            FROM artifacts
            JOIN users ON users.id = artifacts.uploaded_by
            WHERE artifacts.sequence_id = ? AND artifacts.is_deleted = 0
            ORDER BY artifacts.created_at DESC, artifacts.id DESC
            """,
            (sequence_id,),
        ).fetchall()

    def insert_pending(
        self,
        *,
        sequence_id: int,
        uploaded_by: int,
        filename: str,
        artifact_type: str,
        mime_type: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO artifacts (
                sequence_id, uploaded_by, filename, artifact_type,
                mime_type, size_bytes, storage_path
            )
            VALUES (?, ?, ?, ?, ?, 0, '')
            """,
            (sequence_id, uploaded_by, filename, artifact_type, mime_type),
        )
        return int(cursor.lastrowid)

    def mark_stored(self, *, artifact_id: int, size_bytes: int, storage_path: str) -> None:
        self.connection.execute(
            """
            UPDATE artifacts
            SET size_bytes = ?, storage_path = ?
            WHERE id = ?
            """,
            (size_bytes, storage_path, artifact_id),
        )

    def get(self, artifact_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT artifacts.*, users.email AS uploaded_by_email
            FROM artifacts
            JOIN users ON users.id = artifacts.uploaded_by
            WHERE artifacts.id = ? AND artifacts.is_deleted = 0
            """,
            (artifact_id,),
        ).fetchone()

    def soft_delete(self, artifact_id: int) -> None:
        self.connection.execute(
            """
            UPDATE artifacts
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (artifact_id,),
        )

