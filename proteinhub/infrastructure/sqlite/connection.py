from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from proteinhub.infrastructure.sqlite.schema import MIGRATIONS, SCHEMA


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
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(statement)
    connection.execute(
        """
        UPDATE sequences
        SET updated_at = created_at
        WHERE updated_at = ''
        """
    )


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
