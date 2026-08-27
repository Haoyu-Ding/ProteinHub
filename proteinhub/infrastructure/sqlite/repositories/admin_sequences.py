from __future__ import annotations

import sqlite3


class AdminSequenceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def search_sequences(
        self,
        *,
        sequence_query: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        pattern = f"%{sequence_query}%"
        return self.connection.execute(
            """
            SELECT
                'batch_protein' AS source_type,
                proteins.id AS protein_id,
                NULL AS public_protein_id,
                proteins.project_id,
                projects.name AS project_name,
                projects.status AS project_status,
                proteins.name AS name,
                proteins.sequence AS sequence,
                LENGTH(proteins.sequence) AS sequence_length,
                proteins.protein_type AS protein_type,
                proteins.target AS target,
                proteins.updated_at AS updated_at,
                (
                    SELECT COUNT(DISTINCT batch_wells.batch_id)
                    FROM batch_wells
                    WHERE batch_wells.protein_id = proteins.id
                ) AS batch_count
            FROM proteins
            JOIN projects ON projects.id = proteins.project_id
            WHERE EXISTS (
                SELECT 1
                FROM batch_wells
                WHERE batch_wells.protein_id = proteins.id
            )
              AND (? = '' OR UPPER(proteins.sequence) LIKE ?)

            UNION ALL

            SELECT
                'public_protein' AS source_type,
                NULL AS protein_id,
                public_proteins.id AS public_protein_id,
                public_proteins.project_id,
                projects.name AS project_name,
                projects.status AS project_status,
                public_proteins.name AS name,
                public_proteins.sequence AS sequence,
                LENGTH(public_proteins.sequence) AS sequence_length,
                public_proteins.protein_type AS protein_type,
                public_proteins.target AS target,
                public_proteins.updated_at AS updated_at,
                0 AS batch_count
            FROM public_proteins
            JOIN projects ON projects.id = public_proteins.project_id
            WHERE (? = '' OR UPPER(public_proteins.sequence) LIKE ?)

            ORDER BY updated_at DESC, source_type ASC, name ASC
            LIMIT ? OFFSET ?
            """,
            (
                sequence_query,
                pattern,
                sequence_query,
                pattern,
                limit,
                offset,
            ),
        ).fetchall()
