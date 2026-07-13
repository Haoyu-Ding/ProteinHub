from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, UploadFile

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.application.artifact_service import create_artifact, list_artifacts
from proteinhub.application.batch_service import list_protein_batch_results
from proteinhub.application.protein_service import (
    get_protein,
    parse_protein_structure_for_existing,
)
from proteinhub.domain.errors import DomainError


def create_proteins_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/proteins/{protein_id}")
    def protein_detail(
        protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            protein = get_protein(connection, protein_id=protein_id, user_id=user["id"])
            return {
                "protein": protein,
                "artifacts": list_artifacts(
                    connection, protein_id=protein_id, user_id=user["id"]
                ),
                "batch_results": list_protein_batch_results(
                    connection, protein_id=protein_id, user_id=user["id"]
                ),
            }
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/proteins/{protein_id}/artifacts")
    def artifacts(
        protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_artifacts(connection, protein_id=protein_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/proteins/{protein_id}/artifacts")
    def upload_artifact(
        protein_id: int,
        artifact_type: str = "file",
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            uploaded = create_artifact(
                connection,
                storage_root=context.storage_root,
                protein_id=protein_id,
                user_id=user["id"],
                filename=file.filename or "artifact.bin",
                content_type=file.content_type or "application/octet-stream",
                source=file.file,
                artifact_type=artifact_type,
            )
            return uploaded.artifact
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/proteins/{protein_id}/parse-structure")
    def parse_existing_protein_structure_route(
        protein_id: int,
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return parse_protein_structure_for_existing(
                connection,
                protein_id=protein_id,
                user_id=user["id"],
                filename=file.filename or "structure.pdb",
                content=file.file.read(),
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
