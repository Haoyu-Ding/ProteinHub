from __future__ import annotations

import secrets
import sqlite3

from proteinhub.application.auth_service import create_user
from proteinhub.application.permissions import require_admin
from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import UserRepository
from proteinhub.security import hash_password


ACCOUNT_STATUSES = {"all", "active", "disabled"}
GLOBAL_ROLES = {"admin", "user"}
TEMPORARY_PASSWORD_BYTES = 12


def list_admin_users(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    query: str = "",
    status: str = "all",
    global_role: str = "all",
    admin_emails: tuple[str, ...] = (),
) -> list[dict]:
    require_admin(connection, user_id=actor_user_id)
    _sync_configured_admin_roles(connection, admin_emails=admin_emails)
    return UserRepository(connection).list_admin_users(
        query=(query or "").strip(),
        status=_normalize_account_status(status),
        global_role=_normalize_global_role_filter(global_role),
    )


def create_admin_user(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    name: str,
    email: str,
    global_role: str = "user",
    admin_emails: tuple[str, ...] = (),
) -> dict:
    require_admin(connection, user_id=actor_user_id)
    temporary_password = _generate_temporary_password()
    user = create_user(
        connection,
        name=name,
        email=email,
        password=temporary_password,
        global_role=_normalize_global_role(global_role),
        admin_emails=admin_emails,
    )
    return {
        "user": _get_admin_user(connection, user_id=user["id"]),
        "temporary_password": temporary_password,
    }


def update_admin_user(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    target_user_id: int,
    name: str | None = None,
    global_role: str | None = None,
    admin_emails: tuple[str, ...] = (),
) -> dict:
    require_admin(connection, user_id=actor_user_id)
    _sync_configured_admin_roles(connection, admin_emails=admin_emails)
    users = UserRepository(connection)
    target = _get_admin_user(connection, user_id=target_user_id)
    next_name = required(name, "Name") if name is not None else str(target["name"])
    current_role = str(target.get("global_role") or "user")
    next_role = (
        _normalize_global_role(global_role)
        if global_role is not None
        else current_role
    )
    _ensure_configured_admin_can_keep_role(target, next_role, admin_emails=admin_emails)
    _ensure_active_admin_remains(
        users,
        target=target,
        next_role=next_role,
    )

    with transaction(connection):
        users.update_profile(
            user_id=target_user_id,
            name=next_name,
            global_role=next_role,
        )
    return _get_admin_user(connection, user_id=target_user_id)


def disable_admin_user(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    target_user_id: int,
    reason: str = "",
    admin_emails: tuple[str, ...] = (),
) -> dict:
    require_admin(connection, user_id=actor_user_id)
    _sync_configured_admin_roles(connection, admin_emails=admin_emails)
    if int(actor_user_id) == int(target_user_id):
        raise DomainError("You cannot disable your own account")

    users = UserRepository(connection)
    target = _get_admin_user(connection, user_id=target_user_id)
    if _is_active_admin(target) and users.count_active_admins() <= 1:
        raise DomainError("At least one active administrator is required")

    with transaction(connection):
        users.disable_user(
            user_id=target_user_id,
            disabled_by=actor_user_id,
            disabled_reason=(reason or "").strip(),
        )
    return _get_admin_user(connection, user_id=target_user_id)


def enable_admin_user(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    target_user_id: int,
    admin_emails: tuple[str, ...] = (),
) -> dict:
    require_admin(connection, user_id=actor_user_id)
    _sync_configured_admin_roles(connection, admin_emails=admin_emails)
    _get_admin_user(connection, user_id=target_user_id)
    users = UserRepository(connection)
    with transaction(connection):
        users.enable_user(user_id=target_user_id)
    return _get_admin_user(connection, user_id=target_user_id)


def reset_admin_user_password(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    target_user_id: int,
    admin_emails: tuple[str, ...] = (),
) -> dict:
    require_admin(connection, user_id=actor_user_id)
    _sync_configured_admin_roles(connection, admin_emails=admin_emails)
    _get_admin_user(connection, user_id=target_user_id)
    users = UserRepository(connection)
    temporary_password = _generate_temporary_password()
    with transaction(connection):
        users.set_password_hash(
            user_id=target_user_id,
            password_hash=hash_password(temporary_password),
        )
    return {
        "user": _get_admin_user(connection, user_id=target_user_id),
        "temporary_password": temporary_password,
    }


def _get_admin_user(connection: sqlite3.Connection, *, user_id: int) -> dict:
    user = UserRepository(connection).get_admin_user(user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


def _ensure_active_admin_remains(
    users: UserRepository,
    *,
    target: dict,
    next_role: str,
) -> None:
    if (
        _is_active_admin(target)
        and next_role != "admin"
        and users.count_active_admins() <= 1
    ):
        raise DomainError("At least one active administrator is required")


def _ensure_configured_admin_can_keep_role(
    target: dict,
    next_role: str,
    *,
    admin_emails: tuple[str, ...],
) -> None:
    if (
        str(target.get("email") or "").lower() in _normalized_admin_emails(admin_emails)
        and next_role != "admin"
    ):
        raise DomainError("Configured administrator accounts must keep the admin role")


def _sync_configured_admin_roles(
    connection: sqlite3.Connection,
    *,
    admin_emails: tuple[str, ...],
) -> None:
    normalized_emails = _normalized_admin_emails(admin_emails)
    if not normalized_emails:
        return
    users = UserRepository(connection)
    with transaction(connection):
        for email in normalized_emails:
            user = users.get_by_email(email)
            if user and user.get("global_role") != "admin":
                users.set_global_role(user_id=user["id"], global_role="admin")


def _normalize_account_status(value: str) -> str:
    status = (value or "all").strip().lower()
    if status not in ACCOUNT_STATUSES:
        raise DomainError("Account status must be all, active, or disabled")
    return status


def _normalize_global_role_filter(value: str) -> str:
    role = (value or "all").strip().lower()
    if role == "all":
        return role
    return _normalize_global_role(role)


def _normalize_global_role(value: str) -> str:
    role = (value or "user").strip().lower()
    if role not in GLOBAL_ROLES:
        raise DomainError("Global role must be user or admin")
    return role


def _is_active_admin(user: dict) -> bool:
    return bool(user.get("is_active", 1)) and user.get("global_role") == "admin"


def _normalized_admin_emails(admin_emails: tuple[str, ...]) -> set[str]:
    return {email.strip().lower() for email in admin_emails if email.strip()}


def _generate_temporary_password() -> str:
    return secrets.token_urlsafe(TEMPORARY_PASSWORD_BYTES)
