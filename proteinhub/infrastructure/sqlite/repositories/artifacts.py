from __future__ import annotations

import sqlite3


ARTIFACT_COLUMNS = """
    artifacts.id,
    artifacts.protein_id,
    artifacts.uploaded_by,
    artifacts.filename,
    artifacts.artifact_type,
    artifacts.mime_type,
    artifacts.size_bytes,
    artifacts.storage_path,
    artifacts.storage_backend,
    artifacts.content_sha256,
    artifacts.is_deleted,
    artifacts.created_at,
    artifacts.deleted_at
"""


class ArtifactRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, artifact_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT proteins.project_id AS project_id
            FROM artifacts
            JOIN proteins ON proteins.id = artifacts.protein_id
            WHERE artifacts.id = ? AND artifacts.is_deleted = 0
            """,
            (artifact_id,),
        ).fetchone()
        return int(row["project_id"]) if row else None

    def list_for_protein(self, protein_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                {columns},
                users.name AS uploaded_by_name,
                users.email AS uploaded_by_email
            FROM artifacts
            JOIN users ON users.id = artifacts.uploaded_by
            WHERE artifacts.protein_id = ? AND artifacts.is_deleted = 0
            ORDER BY artifacts.created_at DESC, artifacts.id DESC
            """.format(columns=ARTIFACT_COLUMNS),
            (protein_id,),
        ).fetchall()

    def insert_pending(
        self,
        *,
        protein_id: int,
        uploaded_by: int,
        filename: str,
        artifact_type: str,
        mime_type: str,
        storage_backend: str = "filesystem",
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO artifacts (
                protein_id, uploaded_by, filename, artifact_type,
                mime_type, size_bytes, storage_path, storage_backend
            )
            VALUES (?, ?, ?, ?, ?, 0, '', ?)
            """,
            (
                protein_id,
                uploaded_by,
                filename,
                artifact_type,
                mime_type,
                storage_backend,
            ),
        )
        return int(cursor.lastrowid)

    def mark_stored(
        self,
        *,
        artifact_id: int,
        size_bytes: int,
        storage_path: str,
        storage_backend: str = "filesystem",
    ) -> None:
        self.connection.execute(
            """
            UPDATE artifacts
            SET size_bytes = ?, storage_path = ?, storage_backend = ?
            WHERE id = ?
            """,
            (size_bytes, storage_path, storage_backend, artifact_id),
        )

    def get(self, artifact_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                {columns},
                users.name AS uploaded_by_name,
                users.email AS uploaded_by_email
            FROM artifacts
            JOIN users ON users.id = artifacts.uploaded_by
            WHERE artifacts.id = ? AND artifacts.is_deleted = 0
            """.format(columns=ARTIFACT_COLUMNS),
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
