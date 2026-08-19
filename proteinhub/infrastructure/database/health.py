from __future__ import annotations


def database_is_available(connection) -> bool:
    row = connection.execute("SELECT 1 AS ok").fetchone()
    return bool(row and row["ok"] == 1)
