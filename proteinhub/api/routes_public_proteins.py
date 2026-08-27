from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import PublicProteinDetailResponse
from proteinhub.application.public_protein_service import get_public_protein_detail
from proteinhub.domain.errors import DomainError


def create_public_proteins_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/public-proteins/{public_protein_id}",
        response_model=PublicProteinDetailResponse,
    )
    def public_protein_detail(
        public_protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return get_public_protein_detail(
                connection,
                public_protein_id=public_protein_id,
                user_id=user["id"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
