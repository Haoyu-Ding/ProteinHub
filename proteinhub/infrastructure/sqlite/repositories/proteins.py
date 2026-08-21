from __future__ import annotations

import json
import sqlite3

DEFAULT_MANUAL_RATING = "unrated"
EFFECTIVE_DATE_SQL = (
    "COALESCE(NULLIF(proteins.structure_deposit_date, ''), substr(proteins.created_at, 1, 10))"
)
EFFECTIVE_DATE_SOURCE_SQL = """
    CASE
        WHEN proteins.structure_deposit_date != '' THEN 'pdb_deposit'
        ELSE 'created_at'
    END
"""
MANUAL_RATING_RANK_SQL = """
    CASE proteins.manual_rating
        WHEN 'legendary' THEN 5
        WHEN 'epic' THEN 4
        WHEN 'rare' THEN 3
        WHEN 'normal' THEN 2
        ELSE 1
    END
"""
PROTEIN_COLUMNS = """
    proteins.id,
    proteins.project_id,
    proteins.name,
    proteins.sequence,
    proteins.dna_sequence,
    proteins.description,
    proteins.protein_type,
    proteins.target,
    proteins.manual_rating,
    proteins.score_details_json,
    proteins.sequence_similarity_status,
    proteins.sequence_similarity_matches_json,
    proteins.structure_filename,
    proteins.structure_mime_type,
    proteins.structure_size_bytes,
    proteins.structure_storage_path,
    proteins.structure_storage_backend,
    proteins.structure_content_sha256,
    proteins.structure_deposit_date,
    proteins.created_at,
    proteins.updated_at
"""


class ProteinRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, protein_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT project_id FROM proteins WHERE id = ?", (protein_id,)
        ).fetchone()
        return int(row["project_id"]) if row else None

    def list_for_project(
        self,
        project_id: int,
        *,
        manual_ratings: tuple[str, ...] = (),
        date_from: str = "",
        date_to: str = "",
        sort: str = "time_desc",
    ) -> list[dict]:
        filters = ["proteins.project_id = ?"]
        args: list[object] = [project_id]
        if manual_ratings:
            placeholders = ",".join("?" for _ in manual_ratings)
            filters.append(f"proteins.manual_rating IN ({placeholders})")
            args.extend(manual_ratings)
        if date_from:
            filters.append(f"{EFFECTIVE_DATE_SQL} >= ?")
            args.append(date_from)
        if date_to:
            filters.append(f"{EFFECTIVE_DATE_SQL} <= ?")
            args.append(date_to)

        rows = self.connection.execute(
            f"""
            SELECT
                {PROTEIN_COLUMNS},
                proteins.name AS protein_name,
                COUNT(artifacts.id) AS artifact_count,
                {EFFECTIVE_DATE_SQL} AS effective_date,
                {EFFECTIVE_DATE_SOURCE_SQL} AS effective_date_source,
                {MANUAL_RATING_RANK_SQL} AS manual_rating_rank
            FROM proteins
            LEFT JOIN artifacts
                ON artifacts.protein_id = proteins.id AND artifacts.is_deleted = 0
            WHERE {" AND ".join(filters)}
            GROUP BY proteins.id
            ORDER BY {_protein_list_order_by(sort)}
            """,
            tuple(args),
        ).fetchall()
        return [self._with_score_details(row) for row in rows]

    def list_sequences_for_project(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT id, name, sequence
            FROM proteins
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
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
        protein_type: str,
        target: str,
        manual_rating: str = DEFAULT_MANUAL_RATING,
        score_details: dict[str, str] | None = None,
        sequence_similarity_status: str = "",
        sequence_similarity_matches: list[dict] | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO proteins (
                project_id,
                name,
                sequence,
                dna_sequence,
                description,
                protein_type,
                target,
                manual_rating,
                score_details_json,
                sequence_similarity_status,
                sequence_similarity_matches_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                project_id,
                name,
                sequence,
                dna_sequence,
                description,
                protein_type,
                target,
                manual_rating,
                json.dumps(score_details or {}, ensure_ascii=False),
                sequence_similarity_status,
                json.dumps(sequence_similarity_matches or [], ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)

    def get(self, protein_id: int) -> dict | None:
        return self.get_with_project(protein_id)

    def get_with_project(self, protein_id: int) -> dict | None:
        row = self.connection.execute(
            f"""
            SELECT
                {PROTEIN_COLUMNS},
                proteins.name AS protein_name,
                COALESCE(NULLIF(proteins.structure_deposit_date, ''), substr(proteins.created_at, 1, 10)) AS effective_date,
                CASE
                    WHEN proteins.structure_deposit_date != '' THEN 'pdb_deposit'
                    ELSE 'created_at'
                END AS effective_date_source
            FROM proteins
            WHERE proteins.id = ?
            """,
            (protein_id,),
        ).fetchone()
        return self._with_score_details(row) if row else None

    def _with_score_details(self, protein: dict) -> dict:
        details_text = protein.pop("score_details_json", "") or "{}"
        try:
            details = json.loads(details_text)
        except json.JSONDecodeError:
            details = {}
        protein["score_details"] = details if isinstance(details, dict) else {}
        matches_text = protein.pop("sequence_similarity_matches_json", "") or "[]"
        try:
            matches = json.loads(matches_text)
        except json.JSONDecodeError:
            matches = []
        protein["sequence_similarity_matches"] = matches if isinstance(matches, list) else []
        protein.pop("manual_rating_rank", None)
        return protein

    def update_sequence(
        self,
        *,
        protein_id: int,
        name: str,
        sequence: str,
        dna_sequence: str,
        description: str,
        protein_type: str,
        target: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE proteins
            SET
                name = ?,
                sequence = ?,
                dna_sequence = ?,
                description = ?,
                protein_type = ?,
                target = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, sequence, dna_sequence, description, protein_type, target, protein_id),
        )

    def update_structure_file(
        self,
        *,
        protein_id: int,
        filename: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        storage_backend: str = "filesystem",
        deposit_date: str = "",
    ) -> None:
        self.connection.execute(
            """
            UPDATE proteins
            SET
                structure_filename = ?,
                structure_mime_type = ?,
                structure_size_bytes = ?,
                structure_storage_path = ?,
                structure_storage_backend = ?,
                structure_deposit_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                filename,
                mime_type,
                size_bytes,
                storage_path,
                storage_backend,
                deposit_date,
                protein_id,
            ),
        )

    def update_manual_rating(self, *, protein_id: int, manual_rating: str) -> None:
        self.connection.execute(
            """
            UPDATE proteins
            SET
                manual_rating = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (manual_rating, protein_id),
        )

    def update_score_details(
        self, *, protein_id: int, score_details: dict[str, str]
    ) -> None:
        self.connection.execute(
            """
            UPDATE proteins
            SET
                score_details_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(score_details, ensure_ascii=False), protein_id),
        )


def _protein_list_order_by(sort: str) -> str:
    orders = {
        "time_desc": "effective_date DESC, proteins.created_at DESC, proteins.id DESC",
        "time_asc": "effective_date ASC, proteins.created_at ASC, proteins.id ASC",
        "created_desc": "proteins.created_at DESC, proteins.id DESC",
        "created_asc": "proteins.created_at ASC, proteins.id ASC",
        "effective_date_desc": "effective_date DESC, proteins.created_at DESC, proteins.id DESC",
        "effective_date_asc": "effective_date ASC, proteins.created_at ASC, proteins.id ASC",
        "rating_desc": "manual_rating_rank DESC, effective_date DESC, proteins.id DESC",
        "rating_asc": "manual_rating_rank ASC, effective_date DESC, proteins.id DESC",
    }
    return orders.get(sort, orders["time_desc"])
