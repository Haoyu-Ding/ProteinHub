from __future__ import annotations

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
