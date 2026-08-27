from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, Query

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import AdminSequenceSearchResultResponse
from proteinhub.application.admin_sequence_service import search_admin_sequences
from proteinhub.domain.errors import DomainError


def create_admin_sequences_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/admin/sequences",
        response_model=list[AdminSequenceSearchResultResponse],
    )
    def admin_sequences(
        q: str = Query(default=""),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return search_admin_sequences(
                connection,
                user_id=user["id"],
                query=q,
                limit=limit,
                offset=offset,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
