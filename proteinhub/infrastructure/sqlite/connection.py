from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from proteinhub.infrastructure.sqlite.schema import (
    BASELINE_MIGRATION,
    MIGRATIONS,
    SCHEMA,
)


RETIRED_PROTEIN_COLUMNS = {
    "status",
    "priority",
    "assigned_to",
    "discipline_owner",
    "design_rationale",
    "handoff_note",
    "risk_note",
    "version_tag",
}
RETIRED_BATCH_COLUMNS = {"experiment_type"}
RETIRED_BATCH_WELL_COLUMNS = {"result_value", "result_note"}


def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def connect(database_path: Path | str) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = dict_factory
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(database_path: Path | str) -> None:
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)
        apply_migrations(connection)
        connection.commit()


def apply_migrations(connection: sqlite3.Connection) -> None:
    for table_name, column_name, statement in MIGRATIONS:
        if not table_exists(connection, table_name):
            continue
        columns = table_columns(connection, table_name)
        if column_name not in columns:
            connection.execute(statement)
    drop_retired_schema(connection)
    mark_migration_applied(connection, BASELINE_MIGRATION)


def mark_migration_applied(connection: sqlite3.Connection, version: str) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version)
        VALUES (?)
        """,
        (version,),
    )


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def drop_retired_schema(connection: sqlite3.Connection) -> None:
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("DROP TABLE IF EXISTS protein_comments")
        connection.execute("DROP TABLE IF EXISTS sequence_comments")
        connection.execute("DROP TABLE IF EXISTS sequences")
        rebuild_proteins_without_retired_columns(connection)
        rebuild_batches_without_retired_columns(connection)
        rebuild_batch_wells_without_retired_columns(connection)
        rebuild_batch_experiments_for_akta(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def rebuild_proteins_without_retired_columns(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "proteins"):
        return
    columns = table_columns(connection, "proteins")
    if not columns.intersection(RETIRED_PROTEIN_COLUMNS):
        return
    protein_type_expression = "protein_type"
    if "version_tag" in columns:
        protein_type_expression = """
            CASE
                WHEN version_tag IN ('TCR', 'cyclic peptide', 'nanobody', 'minibinder', 'enzymes')
                THEN version_tag
                ELSE protein_type
            END
        """
    manual_rating_expression = "'unrated'"
    if "manual_rating" in columns:
        manual_rating_expression = """
            CASE
                WHEN manual_rating IN ('unrated', 'normal', 'rare', 'epic', 'legendary')
                THEN manual_rating
                ELSE 'unrated'
            END
        """

    connection.execute(
        """
        CREATE TABLE proteins_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            sequence TEXT NOT NULL,
            dna_sequence TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            protein_type TEXT NOT NULL DEFAULT 'TCR',
            target TEXT NOT NULL DEFAULT '',
            manual_rating TEXT NOT NULL DEFAULT 'unrated' CHECK (manual_rating IN ('unrated', 'normal', 'rare', 'epic', 'legendary')),
            score_details_json TEXT NOT NULL DEFAULT '{}',
            sequence_similarity_status TEXT NOT NULL DEFAULT '',
            sequence_similarity_matches_json TEXT NOT NULL DEFAULT '[]',
            structure_filename TEXT NOT NULL DEFAULT '',
            structure_mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
            structure_size_bytes INTEGER NOT NULL DEFAULT 0,
            structure_storage_path TEXT NOT NULL DEFAULT '',
            structure_storage_backend TEXT NOT NULL DEFAULT 'filesystem' CHECK (structure_storage_backend IN ('filesystem', 'database')),
            structure_content BLOB,
            structure_content_sha256 TEXT NOT NULL DEFAULT '',
            structure_deposit_date TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    score_details_expression = "'{}'"
    if "score_details_json" in columns:
        score_details_expression = "COALESCE(NULLIF(score_details_json, ''), '{}')"
    similarity_status_expression = (
        "sequence_similarity_status"
        if "sequence_similarity_status" in columns
        else "''"
    )
    similarity_matches_expression = (
        "COALESCE(NULLIF(sequence_similarity_matches_json, ''), '[]')"
        if "sequence_similarity_matches_json" in columns
        else "'[]'"
    )
    structure_deposit_date_expression = (
        "COALESCE(structure_deposit_date, '')"
        if "structure_deposit_date" in columns
        else "''"
    )
    structure_storage_backend_expression = (
        """
            CASE
                WHEN structure_storage_backend IN ('filesystem', 'database')
                THEN structure_storage_backend
                ELSE 'filesystem'
            END
        """
        if "structure_storage_backend" in columns
        else "'filesystem'"
    )
    structure_content_expression = (
        "structure_content" if "structure_content" in columns else "NULL"
    )
    structure_content_sha256_expression = (
        "COALESCE(structure_content_sha256, '')"
        if "structure_content_sha256" in columns
        else "''"
    )
    connection.execute(
        f"""
        INSERT INTO proteins_new (
            id,
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
            structure_filename,
            structure_mime_type,
            structure_size_bytes,
            structure_storage_path,
            structure_storage_backend,
            structure_content,
            structure_content_sha256,
            structure_deposit_date,
            created_at,
            updated_at
        )
        SELECT
            id,
            project_id,
            name,
            sequence,
            dna_sequence,
            description,
            {protein_type_expression},
            target,
            {manual_rating_expression},
            {score_details_expression},
            {similarity_status_expression},
            {similarity_matches_expression},
            structure_filename,
            structure_mime_type,
            structure_size_bytes,
            structure_storage_path,
            {structure_storage_backend_expression},
            {structure_content_expression},
            {structure_content_sha256_expression},
            {structure_deposit_date_expression},
            created_at,
            COALESCE(NULLIF(updated_at, ''), created_at, CURRENT_TIMESTAMP)
        FROM proteins
        """
    )
    connection.execute("DROP TABLE proteins")
    connection.execute("ALTER TABLE proteins_new RENAME TO proteins")


def rebuild_batches_without_retired_columns(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "batches"):
        return
    columns = table_columns(connection, "batches")
    if not columns.intersection(RETIRED_BATCH_COLUMNS):
        return
    ordered_at_expression = "ordered_at" if "ordered_at" in columns else "''"
    receipt_note_expression = "receipt_note" if "receipt_note" in columns else "''"
    receipt_updated_by_expression = (
        "receipt_updated_by" if "receipt_updated_by" in columns else "NULL"
    )
    receipt_updated_at_expression = (
        "receipt_updated_at" if "receipt_updated_at" in columns else "''"
    )

    connection.execute(
        """
        CREATE TABLE batches_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            plate_format TEXT NOT NULL DEFAULT '96' CHECK (plate_format IN ('96')),
            order_status TEXT NOT NULL DEFAULT 'not_ordered' CHECK (order_status IN ('not_ordered', 'ordered', 'partially_received', 'fully_received')),
            ordered_at TEXT NOT NULL DEFAULT '',
            receipt_note TEXT NOT NULL DEFAULT '',
            receipt_updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            receipt_updated_at TEXT NOT NULL DEFAULT '',
            translation_padding INTEGER NOT NULL DEFAULT 0,
            translation_additional_w INTEGER NOT NULL DEFAULT 0,
            translation_organism TEXT NOT NULL DEFAULT '',
            translation_backbone TEXT NOT NULL DEFAULT '',
            translation_resistance TEXT NOT NULL DEFAULT '',
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO batches_new (
            id,
            project_id,
            name,
            description,
            plate_format,
            order_status,
            ordered_at,
            receipt_note,
            receipt_updated_by,
            receipt_updated_at,
            translation_padding,
            translation_additional_w,
            translation_organism,
            translation_backbone,
            translation_resistance,
            created_by,
            created_at,
            updated_at
        )
        SELECT
            id,
            project_id,
            name,
            description,
            plate_format,
            COALESCE(NULLIF(order_status, ''), 'not_ordered'),
            COALESCE(NULLIF({ordered_at_expression}, ''), ''),
            COALESCE(NULLIF({receipt_note_expression}, ''), ''),
            {receipt_updated_by_expression},
            COALESCE(NULLIF({receipt_updated_at_expression}, ''), ''),
            translation_padding,
            translation_additional_w,
            translation_organism,
            translation_backbone,
            translation_resistance,
            created_by,
            created_at,
            COALESCE(NULLIF(updated_at, ''), created_at, CURRENT_TIMESTAMP)
        FROM batches
        """
    )
    connection.execute("DROP TABLE batches")
    connection.execute("ALTER TABLE batches_new RENAME TO batches")


def rebuild_batch_wells_without_retired_columns(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "batch_wells"):
        return
    columns = table_columns(connection, "batch_wells")
    if not columns.intersection(RETIRED_BATCH_WELL_COLUMNS):
        return

    connection.execute(
        """
        CREATE TABLE batch_wells_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
            position TEXT NOT NULL,
            source_aa_sequence TEXT NOT NULL DEFAULT '',
            translated_aa_sequence TEXT NOT NULL DEFAULT '',
            dna_sequence TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (batch_id, position)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO batch_wells_new (
            id,
            batch_id,
            protein_id,
            position,
            source_aa_sequence,
            translated_aa_sequence,
            dna_sequence,
            created_at,
            updated_at
        )
        SELECT
            id,
            batch_id,
            protein_id,
            position,
            source_aa_sequence,
            translated_aa_sequence,
            dna_sequence,
            created_at,
            COALESCE(NULLIF(updated_at, ''), created_at, CURRENT_TIMESTAMP)
        FROM batch_wells
        """
    )
    connection.execute("DROP TABLE batch_wells")
    connection.execute("ALTER TABLE batch_wells_new RENAME TO batch_wells")


def rebuild_batch_experiments_for_akta(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "batch_experiments"):
        return
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'batch_experiments'
        """
    ).fetchone()
    table_sql = row["sql"] if row else ""
    if "'AKTA'" in table_sql:
        return

    connection.execute(
        """
        CREATE TABLE batch_experiments_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            experiment_type TEXT NOT NULL CHECK (experiment_type IN ('FPLC', 'SPR', 'HPLC', 'AKTA')),
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO batch_experiments_new (
            id,
            batch_id,
            experiment_type,
            name,
            description,
            created_by,
            created_at,
            updated_at
        )
        SELECT
            id,
            batch_id,
            experiment_type,
            name,
            description,
            created_by,
            created_at,
            COALESCE(NULLIF(updated_at, ''), created_at, CURRENT_TIMESTAMP)
        FROM batch_experiments
        """
    )
    connection.execute("DROP TABLE batch_experiments")
    connection.execute("ALTER TABLE batch_experiments_new RENAME TO batch_experiments")


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
