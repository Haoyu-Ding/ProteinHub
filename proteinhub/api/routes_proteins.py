from __future__ import annotations

import sqlite3
from collections.abc import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import (
    ArtifactResponse,
    ProteinManualRatingUpdateRequest,
    ProteinDetailResponse,
    ProteinResponse,
    StructureSequenceResponse,
)
from proteinhub.application.artifact_service import create_artifact, list_artifacts
from proteinhub.application.batch_service import list_protein_batch_results
from proteinhub.application.protein_service import (
    get_protein,
    get_protein_structure_file,
    parse_protein_structure_for_existing,
    update_protein_manual_rating,
)
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.storage.database_file_store import DatabaseFileStore
from proteinhub.infrastructure.storage.file_store import file_store_for


def create_proteins_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/proteins/{protein_id}", response_model=ProteinDetailResponse)
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
                "access_role": protein.get("access_role", ""),
            }
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch("/proteins/{protein_id}/manual-rating", response_model=ProteinResponse)
    def update_manual_rating(
        protein_id: int,
        payload: ProteinManualRatingUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_protein_manual_rating(
                connection,
                protein_id=protein_id,
                user_id=user["id"],
                manual_rating=payload.manual_rating,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get(
        "/proteins/{protein_id}/artifacts",
        response_model=list[ArtifactResponse],
    )
    def artifacts(
        protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_artifacts(connection, protein_id=protein_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/proteins/{protein_id}/structure/download")
    def download_protein_structure(
        protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> Response:
        try:
            protein = get_protein_structure_file(
                connection, protein_id=protein_id, user_id=user["id"]
            )
            if protein.get("structure_storage_backend") == "database":
                content = DatabaseFileStore(connection).read_protein_structure(protein_id)
                if content is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Protein structure file missing",
                    )
                return Response(
                    content=content,
                    media_type=protein["structure_mime_type"],
                    headers=_download_headers(protein["structure_filename"]),
                )
            path = file_store_for(connection, context.storage_root).resolve(
                protein["structure_storage_path"]
            )
            if not path.exists():
                raise HTTPException(status_code=404, detail="Protein structure file missing")
            return FileResponse(
                path,
                media_type=protein["structure_mime_type"],
                filename=protein["structure_filename"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/proteins/{protein_id}/artifacts",
        response_model=ArtifactResponse,
    )
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

    @router.post(
        "/proteins/{protein_id}/parse-structure",
        response_model=StructureSequenceResponse,
    )
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


def _download_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
