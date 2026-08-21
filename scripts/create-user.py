#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import shlex
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from proteinhub.application.auth_service import create_user
from proteinhub.config import get_settings
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.database.connection import connect, init_db


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a ProteinHub user without exposing public registration.",
    )
    parser.add_argument(
        "--env-file",
        default="/etc/proteinhub.env",
        help="Environment file to load before connecting to the database.",
    )
    parser.add_argument("--name", required=True, help="Display name for the user.")
    parser.add_argument("--email", required=True, help="Login email for the user.")
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Create the user with the global administrator role.",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Initial password. Omit to enter it interactively.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the initial password from standard input.",
    )
    args = parser.parse_args()

    if args.password and args.password_stdin:
        print("Use either --password or --password-stdin, not both.", file=sys.stderr)
        return 2

    load_env_file(Path(args.env_file))
    settings = get_settings()
    password = _password_from_args(args)
    role = "admin" if args.admin else "user"

    init_db(settings)
    connection = connect(settings)
    try:
        user = create_user(
            connection,
            email=args.email,
            password=password,
            name=args.name,
            global_role=role,
            admin_emails=settings.admin_emails,
        )
    except DomainError as error:
        print(f"Failed to create user: {error.message}", file=sys.stderr)
        return 1
    finally:
        connection.close()

    print(
        f"Created {user['global_role']} user {user['name']} "
        f"<{user['email']}> with id {user['id']}."
    )
    return 0


def _password_from_args(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    if args.password_stdin:
        return sys.stdin.read().strip()

    first = getpass.getpass("Initial password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise SystemExit("Passwords do not match.")
    return first


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        parsed = shlex.split(value, comments=False, posix=True)
        os.environ[key] = parsed[0] if parsed else ""


if __name__ == "__main__":
    sys.exit(main())
