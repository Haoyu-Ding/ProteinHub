from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, UploadFile

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.application.artifact_service import create_artifact, list_artifacts
from proteinhub.application.sequence_service import get_sequence
from proteinhub.domain.errors import DomainError


def create_sequences_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/sequences/{sequence_id}")
    def sequence_detail(
        sequence_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            sequence = get_sequence(connection, sequence_id=sequence_id, user_id=user["id"])
            return {
                "sequence": sequence,
                "artifacts": list_artifacts(
                    connection, sequence_id=sequence_id, user_id=user["id"]
                ),
            }
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/sequences/{sequence_id}/artifacts")
    def artifacts(
        sequence_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_artifacts(connection, sequence_id=sequence_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/sequences/{sequence_id}/artifacts")
    def upload_artifact(
        sequence_id: int,
        artifact_type: str = "file",
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            uploaded = create_artifact(
                connection,
                storage_root=context.storage_root,
                sequence_id=sequence_id,
                user_id=user["id"],
                filename=file.filename or "artifact.bin",
                content_type=file.content_type or "application/octet-stream",
                source=file.file,
                artifact_type=artifact_type,
            )
            return uploaded.artifact
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
