from __future__ import annotations

import sqlite3


class ProjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_role(self, *, project_id: int, user_id: int) -> str | None:
        row = self.connection.execute(
            """
            SELECT role
            FROM project_members
            WHERE project_id = ? AND user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()
        return row["role"] if row else None

    def list_for_user(self, user_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT projects.*, project_members.role
            FROM projects
            JOIN project_members ON project_members.project_id = projects.id
            WHERE project_members.user_id = ?
            ORDER BY projects.created_at DESC, projects.id DESC
            """,
            (user_id,),
        ).fetchall()

    def insert(self, *, name: str, description: str, owner_id: int) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO projects (name, description, owner_id)
            VALUES (?, ?, ?)
            """,
            (name, description, owner_id),
        )
        return int(cursor.lastrowid)

    def get(self, project_id: int) -> dict | None:
        return self.connection.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    def insert_member(
        self, *, project_id: int, user_id: int, role: str, discipline: str = "other"
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role, discipline)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, user_id, role, discipline),
        )

    def get_member(self, *, project_id: int, user_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                project_members.role,
                project_members.discipline,
                project_members.created_at
            FROM project_members
            JOIN users ON users.id = project_members.user_id
            WHERE project_members.project_id = ? AND project_members.user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()

    def count_owners(self, project_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS owner_count
            FROM project_members
            WHERE project_id = ? AND role = 'owner'
            """,
            (project_id,),
        ).fetchone()
        return int(row["owner_count"])

    def update_member(
        self, *, project_id: int, user_id: int, role: str, discipline: str
    ) -> None:
        self.connection.execute(
            """
            UPDATE project_members
            SET role = ?, discipline = ?
            WHERE project_id = ? AND user_id = ?
            """,
            (role, discipline, project_id, user_id),
        )

    def list_members(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                project_members.role,
                project_members.discipline,
                project_members.created_at
            FROM project_members
            JOIN users ON users.id = project_members.user_id
            WHERE project_members.project_id = ?
            ORDER BY project_members.role DESC, users.name, users.email
            """,
            (project_id,),
        ).fetchall()
