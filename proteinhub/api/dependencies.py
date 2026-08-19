from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from proteinhub.config import Settings
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.database.connection import connect
from proteinhub.security import decode_token
from proteinhub.application.auth_service import get_user


@dataclass(frozen=True)
class ApiContext:
    database_path: Path
    storage_root: Path
    settings: Settings


def map_domain_error(error: DomainError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)


def build_dependencies(context: ApiContext):
    def get_connection() -> Iterator:
        connection = connect(context.settings)
        try:
            yield connection
        finally:
            connection.close()

    def current_user(
        authorization: Annotated[str | None, Header()] = None,
        connection = Depends(get_connection),
    ) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.split(" ", 1)[1]
        try:
            payload = decode_token(
                token,
                context.settings.jwt_secret,
                issuer=context.settings.jwt_issuer,
            )
            return get_user(
                connection,
                int(payload["sub"]),
                admin_emails=context.settings.admin_emails,
            )
        except (DomainError, ValueError, KeyError):
            raise HTTPException(status_code=401, detail="Invalid bearer token") from None

    return get_connection, current_user
