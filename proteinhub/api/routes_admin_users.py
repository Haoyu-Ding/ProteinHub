from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, Query

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import (
    AdminUserCreateRequest,
    AdminUserDisableRequest,
    AdminUserPasswordResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from proteinhub.application.admin_user_service import (
    create_admin_user,
    disable_admin_user,
    enable_admin_user,
    list_admin_users,
    reset_admin_user_password,
    update_admin_user,
)
from proteinhub.domain.errors import DomainError


def create_admin_users_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/users", response_model=list[AdminUserResponse])
    def admin_users(
        q: str = Query(default=""),
        status: str = Query(default="all"),
        global_role: str = Query(default="all"),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_admin_users(
                connection,
                actor_user_id=user["id"],
                query=q,
                status=status,
                global_role=global_role,
                admin_emails=context.settings.admin_emails,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/admin/users", response_model=AdminUserPasswordResponse)
    def create_user_route(
        payload: AdminUserCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_admin_user(
                connection,
                actor_user_id=user["id"],
                name=payload.name,
                email=payload.email,
                global_role=payload.global_role,
                admin_emails=context.settings.admin_emails,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch("/admin/users/{target_user_id}", response_model=AdminUserResponse)
    def update_user_route(
        target_user_id: int,
        payload: AdminUserUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_admin_user(
                connection,
                actor_user_id=user["id"],
                target_user_id=target_user_id,
                name=payload.name,
                global_role=payload.global_role,
                admin_emails=context.settings.admin_emails,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/admin/users/{target_user_id}/disable",
        response_model=AdminUserResponse,
    )
    def disable_user_route(
        target_user_id: int,
        payload: AdminUserDisableRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return disable_admin_user(
                connection,
                actor_user_id=user["id"],
                target_user_id=target_user_id,
                reason=payload.reason,
                admin_emails=context.settings.admin_emails,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/admin/users/{target_user_id}/enable", response_model=AdminUserResponse)
    def enable_user_route(
        target_user_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return enable_admin_user(
                connection,
                actor_user_id=user["id"],
                target_user_id=target_user_id,
                admin_emails=context.settings.admin_emails,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/admin/users/{target_user_id}/reset-password",
        response_model=AdminUserPasswordResponse,
    )
    def reset_password_route(
        target_user_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return reset_admin_user_password(
                connection,
                actor_user_id=user["id"],
                target_user_id=target_user_id,
                admin_emails=context.settings.admin_emails,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
