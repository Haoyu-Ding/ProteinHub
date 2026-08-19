from __future__ import annotations

import sqlite3
from collections.abc import Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.application.artifact_service import get_artifact, soft_delete_artifact
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.storage.database_file_store import DatabaseFileStore
from proteinhub.infrastructure.storage.file_store import file_store_for


def create_artifacts_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/artifacts/{artifact_id}/download")
    def download_artifact(
        artifact_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> Response:
        try:
            artifact = get_artifact(connection, artifact_id=artifact_id, user_id=user["id"])
            if artifact.get("storage_backend") == "database":
                store = DatabaseFileStore(connection)
                content = store.read_artifact(artifact_id)
                if content is None:
                    raise HTTPException(status_code=404, detail="Artifact file missing")
                return Response(
                    content=content,
                    media_type=artifact["mime_type"],
                    headers=_download_headers(artifact["filename"]),
                )
            path = file_store_for(connection, context.storage_root).resolve(
                artifact["storage_path"]
            )
            if not path.exists():
                raise HTTPException(status_code=404, detail="Artifact file missing")
            return FileResponse(
                path,
                media_type=artifact["mime_type"],
                filename=artifact["filename"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.delete("/artifacts/{artifact_id}", status_code=204)
    def delete_artifact(
        artifact_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> None:
        try:
            soft_delete_artifact(connection, artifact_id=artifact_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    return router


def _download_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
