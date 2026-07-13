from __future__ import annotations

import json
import sqlite3


class ExperimentRepository:
    DETAIL_TABLES = {
        "FPLC": "fplc_experiments",
        "SPR": "spr_experiments",
        "HPLC": "hplc_experiments",
    }

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def batch_id_for(self, experiment_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT batch_id FROM batch_experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
        return int(row["batch_id"]) if row else None

    def insert(
        self,
        *,
        batch_id: int,
        experiment_type: str,
        name: str,
        description: str,
        created_by: int,
        details: dict,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO batch_experiments (
                batch_id, experiment_type, name, description, created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (batch_id, experiment_type, name, description, created_by),
        )
        experiment_id = int(cursor.lastrowid)
        detail_table = self._detail_table(experiment_type)
        self.connection.execute(
            f"""
            INSERT INTO {detail_table} (experiment_id, details_json)
            VALUES (?, ?)
            """,
            (experiment_id, json.dumps(details, ensure_ascii=False, sort_keys=True)),
        )
        return experiment_id

    def get(self, experiment_id: int) -> dict | None:
        experiment = self.connection.execute(
            """
            SELECT
                batch_experiments.*,
                users.name AS created_by_name,
                users.email AS created_by_email
            FROM batch_experiments
            JOIN users ON users.id = batch_experiments.created_by
            WHERE batch_experiments.id = ?
            """,
            (experiment_id,),
        ).fetchone()
        if not experiment:
            return None
        return self._with_details(experiment)

    def list_for_batch(self, batch_id: int) -> list[dict]:
        experiments = self.connection.execute(
            """
            SELECT
                batch_experiments.*,
                users.name AS created_by_name,
                users.email AS created_by_email,
                (
                    SELECT COUNT(*)
                    FROM experiment_well_results
                    WHERE experiment_well_results.experiment_id = batch_experiments.id
                      AND (
                          experiment_well_results.result_value != ''
                          OR experiment_well_results.result_note != ''
                      )
                ) AS result_count
            FROM batch_experiments
            JOIN users ON users.id = batch_experiments.created_by
            WHERE batch_experiments.batch_id = ?
            ORDER BY batch_experiments.created_at DESC, batch_experiments.id DESC
            """,
            (batch_id,),
        ).fetchall()
        return [self._with_details(experiment) for experiment in experiments]

    def list_well_results(self, experiment_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                batch_wells.id AS well_id,
                batch_wells.position,
                batch_wells.protein_id,
                proteins.name AS protein_name,
                proteins.sequence AS protein_sequence,
                proteins.version_tag AS protein_version_tag,
                experiment_well_results.id AS result_id,
                COALESCE(experiment_well_results.result_value, '') AS result_value,
                COALESCE(experiment_well_results.result_note, '') AS result_note,
                experiment_well_results.updated_at AS result_updated_at
            FROM batch_experiments
            JOIN batch_wells ON batch_wells.batch_id = batch_experiments.batch_id
            JOIN proteins ON proteins.id = batch_wells.protein_id
            LEFT JOIN experiment_well_results
                ON experiment_well_results.experiment_id = batch_experiments.id
               AND experiment_well_results.well_id = batch_wells.id
            WHERE batch_experiments.id = ?
            ORDER BY batch_wells.position ASC
            """,
            (experiment_id,),
        ).fetchall()

    def get_well_for_experiment(
        self, *, experiment_id: int, well_id: int
    ) -> dict | None:
        return self.connection.execute(
            """
            SELECT batch_wells.*
            FROM batch_experiments
            JOIN batch_wells ON batch_wells.batch_id = batch_experiments.batch_id
            WHERE batch_experiments.id = ? AND batch_wells.id = ?
            """,
            (experiment_id, well_id),
        ).fetchone()

    def upsert_well_result(
        self,
        *,
        experiment_id: int,
        well_id: int,
        result_value: str,
        result_note: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO experiment_well_results (
                experiment_id, well_id, result_value, result_note
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT (experiment_id, well_id)
            DO UPDATE SET
                result_value = excluded.result_value,
                result_note = excluded.result_note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (experiment_id, well_id, result_value, result_note),
        )

    def _detail_table(self, experiment_type: str) -> str:
        return self.DETAIL_TABLES[experiment_type]

    def _with_details(self, experiment: dict) -> dict:
        detail_table = self._detail_table(experiment["experiment_type"])
        detail = self.connection.execute(
            f"SELECT details_json FROM {detail_table} WHERE experiment_id = ?",
            (experiment["id"],),
        ).fetchone()
        experiment["details"] = json.loads(detail["details_json"]) if detail else {}
        return experiment
