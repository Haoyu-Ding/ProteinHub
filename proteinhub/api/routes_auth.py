from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import (
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from proteinhub.application.auth_service import authenticate_user
from proteinhub.domain.errors import DomainError
from proteinhub.security import create_token


def create_auth_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.post("/auth/login", response_model=TokenResponse)
    def login(
        payload: LoginRequest,
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            user = authenticate_user(
                connection,
                payload.email,
                payload.password,
                admin_emails=context.settings.admin_emails,
            )
            token = create_token(
                user["id"],
                context.settings.jwt_secret,
                issuer=context.settings.jwt_issuer,
                ttl_seconds=context.settings.token_ttl_seconds,
            )
            return {"access_token": token, "user": user}
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/me", response_model=UserResponse)
    def me(user: dict = Depends(current_user)) -> dict:
        return user

    return router
