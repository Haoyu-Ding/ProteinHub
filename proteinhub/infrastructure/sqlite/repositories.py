from __future__ import annotations

import json
import sqlite3


class UserRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_public(self, user_id: int) -> dict | None:
        return self.connection.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    def get_by_email(self, email: str) -> dict | None:
        return self.connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    def insert(self, *, name: str, email: str, password_hash: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        return int(cursor.lastrowid)

    def search_available_for_project(self, *, project_id: int, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self.connection.execute(
            """
            SELECT id, name, email, created_at
            FROM users
            WHERE (name LIKE ? OR email LIKE ?)
              AND id NOT IN (
                  SELECT user_id FROM project_members WHERE project_id = ?
              )
            ORDER BY name, email
            LIMIT 8
            """,
            (pattern, pattern, project_id),
        ).fetchall()


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

    def insert_member(
        self, *, project_id: int, user_id: int, role: str, discipline: str = "other"
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role, discipline)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, user_id, role, discipline),
        )

    def get_member(self, *, project_id: int, user_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                project_members.role,
                project_members.discipline,
                project_members.created_at
            FROM project_members
            JOIN users ON users.id = project_members.user_id
            WHERE project_members.project_id = ? AND project_members.user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()

    def count_owners(self, project_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS owner_count
            FROM project_members
            WHERE project_id = ? AND role = 'owner'
            """,
            (project_id,),
        ).fetchone()
        return int(row["owner_count"])

    def update_member(
        self, *, project_id: int, user_id: int, role: str, discipline: str
    ) -> None:
        self.connection.execute(
            """
            UPDATE project_members
            SET role = ?, discipline = ?
            WHERE project_id = ? AND user_id = ?
            """,
            (role, discipline, project_id, user_id),
        )

    def list_members(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                project_members.role,
                project_members.discipline,
                project_members.created_at
            FROM project_members
            JOIN users ON users.id = project_members.user_id
            WHERE project_members.project_id = ?
            ORDER BY project_members.role DESC, users.name, users.email
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
                artifacts.*,
                users.name AS uploaded_by_name,
                users.email AS uploaded_by_email
            FROM artifacts
            JOIN users ON users.id = artifacts.uploaded_by
            WHERE artifacts.protein_id = ? AND artifacts.is_deleted = 0
            ORDER BY artifacts.created_at DESC, artifacts.id DESC
            """,
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
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO artifacts (
                protein_id, uploaded_by, filename, artifact_type,
                mime_type, size_bytes, storage_path
            )
            VALUES (?, ?, ?, ?, ?, 0, '')
            """,
            (protein_id, uploaded_by, filename, artifact_type, mime_type),
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
            SELECT
                artifacts.*,
                users.name AS uploaded_by_name,
                users.email AS uploaded_by_email
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
