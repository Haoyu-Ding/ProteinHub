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

    connection.execute(
        """
        CREATE TABLE proteins_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            sequence TEXT NOT NULL,
            dna_sequence TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            version_tag TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO proteins_new (
            id,
            project_id,
            name,
            sequence,
            dna_sequence,
            description,
            version_tag,
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
            version_tag,
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

    connection.execute(
        """
        CREATE TABLE batches_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            plate_format TEXT NOT NULL DEFAULT '96' CHECK (plate_format IN ('96')),
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO batches_new (
            id,
            project_id,
            name,
            description,
            plate_format,
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
            created_at,
            updated_at
        )
        SELECT
            id,
            batch_id,
            protein_id,
            position,
            created_at,
            COALESCE(NULLIF(updated_at, ''), created_at, CURRENT_TIMESTAMP)
        FROM batch_wells
        """
    )
    connection.execute("DROP TABLE batch_wells")
    connection.execute("ALTER TABLE batch_wells_new RENAME TO batch_wells")


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
