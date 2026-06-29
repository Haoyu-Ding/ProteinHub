from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from proteinhub.config import Settings
from proteinhub.security import create_token, decode_token
from proteinhub.services import (
    DomainError,
    add_project_member,
    authenticate_user,
    create_artifact,
    create_project,
    create_protein,
    create_sequence,
    get_artifact,
    get_project,
    get_sequence,
    get_user,
    list_artifacts,
    list_project_members,
    list_projects,
    list_proteins,
    list_sequences,
    register_user,
    soft_delete_artifact,
)
from proteinhub.storage import resolve_storage_path


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class MemberCreateRequest(BaseModel):
    email: str
    role: str = "member"


class ProteinCreateRequest(BaseModel):
    name: str
    description: str = ""


class SequenceCreateRequest(BaseModel):
    name: str
    sequence: str
    description: str = ""
    version_tag: str = ""


def map_domain_error(error: DomainError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)


def create_api_router(
    *,
    database_path: Path,
    storage_root: Path,
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def get_connection() -> sqlite3.Connection:
        from proteinhub.db import connect

        connection = connect(database_path)
        try:
            yield connection
        finally:
            connection.close()

    def current_user(
        authorization: Annotated[str | None, Header()] = None,
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.split(" ", 1)[1]
        try:
            payload = decode_token(
                token,
                settings.jwt_secret,
                issuer=settings.jwt_issuer,
            )
            return get_user(connection, int(payload["sub"]))
        except (DomainError, ValueError, KeyError):
            raise HTTPException(status_code=401, detail="Invalid bearer token") from None

    @router.post("/auth/register", response_model=TokenResponse)
    def register(
        payload: RegisterRequest,
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            user = register_user(connection, payload.email, payload.password)
            token = create_token(
                user["id"],
                settings.jwt_secret,
                issuer=settings.jwt_issuer,
                ttl_seconds=settings.token_ttl_seconds,
            )
            return {"access_token": token, "user": user}
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/auth/login", response_model=TokenResponse)
    def login(
        payload: LoginRequest,
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            user = authenticate_user(connection, payload.email, payload.password)
            token = create_token(
                user["id"],
                settings.jwt_secret,
                issuer=settings.jwt_issuer,
                ttl_seconds=settings.token_ttl_seconds,
            )
            return {"access_token": token, "user": user}
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/me")
    def me(user: dict = Depends(current_user)) -> dict:
        return user

    @router.get("/projects")
    def projects(
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        return list_projects(connection, user["id"])

    @router.post("/projects")
    def create_project_route(
        payload: ProjectCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_project(
                connection,
                user_id=user["id"],
                name=payload.name,
                description=payload.description,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/projects/{project_id}")
    def project_detail(
        project_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return {
                "project": get_project(connection, project_id=project_id, user_id=user["id"]),
                "members": list_project_members(
                    connection, project_id=project_id, user_id=user["id"]
                ),
            }
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/projects/{project_id}/members")
    def add_member_route(
        project_id: int,
        payload: MemberCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return add_project_member(
                connection,
                project_id=project_id,
                owner_user_id=user["id"],
                email=payload.email,
                role=payload.role,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/projects/{project_id}/proteins")
    def proteins(
        project_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_proteins(connection, project_id=project_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/projects/{project_id}/proteins")
    def create_protein_route(
        project_id: int,
        payload: ProteinCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_protein(
                connection,
                project_id=project_id,
                user_id=user["id"],
                name=payload.name,
                description=payload.description,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

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
                storage_root=storage_root,
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

    @router.get("/artifacts/{artifact_id}/download")
    def download_artifact(
        artifact_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> FileResponse:
        try:
            artifact = get_artifact(connection, artifact_id=artifact_id, user_id=user["id"])
            path = resolve_storage_path(storage_root, artifact["storage_path"])
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

