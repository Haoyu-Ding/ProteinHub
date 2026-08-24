from __future__ import annotations

import sqlite3


PUBLIC_PROTEIN_COLUMNS = """
    public_proteins.id,
    public_proteins.project_id,
    public_proteins.name,
    public_proteins.sequence,
    public_proteins.description,
    public_proteins.protein_type,
    public_proteins.target,
    public_proteins.created_by,
    public_proteins.created_at,
    public_proteins.updated_at
"""


class PublicProteinRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, public_protein_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT project_id FROM public_proteins WHERE id = ?",
            (public_protein_id,),
        ).fetchone()
        return int(row["project_id"]) if row else None

    def list_for_project(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            f"""
            SELECT
                {PUBLIC_PROTEIN_COLUMNS},
                users.name AS created_by_name,
                users.email AS created_by_email
            FROM public_proteins
            JOIN users ON users.id = public_proteins.created_by
            WHERE public_proteins.project_id = ?
            ORDER BY public_proteins.created_at DESC, public_proteins.id DESC
            """,
            (project_id,),
        ).fetchall()

    def insert(
        self,
        *,
        project_id: int,
        name: str,
        sequence: str,
        description: str,
        protein_type: str,
        target: str,
        created_by: int,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO public_proteins (
                project_id,
                name,
                sequence,
                description,
                protein_type,
                target,
                created_by,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                project_id,
                name,
                sequence,
                description,
                protein_type,
                target,
                created_by,
            ),
        )
        return int(cursor.lastrowid)

    def get(self, public_protein_id: int) -> dict | None:
        return self.connection.execute(
            f"""
            SELECT
                {PUBLIC_PROTEIN_COLUMNS},
                users.name AS created_by_name,
                users.email AS created_by_email
            FROM public_proteins
            JOIN users ON users.id = public_proteins.created_by
            WHERE public_proteins.id = ?
            """,
            (public_protein_id,),
        ).fetchone()

    def update(
        self,
        *,
        public_protein_id: int,
        name: str,
        sequence: str,
        description: str,
        protein_type: str,
        target: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE public_proteins
            SET
                name = ?,
                sequence = ?,
                description = ?,
                protein_type = ?,
                target = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                name,
                sequence,
                description,
                protein_type,
                target,
                public_protein_id,
            ),
        )

    def delete(self, public_protein_id: int) -> None:
        self.connection.execute(
            "DELETE FROM public_proteins WHERE id = ?",
            (public_protein_id,),
        )
