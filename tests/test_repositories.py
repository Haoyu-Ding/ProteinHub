from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from proteinhub.infrastructure.postgres.schema import POSTGRES_MIGRATIONS, POSTGRES_SCHEMA
from proteinhub.infrastructure.sqlite.connection import init_db
from proteinhub.infrastructure.sqlite.repositories.projects import ProjectRepository


class _FakeCursor:
    def fetchall(self) -> list[dict]:
        return []


class _CapturingConnection:
    def __init__(self) -> None:
        self.statement = ""
        self.parameters: tuple[Any, ...] = ()

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> _FakeCursor:
        self.statement = statement
        self.parameters = parameters
        return _FakeCursor()


def test_project_member_list_subquery_has_postgresql_alias() -> None:
    connection = _CapturingConnection()

    ProjectRepository(connection).list_members(123)  # type: ignore[arg-type]

    assert ") AS project_member_rows" in connection.statement
    assert connection.parameters == (123, 123)


def test_project_workspace_indexes_are_created_for_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"

    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }

    assert "idx_proteins_project_created" in indexes
    assert "idx_artifacts_protein_deleted" in indexes
    assert "idx_batches_project_created" in indexes
    assert "idx_batch_experiments_batch" in indexes
    assert "idx_experiment_well_results_experiment" in indexes


def test_project_workspace_indexes_are_present_for_postgresql() -> None:
    assert "CREATE INDEX IF NOT EXISTS idx_proteins_project_created" in POSTGRES_SCHEMA
    assert "CREATE INDEX IF NOT EXISTS idx_artifacts_protein_deleted" in POSTGRES_SCHEMA
    assert "CREATE INDEX IF NOT EXISTS idx_batches_project_created" in POSTGRES_SCHEMA
    assert "CREATE INDEX IF NOT EXISTS idx_batch_experiments_batch" in POSTGRES_SCHEMA
    assert (
        "CREATE INDEX IF NOT EXISTS idx_experiment_well_results_experiment"
        in POSTGRES_SCHEMA
    )


def test_user_account_columns_are_present_for_postgresql() -> None:
    migration_text = "\n".join(POSTGRES_MIGRATIONS)
    for column in (
        "is_active",
        "disabled_at",
        "disabled_by",
        "disabled_reason",
        "last_login_at",
        "password_updated_at",
    ):
        assert column in POSTGRES_SCHEMA
        assert f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column}" in migration_text
