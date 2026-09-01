from __future__ import annotations

import hashlib
import sqlite3


RAW_FILE_COLUMNS = """
    experiment_raw_files.id,
    experiment_raw_files.experiment_id,
    experiment_raw_files.uploaded_by,
    experiment_raw_files.well_id,
    experiment_raw_files.filename,
    experiment_raw_files.raw_file_type,
    experiment_raw_files.mime_type,
    experiment_raw_files.size_bytes,
    experiment_raw_files.content_sha256,
    experiment_raw_files.created_at
"""


class ExperimentRawFileRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, raw_file_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT batches.project_id AS project_id
            FROM experiment_raw_files
            JOIN batch_experiments
                ON batch_experiments.id = experiment_raw_files.experiment_id
            JOIN batches ON batches.id = batch_experiments.batch_id
            WHERE experiment_raw_files.id = ?
            """,
            (raw_file_id,),
        ).fetchone()
        return int(row["project_id"]) if row else None

    def batch_id_for(self, raw_file_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT batch_experiments.batch_id AS batch_id
            FROM experiment_raw_files
            JOIN batch_experiments
                ON batch_experiments.id = experiment_raw_files.experiment_id
            WHERE experiment_raw_files.id = ?
            """,
            (raw_file_id,),
        ).fetchone()
        return int(row["batch_id"]) if row else None

    def list_for_experiment(self, experiment_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                {columns},
                batch_wells.position,
                batch_wells.protein_id,
                proteins.name AS protein_name,
                users.name AS uploaded_by_name,
                users.email AS uploaded_by_email
            FROM experiment_raw_files
            JOIN users ON users.id = experiment_raw_files.uploaded_by
            LEFT JOIN batch_wells ON batch_wells.id = experiment_raw_files.well_id
            LEFT JOIN proteins ON proteins.id = batch_wells.protein_id
            WHERE experiment_raw_files.experiment_id = ?
            ORDER BY experiment_raw_files.created_at DESC, experiment_raw_files.id DESC
            """.format(columns=RAW_FILE_COLUMNS),
            (experiment_id,),
        ).fetchall()

    def get(self, raw_file_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                {columns},
                batch_wells.position,
                batch_wells.protein_id,
                proteins.name AS protein_name,
                users.name AS uploaded_by_name,
                users.email AS uploaded_by_email
            FROM experiment_raw_files
            JOIN users ON users.id = experiment_raw_files.uploaded_by
            LEFT JOIN batch_wells ON batch_wells.id = experiment_raw_files.well_id
            LEFT JOIN proteins ON proteins.id = batch_wells.protein_id
            WHERE experiment_raw_files.id = ?
            """.format(columns=RAW_FILE_COLUMNS),
            (raw_file_id,),
        ).fetchone()

    def get_content(self, raw_file_id: int) -> bytes | None:
        row = self.connection.execute(
            """
            SELECT content
            FROM experiment_raw_files
            WHERE id = ?
            """,
            (raw_file_id,),
        ).fetchone()
        return row["content"] if row else None

    def insert(
        self,
        *,
        experiment_id: int,
        uploaded_by: int,
        filename: str,
        raw_file_type: str,
        mime_type: str,
        content: bytes,
        well_id: int | None = None,
    ) -> int:
        digest = hashlib.sha256(content).hexdigest()
        cursor = self.connection.execute(
            """
            INSERT INTO experiment_raw_files (
                experiment_id,
                uploaded_by,
                well_id,
                filename,
                raw_file_type,
                mime_type,
                size_bytes,
                content,
                content_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                uploaded_by,
                well_id,
                filename,
                raw_file_type,
                mime_type or "application/octet-stream",
                len(content),
                content,
                digest,
            ),
        )
        return int(cursor.lastrowid)
