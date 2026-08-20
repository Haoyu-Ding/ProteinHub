from __future__ import annotations

from typing import Any

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
