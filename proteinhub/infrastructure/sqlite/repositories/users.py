from __future__ import annotations

import sqlite3


class UserRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_public(self, user_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                id,
                name,
                email,
                global_role,
                is_active,
                disabled_at,
                disabled_by,
                disabled_reason,
                last_login_at,
                password_updated_at,
                created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    def get_admin_user(self, user_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                users.global_role,
                users.is_active,
                users.disabled_at,
                users.disabled_by,
                users.disabled_reason,
                users.last_login_at,
                users.password_updated_at,
                users.created_at,
                COALESCE(disabled_users.name, '') AS disabled_by_name,
                COALESCE(disabled_users.email, '') AS disabled_by_email
            FROM users
            LEFT JOIN users AS disabled_users ON disabled_users.id = users.disabled_by
            WHERE users.id = ?
            """,
            (user_id,),
        ).fetchone()

    def get_by_email(self, email: str) -> dict | None:
        return self.connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    def insert(self, *, name: str, email: str, password_hash: str) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO users (name, email, password_hash, password_updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (name, email, password_hash),
        )
        return int(cursor.lastrowid)

    def set_global_role(self, *, user_id: int, global_role: str) -> None:
        self.connection.execute(
            """
            UPDATE users
            SET global_role = ?
            WHERE id = ?
            """,
            (global_role, user_id),
        )

    def list_admin_users(
        self,
        *,
        query: str = "",
        status: str = "all",
        global_role: str = "all",
    ) -> list[dict]:
        conditions: list[str] = []
        parameters: list[object] = []
        if query:
            pattern = f"%{query}%"
            conditions.append("(users.name LIKE ? OR users.email LIKE ?)")
            parameters.extend([pattern, pattern])
        if status == "active":
            conditions.append("users.is_active = 1")
        elif status == "disabled":
            conditions.append("users.is_active = 0")
        if global_role in {"admin", "user"}:
            conditions.append("users.global_role = ?")
            parameters.append(global_role)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.connection.execute(
            f"""
            SELECT
                users.id,
                users.name,
                users.email,
                users.global_role,
                users.is_active,
                users.disabled_at,
                users.disabled_by,
                users.disabled_reason,
                users.last_login_at,
                users.password_updated_at,
                users.created_at,
                COALESCE(disabled_users.name, '') AS disabled_by_name,
                COALESCE(disabled_users.email, '') AS disabled_by_email
            FROM users
            LEFT JOIN users AS disabled_users ON disabled_users.id = users.disabled_by
            {where_clause}
            ORDER BY users.is_active DESC, users.name, users.email
            """,
            parameters,
        ).fetchall()

    def count_active_admins(self) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            WHERE global_role = 'admin' AND is_active = 1
            """
        ).fetchone()
        return int(row["count"]) if row else 0

    def update_profile(self, *, user_id: int, name: str, global_role: str) -> None:
        self.connection.execute(
            """
            UPDATE users
            SET name = ?, global_role = ?
            WHERE id = ?
            """,
            (name, global_role, user_id),
        )

    def disable_user(
        self,
        *,
        user_id: int,
        disabled_by: int,
        disabled_reason: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE users
            SET
                is_active = 0,
                disabled_at = CURRENT_TIMESTAMP,
                disabled_by = ?,
                disabled_reason = ?
            WHERE id = ?
            """,
            (disabled_by, disabled_reason, user_id),
        )

    def enable_user(self, *, user_id: int) -> None:
        self.connection.execute(
            """
            UPDATE users
            SET
                is_active = 1,
                disabled_at = '',
                disabled_by = NULL,
                disabled_reason = ''
            WHERE id = ?
            """,
            (user_id,),
        )

    def set_password_hash(self, *, user_id: int, password_hash: str) -> None:
        self.connection.execute(
            """
            UPDATE users
            SET password_hash = ?, password_updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (password_hash, user_id),
        )

    def record_login(self, *, user_id: int) -> None:
        self.connection.execute(
            """
            UPDATE users
            SET last_login_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )

    def search_available_for_project(self, *, project_id: int, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self.connection.execute(
            """
            SELECT id, name, email, created_at
            FROM users
            WHERE (name LIKE ? OR email LIKE ?)
              AND is_active = 1
              AND id != COALESCE(
                  (SELECT owner_id FROM projects WHERE id = ?),
                  -1
              )
              AND id NOT IN (
                  SELECT user_id FROM project_members WHERE project_id = ?
              )
            ORDER BY name, email
            LIMIT 8
            """,
            (pattern, pattern, project_id, project_id),
        ).fetchall()
