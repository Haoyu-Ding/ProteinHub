from __future__ import annotations

import sqlite3

from proteinhub.application.validation import required
from proteinhub.domain.errors import AuthenticationError, ConflictError, DomainError, NotFoundError
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import UserRepository
from proteinhub.security import hash_password, verify_password


def get_user(connection: sqlite3.Connection, user_id: int) -> dict:
    user = UserRepository(connection).get_public(user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


def register_user(connection: sqlite3.Connection, email: str, password: str) -> dict:
    normalized_email = required(email, "Email").lower()
    if len(password) < 8:
        raise DomainError("Password must be at least 8 characters")

    users = UserRepository(connection)
    try:
        with transaction(connection):
            user_id = users.insert(
                email=normalized_email,
                password_hash=hash_password(password),
            )
        return get_user(connection, user_id)
    except sqlite3.IntegrityError as exc:
        raise ConflictError("Email is already registered") from exc


def authenticate_user(connection: sqlite3.Connection, email: str, password: str) -> dict:
    user = UserRepository(connection).get_by_email(email.strip().lower())
    if not user or not verify_password(password, user["password_hash"]):
        raise AuthenticationError()
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}
