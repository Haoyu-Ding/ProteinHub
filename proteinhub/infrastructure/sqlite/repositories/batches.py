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
                users.email AS created_by_email,
                COALESCE(receipt_users.name, '') AS receipt_updated_by_name,
                COALESCE(receipt_users.email, '') AS receipt_updated_by_email
            FROM batches
            JOIN users ON users.id = batches.created_by
            LEFT JOIN users AS receipt_users ON receipt_users.id = batches.receipt_updated_by
            WHERE batches.id = ?
            """,
            (batch_id,),
        ).fetchone()

    def get_label_context(self, batch_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                batches.id AS batch_id,
                batches.name AS batch_name,
                batches.project_id,
                projects.owner_id,
                owner_users.name AS owner_name,
                owner_users.email AS owner_email
            FROM batches
            JOIN projects ON projects.id = batches.project_id
            JOIN users AS owner_users ON owner_users.id = projects.owner_id
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
                COALESCE(receipt_users.name, '') AS receipt_updated_by_name,
                COALESCE(receipt_users.email, '') AS receipt_updated_by_email,
                (
                    SELECT COUNT(*)
                    FROM batch_wells
                    WHERE batch_wells.batch_id = batches.id
                ) AS well_count,
                (
                    SELECT COUNT(*)
                    FROM batch_wells
                    WHERE batch_wells.batch_id = batches.id
                      AND batch_wells.received_at != ''
                ) AS received_well_count,
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
            LEFT JOIN users AS receipt_users ON receipt_users.id = batches.receipt_updated_by
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

    def update_translation_settings(
        self,
        *,
        batch_id: int,
        padding: bool,
        add_additional_w: bool,
        organism: str,
        backbone: str,
        resistance: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE batches
            SET
                translation_padding = ?,
                translation_additional_w = ?,
                translation_organism = ?,
                translation_backbone = ?,
                translation_resistance = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                int(bool(padding)),
                int(bool(add_additional_w)),
                organism,
                backbone,
                resistance,
                batch_id,
            ),
        )

    def update_order_status(self, *, batch_id: int, order_status: str) -> None:
        self.connection.execute(
            """
            UPDATE batches
            SET
                order_status = ?,
                ordered_at = CASE
                    WHEN ? IN ('ordered', 'partially_received', 'fully_received')
                     AND ordered_at = ''
                    THEN CURRENT_TIMESTAMP
                    ELSE ordered_at
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (order_status, order_status, batch_id),
        )

    def update_receipt_note(
        self, *, batch_id: int, receipt_note: str, receipt_updated_by: int
    ) -> None:
        self.connection.execute(
            """
            UPDATE batches
            SET
                receipt_note = ?,
                receipt_updated_by = ?,
                receipt_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (receipt_note, receipt_updated_by, batch_id),
        )

    def update_received_wells(
        self,
        *,
        batch_id: int,
        received_well_ids: set[int],
        received_by: int,
    ) -> None:
        rows = self.connection.execute(
            """
            SELECT id, received_at
            FROM batch_wells
            WHERE batch_id = ?
            """,
            (batch_id,),
        ).fetchall()
        mark_ids = [
            int(row["id"])
            for row in rows
            if int(row["id"]) in received_well_ids and not row["received_at"]
        ]
        clear_ids = [
            int(row["id"])
            for row in rows
            if int(row["id"]) not in received_well_ids and row["received_at"]
        ]
        if mark_ids:
            self.connection.executemany(
                """
                UPDATE batch_wells
                SET
                    received_at = CURRENT_TIMESTAMP,
                    received_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [(received_by, well_id) for well_id in mark_ids],
            )
        if clear_ids:
            self.connection.executemany(
                """
                UPDATE batch_wells
                SET
                    received_at = '',
                    received_by = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [(well_id,) for well_id in clear_ids],
            )

    def list_order_monitor_batches(self) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                batches.id,
                batches.project_id,
                projects.name AS project_name,
                batches.name,
                batches.description,
                batches.plate_format,
                batches.order_status,
                batches.ordered_at,
                CASE
                    WHEN batches.ordered_at != '' THEN batches.ordered_at
                    WHEN batches.order_status IN ('ordered', 'partially_received', 'fully_received')
                    THEN batches.updated_at
                    ELSE ''
                END AS order_monitor_ordered_at,
                projects.owner_id,
                owner_users.name AS owner_name,
                owner_users.email AS owner_email,
                batches.created_at,
                batches.updated_at,
                users.name AS created_by_name,
                users.email AS created_by_email,
                (
                    SELECT COUNT(*)
                    FROM batch_wells
                    WHERE batch_wells.batch_id = batches.id
                ) AS well_count,
                (
                    SELECT COUNT(*)
                    FROM batch_wells
                    WHERE batch_wells.batch_id = batches.id
                      AND batch_wells.received_at != ''
                ) AS received_well_count
            FROM batches
            JOIN projects ON projects.id = batches.project_id
            JOIN users AS owner_users ON owner_users.id = projects.owner_id
            JOIN users ON users.id = batches.created_by
            WHERE batches.order_status IN ('ordered', 'partially_received', 'fully_received')
            ORDER BY order_monitor_ordered_at DESC, batches.id DESC
            """,
        ).fetchall()

    def update_well_translation_result(
        self,
        *,
        well_id: int,
        source_aa_sequence: str,
        translated_aa_sequence: str,
        dna_sequence: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE batch_wells
            SET
                source_aa_sequence = ?,
                translated_aa_sequence = ?,
                dna_sequence = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                source_aa_sequence,
                translated_aa_sequence,
                dna_sequence,
                well_id,
            ),
        )

    def list_wells(self, batch_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                batch_wells.*,
                proteins.name AS protein_name,
                proteins.sequence AS protein_sequence,
                proteins.protein_type AS protein_type,
                proteins.score_details_json AS score_details_json,
                COALESCE(receipt_users.name, '') AS received_by_name,
                COALESCE(receipt_users.email, '') AS received_by_email
            FROM batch_wells
            JOIN proteins ON proteins.id = batch_wells.protein_id
            LEFT JOIN users AS receipt_users ON receipt_users.id = batch_wells.received_by
            WHERE batch_wells.batch_id = ?
            ORDER BY batch_wells.position ASC
            """,
            (batch_id,),
        ).fetchall()

    def list_sequence_exports(self, batch_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                batch_wells.id AS well_id,
                batch_wells.position,
                batch_wells.protein_id,
                proteins.name AS protein_name,
                proteins.sequence AS protein_sequence
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
                proteins.name AS protein_name,
                COALESCE(receipt_users.name, '') AS received_by_name,
                COALESCE(receipt_users.email, '') AS received_by_email
            FROM batch_wells
            JOIN proteins ON proteins.id = batch_wells.protein_id
            LEFT JOIN users AS receipt_users ON receipt_users.id = batch_wells.received_by
            WHERE batch_wells.batch_id = ? AND batch_wells.id = ?
            """,
            (batch_id, well_id),
        ).fetchone()

    def get_well_by_position(self, *, batch_id: int, position: str) -> dict | None:
        return self.connection.execute(
            """
            SELECT *
            FROM batch_wells
            WHERE batch_id = ? AND position = ?
            """,
            (batch_id, position),
        ).fetchone()

    def has_recorded_results(self, batch_id: int) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM experiment_well_results
            JOIN batch_experiments
                ON batch_experiments.id = experiment_well_results.experiment_id
            WHERE batch_experiments.batch_id = ?
              AND (
                  experiment_well_results.result_value != ''
                  OR experiment_well_results.result_note != ''
              )
            LIMIT 1
            """,
            (batch_id,),
        ).fetchone()
        return row is not None

    def update_well_position(self, *, well_id: int, position: str) -> None:
        self.connection.execute(
            """
            UPDATE batch_wells
            SET position = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (position, well_id),
        )

    def swap_well_positions(self, *, first_well: dict, second_well: dict) -> None:
        temporary_position = f"__swap_{first_well['id']}_{second_well['id']}__"
        self.update_well_position(well_id=first_well["id"], position=temporary_position)
        self.update_well_position(
            well_id=second_well["id"],
            position=first_well["position"],
        )
        self.update_well_position(
            well_id=first_well["id"],
            position=second_well["position"],
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
