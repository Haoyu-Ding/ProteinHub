from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from proteinhub.infrastructure.database.connection import normalize_db_row
from proteinhub.infrastructure.postgres.schema import (
    BASELINE_MIGRATION,
    POSTGRES_MIGRATIONS,
    POSTGRES_SCHEMA,
)


class PostgresCursor:
    def __init__(self, cursor, connection: "PostgresConnection") -> None:
        self._cursor = cursor
        self._connection = connection

    @property
    def lastrowid(self) -> int:
        row = self._connection._raw.execute("SELECT LASTVAL() AS lastrowid").fetchone()
        return int(row["lastrowid"])

    def fetchone(self) -> dict | None:
        return normalize_db_row(self._cursor.fetchone())

    def fetchall(self) -> list[dict]:
        return [normalize_db_row(row) for row in self._cursor.fetchall()]


class PostgresConnection:
    backend = "postgresql"

    def __init__(self, raw_connection) -> None:
        self._raw = raw_connection

    def execute(self, statement: str, parameters: Iterable[Any] = ()) -> PostgresCursor:
        cursor = self._raw.execute(_prepare_statement(statement), tuple(parameters))
        return PostgresCursor(cursor, self)

    def executemany(
        self,
        statement: str,
        parameter_sets: Iterable[Iterable[Any]],
    ) -> None:
        with self._raw.cursor() as cursor:
            cursor.executemany(
                _prepare_statement(statement),
                [tuple(parameters) for parameters in parameter_sets],
            )

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def connect_postgres(database_url: str) -> PostgresConnection:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires installing the psycopg[binary] dependency"
        ) from exc

    return PostgresConnection(psycopg.connect(database_url, row_factory=dict_row))


def init_postgres_db(database_url: str) -> None:
    with connect_postgres(database_url) as connection:
        for statement in _statements(POSTGRES_SCHEMA):
            connection.execute(statement)
        for statement in POSTGRES_MIGRATIONS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version)
            VALUES (?)
            ON CONFLICT (version) DO NOTHING
            """,
            (BASELINE_MIGRATION,),
        )


def _prepare_statement(statement: str) -> str:
    statement = re.sub(
        r"\bCURRENT_TIMESTAMP\b(?!\s*::text)",
        "(CURRENT_TIMESTAMP::text)",
        statement,
    )
    return _replace_qmark_placeholders(
        statement,
    )


def _replace_qmark_placeholders(statement: str) -> str:
    parts: list[str] = []
    in_single_quote = False
    index = 0
    while index < len(statement):
        char = statement[index]
        if char == "'":
            parts.append(char)
            if index + 1 < len(statement) and statement[index + 1] == "'":
                parts.append(statement[index + 1])
                index += 2
                continue
            in_single_quote = not in_single_quote
        elif char == "?" and not in_single_quote:
            parts.append("%s")
        else:
            parts.append(char)
        index += 1
    return "".join(parts)


def _statements(script: str) -> list[str]:
    return [
        statement.strip()
        for statement in script.split(";")
        if statement.strip()
    ]
