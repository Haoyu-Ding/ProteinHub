from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from proteinhub.config import Settings
from proteinhub.infrastructure.sqlite.connection import (
    connect as connect_sqlite,
    init_db as init_sqlite_db,
)


def init_db(target: Settings | Path | str) -> None:
    database_url = _database_url(target)
    if database_url:
        from proteinhub.infrastructure.postgres.connection import init_postgres_db

        init_postgres_db(database_url)
        return
    init_sqlite_db(_database_path(target))


def connect(target: Settings | Path | str):
    database_url = _database_url(target)
    if database_url:
        from proteinhub.infrastructure.postgres.connection import connect_postgres

        connection = connect_postgres(database_url)
    else:
        connection = connect_sqlite(_database_path(target))
    if isinstance(target, Settings):
        try:
            connection.artifact_storage_backend = target.artifact_storage_backend
        except AttributeError:
            pass
    return connection


@contextmanager
def transaction(connection) -> Iterator[Any]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def normalize_db_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, dict):
        return {key: normalize_db_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_db_value(item) for item in value]
    return value


def normalize_db_row(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return {key: normalize_db_value(value) for key, value in row.items()}
    return row


def _database_url(target: Settings | Path | str) -> str:
    if isinstance(target, Settings):
        return target.database_url
    text = str(target)
    if text.startswith(("postgresql://", "postgres://")):
        return text
    return ""


def _database_path(target: Settings | Path | str) -> Path:
    if isinstance(target, Settings):
        return target.database_path
    return Path(target)
