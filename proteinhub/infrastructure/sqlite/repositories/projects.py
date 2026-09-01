from __future__ import annotations

import sqlite3


class ProjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_role(self, *, project_id: int, user_id: int) -> str | None:
        row = self.connection.execute(
            """
            SELECT
                projects.owner_id,
                project_members.user_id AS member_user_id
            FROM projects
            LEFT JOIN project_members
                ON project_members.project_id = projects.id
               AND project_members.user_id = ?
            WHERE projects.id = ?
            """,
            (user_id, project_id),
        ).fetchone()
        if not row:
            return None
        if row["owner_id"] == user_id:
            return "owner"
        if row["member_user_id"] is not None:
            return "member"
        return None

    def list_for_user(self, user_id: int, status: str) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                projects.*,
                owner_users.name AS owner_name,
                owner_users.email AS owner_email,
                CASE
                    WHEN projects.owner_id = ? THEN 'owner'
                    ELSE 'member'
                END AS role
            FROM projects
            JOIN users AS owner_users ON owner_users.id = projects.owner_id
            LEFT JOIN project_members
                ON project_members.project_id = projects.id
               AND project_members.user_id = ?
            WHERE (projects.owner_id = ?
               OR project_members.user_id = ?)
              AND projects.status = ?
            ORDER BY projects.created_at DESC, projects.id DESC
            """,
            (user_id, user_id, user_id, user_id, status),
        ).fetchall()

    def list_all_as_owner(self, status: str) -> list[dict]:
        return self.connection.execute(
            """
            SELECT
                projects.*,
                owner_users.name AS owner_name,
                owner_users.email AS owner_email,
                'owner' AS role
            FROM projects
            JOIN users AS owner_users ON owner_users.id = projects.owner_id
            WHERE projects.status = ?
            ORDER BY projects.created_at DESC, projects.id DESC
            """,
            (status,),
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

    def update_status(self, *, project_id: int, status: str) -> None:
        self.connection.execute(
            """
            UPDATE projects
            SET status = ?
            WHERE id = ?
            """,
            (status, project_id),
        )

    def insert_member(self, *, project_id: int, user_id: int, role: str) -> None:
        self.connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (?, ?, ?)
            """,
            (project_id, user_id, role),
        )

    def get_member(self, *, project_id: int, user_id: int) -> dict | None:
        return self.connection.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,
                CASE
                    WHEN projects.owner_id = users.id THEN 'owner'
                    ELSE 'member'
                END AS role,
                COALESCE(project_members.created_at, projects.created_at) AS created_at
            FROM projects
            JOIN users ON users.id = ?
            LEFT JOIN project_members
                ON project_members.project_id = projects.id
               AND project_members.user_id = users.id
            WHERE projects.id = ?
              AND (
                  projects.owner_id = users.id
                  OR project_members.user_id IS NOT NULL
              )
            """,
            (user_id, project_id),
        ).fetchone()

    def count_owners(self, project_id: int) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS owner_count
            FROM projects
            WHERE id = ? AND owner_id IS NOT NULL
            """,
            (project_id,),
        ).fetchone()
        return int(row["owner_count"])

    def update_member(self, *, project_id: int, user_id: int, role: str) -> None:
        self.connection.execute(
            """
            UPDATE project_members
            SET role = ?
            WHERE project_id = ? AND user_id = ?
            """,
            (role, project_id, user_id),
        )

    def list_members(self, project_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT *
            FROM (
                SELECT
                    users.id,
                    users.name,
                    users.email,
                    'owner' AS role,
                    COALESCE(project_members.created_at, projects.created_at) AS created_at
                FROM projects
                JOIN users ON users.id = projects.owner_id
                LEFT JOIN project_members
                    ON project_members.project_id = projects.id
                   AND project_members.user_id = users.id
                WHERE projects.id = ?
                UNION ALL
                SELECT
                    users.id,
                    users.name,
                    users.email,
                    'member' AS role,
                    project_members.created_at
                FROM project_members
                JOIN users ON users.id = project_members.user_id
                JOIN projects ON projects.id = project_members.project_id
                WHERE project_members.project_id = ?
                  AND users.id != projects.owner_id
            ) AS project_member_rows
            ORDER BY role DESC, name, email
            """,
            (project_id, project_id),
        ).fetchall()

    def list_members_for_projects(self, project_ids: list[int]) -> list[dict]:
        if not project_ids:
            return []
        placeholders = ",".join("?" for _ in project_ids)
        return self.connection.execute(
            f"""
            SELECT
                project_members.project_id,
                users.id,
                users.name,
                users.email
            FROM project_members
            JOIN users ON users.id = project_members.user_id
            JOIN projects ON projects.id = project_members.project_id
            WHERE project_members.project_id IN ({placeholders})
              AND users.id != projects.owner_id
            ORDER BY project_members.project_id, users.name, users.email
            """,
            tuple(project_ids),
        ).fetchall()
