from __future__ import annotations

import sqlite3


class BatchRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def project_id_for(self, batch_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT project_id FROM batches WHERE id = ?", (batch_id,)
        ).fetchone()
        return int(row["project_id"]) if row else None

    def get(self, batch_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                batches.*,
                users.name AS created_by_name,
                users.email AS created_by_email
            FROM batches
            JOIN users ON users.id = batches.created_by
            WHERE batches.id = ?
            """,
            (batch_id,),
        ).fetchone()

    def list_for_project(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                batches.*,
                users.name AS created_by_name,
                users.email AS created_by_email,
                (
                    SELECT COUNT(*)
                    FROM batch_wells
                    WHERE batch_wells.batch_id = batches.id
                ) AS well_count,
                (
                    SELECT COUNT(*)
                    FROM batch_experiments
                    WHERE batch_experiments.batch_id = batches.id
                ) AS experiment_count,
                (
                    SELECT COUNT(*)
                    FROM experiment_well_results
                    JOIN batch_experiments
                        ON batch_experiments.id = experiment_well_results.experiment_id
                    WHERE batch_experiments.batch_id = batches.id
                      AND (
                          experiment_well_results.result_value != ''
                          OR experiment_well_results.result_note != ''
                      )
                ) AS result_count
            FROM batches
            JOIN users ON users.id = batches.created_by
            WHERE batches.project_id = ?
            ORDER BY batches.created_at DESC, batches.id DESC
            """,
            (project_id,),
        ).fetchall()

    def insert(
        self,
        *,
        project_id: int,
        name: str,
        description: str,
        plate_format: str,
        created_by: int,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO batches (
                project_id, name, description, plate_format, created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                name,
                description,
                plate_format,
                created_by,
            ),
        )
        return int(cursor.lastrowid)

    def insert_wells(self, *, batch_id: int, wells: list[tuple[str, int]]) -> None:
        self.connection.executemany(
            """
            INSERT INTO batch_wells (batch_id, position, protein_id)
            VALUES (?, ?, ?)
            """,
            [(batch_id, position, protein_id) for position, protein_id in wells],
        )

    def list_wells(self, batch_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                batch_wells.*,
                proteins.name AS protein_name,
                proteins.sequence AS protein_sequence,
                proteins.version_tag AS protein_version_tag
            FROM batch_wells
            JOIN proteins ON proteins.id = batch_wells.protein_id
            WHERE batch_wells.batch_id = ?
            ORDER BY batch_wells.position ASC
            """,
            (batch_id,),
        ).fetchall()

    def get_well(self, *, batch_id: int, well_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                batch_wells.*,
                proteins.name AS protein_name
            FROM batch_wells
            JOIN proteins ON proteins.id = batch_wells.protein_id
            WHERE batch_wells.batch_id = ? AND batch_wells.id = ?
            """,
            (batch_id, well_id),
        ).fetchone()

    def update_well_result(
        self, *, well_id: int, result_value: str, result_note: str
    ) -> None:
        self.connection.execute(
            """
            UPDATE batch_wells
            SET
                result_value = ?,
                result_note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (result_value, result_note, well_id),
        )

    def list_results_for_protein(self, protein_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                experiment_well_results.*,
                batch_wells.position,
                batch_wells.protein_id,
                batches.id AS batch_id,
                batches.name AS batch_name,
                batches.plate_format,
                batches.project_id,
                batch_experiments.id AS experiment_id,
                batch_experiments.name AS experiment_name,
                batch_experiments.experiment_type
            FROM experiment_well_results
            JOIN batch_wells ON batch_wells.id = experiment_well_results.well_id
            JOIN batch_experiments
                ON batch_experiments.id = experiment_well_results.experiment_id
            JOIN batches ON batches.id = batch_experiments.batch_id
            WHERE batch_wells.protein_id = ?
              AND (
                  experiment_well_results.result_value != ''
                  OR experiment_well_results.result_note != ''
              )
            ORDER BY
                batch_experiments.created_at DESC,
                batch_experiments.id DESC,
                batch_wells.position ASC
            """,
            (protein_id,),
        ).fetchall()
