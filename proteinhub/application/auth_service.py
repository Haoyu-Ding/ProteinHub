from __future__ import annotations

import sqlite3

from proteinhub.application.validation import required
from proteinhub.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
)
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import UserRepository
from proteinhub.security import hash_password, verify_password


def get_user(
    connection: sqlite3.Connection,
    user_id: int,
    *,
    admin_emails: tuple[str, ...] = (),
) -> dict:
    user = UserRepository(connection).get_public(user_id)
    if not user:
        raise NotFoundError("User not found")
    user = _apply_configured_admin_role(
        connection,
        user,
        admin_emails=admin_emails,
    )
    if not _is_active(user):
        raise AuthenticationError("Account is disabled")
    return user


def register_user(
    connection: sqlite3.Connection,
    email: str,
    password: str,
    name: str,
    *,
    admin_emails: tuple[str, ...] = (),
) -> dict:
    return create_user(
        connection,
        email=email,
        password=password,
        name=name,
        global_role="user",
        admin_emails=admin_emails,
    )


def create_user(
    connection: sqlite3.Connection,
    *,
    email: str,
    password: str,
    name: str,
    global_role: str = "user",
    admin_emails: tuple[str, ...] = (),
) -> dict:
    normalized_email = required(email, "Email").lower()
    display_name = required(name, "Name")
    if len(password) < 8:
        raise DomainError("Password must be at least 8 characters")
    normalized_role = _normalize_global_role(global_role)

    users = UserRepository(connection)
    try:
        with transaction(connection):
            user_id = users.insert(
                name=display_name,
                email=normalized_email,
                password_hash=hash_password(password),
            )
            if normalized_role != "user":
                users.set_global_role(user_id=user_id, global_role=normalized_role)
        return get_user(connection, user_id, admin_emails=admin_emails)
    except sqlite3.IntegrityError as exc:
        raise ConflictError("Email is already registered") from exc


def authenticate_user(
    connection: sqlite3.Connection,
    email: str,
    password: str,
    *,
    admin_emails: tuple[str, ...] = (),
) -> dict:
    user = UserRepository(connection).get_by_email(email.strip().lower())
    if not user or not verify_password(password, user["password_hash"]):
        raise AuthenticationError()
    get_user(connection, user["id"], admin_emails=admin_emails)
    users = UserRepository(connection)
    with transaction(connection):
        users.record_login(user_id=user["id"])
    return get_user(connection, user["id"], admin_emails=admin_emails)


def _apply_configured_admin_role(
    connection: sqlite3.Connection,
    user: dict,
    *,
    admin_emails: tuple[str, ...],
) -> dict:
    normalized_admin_emails = {email.lower() for email in admin_emails}
    normalized_email = str(user["email"]).lower()
    if normalized_email in normalized_admin_emails and user.get("global_role") != "admin":
        UserRepository(connection).set_global_role(
            user_id=user["id"],
            global_role="admin",
        )
        connection.commit()
        user = dict(user)
        user["global_role"] = "admin"
    user.setdefault("global_role", "user")
    return user


def _normalize_global_role(value: str) -> str:
    role = (value or "user").strip().lower()
    if role not in {"user", "admin"}:
        raise DomainError("Global role must be user or admin")
    return role


def _is_active(user: dict) -> bool:
    return bool(user.get("is_active", 1))
