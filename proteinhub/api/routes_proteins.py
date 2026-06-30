from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends

from proteinhub.api.dependencies import map_domain_error
from proteinhub.api.schemas import SequenceCreateRequest
from proteinhub.application.sequence_service import create_sequence, list_sequences
from proteinhub.domain.errors import DomainError


def create_proteins_router(
    *,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/proteins/{protein_id}/sequences")
    def sequences(
        protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_sequences(connection, protein_id=protein_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/proteins/{protein_id}/sequences")
    def create_sequence_route(
        protein_id: int,
        payload: SequenceCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_sequence(
                connection,
                protein_id=protein_id,
                user_id=user["id"],
                name=payload.name,
                sequence=payload.sequence,
                description=payload.description,
                version_tag=payload.version_tag,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
