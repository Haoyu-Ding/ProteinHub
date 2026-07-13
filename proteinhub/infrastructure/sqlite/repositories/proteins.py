from __future__ import annotations

import sqlite3


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
            SELECT
                proteins.*,
                proteins.name AS protein_name,
                COUNT(artifacts.id) AS artifact_count
            FROM proteins
            LEFT JOIN artifacts
                ON artifacts.protein_id = proteins.id AND artifacts.is_deleted = 0
            WHERE proteins.project_id = ?
            GROUP BY proteins.id
            ORDER BY proteins.created_at DESC, proteins.id DESC
            """,
            (project_id,),
        ).fetchall()

    def existing_ids_for_project(self, *, project_id: int, protein_ids: set[int]) -> set[int]:
        if not protein_ids:
            return set()
        placeholders = ",".join("?" for _ in protein_ids)
        rows = self.connection.execute(
            f"""
            SELECT id
            FROM proteins
            WHERE project_id = ? AND id IN ({placeholders})
            """,
            (project_id, *protein_ids),
        ).fetchall()
        return {int(row["id"]) for row in rows}

    def insert(
        self,
        *,
        project_id: int,
        name: str,
        sequence: str,
        dna_sequence: str,
        description: str,
        version_tag: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO proteins (
                project_id, name, sequence, dna_sequence, description, version_tag, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (project_id, name, sequence, dna_sequence, description, version_tag),
        )
        return int(cursor.lastrowid)

    def get(self, protein_id: int) -> dict | None:
        return self.get_with_project(protein_id)

    def get_with_project(self, protein_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                proteins.*,
                proteins.name AS protein_name
            FROM proteins
            WHERE proteins.id = ?
            """,
            (protein_id,),
        ).fetchone()

    def update_sequence(
        self,
        *,
        protein_id: int,
        name: str,
        sequence: str,
        dna_sequence: str,
        description: str,
        version_tag: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE proteins
            SET
                name = ?,
                sequence = ?,
                dna_sequence = ?,
                description = ?,
                version_tag = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, sequence, dna_sequence, description, version_tag, protein_id),
        )
