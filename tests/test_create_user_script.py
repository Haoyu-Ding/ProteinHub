from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from proteinhub.security import verify_password


def test_create_user_script_creates_admin_user(tmp_path: Path) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"
    env = os.environ.copy()
    env.pop("PROTEINHUB_DATABASE_URL", None)
    env["PROTEINHUB_DATABASE"] = str(database_path)
    env["PROTEINHUB_STORAGE_DIR"] = str(tmp_path / "storage")
    env["PROTEINHUB_JWT_SECRET"] = "test-secret"
    env["PROTEINHUB_NICEGUI_STORAGE_SECRET"] = "test-storage-secret"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/create-user.py",
            "--env-file",
            str(tmp_path / "missing.env"),
            "--name",
            "运维管理员",
            "--email",
            "ops@example.com",
            "--admin",
            "--password",
            "password123",
        ],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Created admin user" in result.stdout

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        user = connection.execute(
            "SELECT name, email, password_hash, global_role FROM users WHERE email = ?",
            ("ops@example.com",),
        ).fetchone()
    finally:
        connection.close()

    assert user is not None
    assert user["name"] == "运维管理员"
    assert user["global_role"] == "admin"
    assert verify_password("password123", user["password_hash"])
