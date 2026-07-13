from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Query, UploadFile

from proteinhub.api.dependencies import map_domain_error
from proteinhub.api.schemas import (
    MemberCreateRequest,
    MemberUpdateRequest,
    ProjectCreateRequest,
    ProteinCreateRequest,
)
from proteinhub.application.project_service import (
    add_project_member,
    create_project,
    get_project,
    list_project_members,
    list_projects,
    search_project_member_candidates,
    update_project_member,
)
from proteinhub.application.protein_service import (
    create_protein,
    list_proteins,
    parse_protein_sequence,
)
from proteinhub.domain.errors import DomainError


def create_projects_router(
    *,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

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
                discipline=payload.discipline,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch("/projects/{project_id}/members/{member_user_id}")
    def update_member_route(
        project_id: int,
        member_user_id: int,
        payload: MemberUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_project_member(
                connection,
                project_id=project_id,
                owner_user_id=user["id"],
                member_user_id=member_user_id,
                role=payload.role,
                discipline=payload.discipline,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/projects/{project_id}/member-candidates")
    def member_candidates(
        project_id: int,
        query: str = Query(default=""),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return search_project_member_candidates(
                connection,
                project_id=project_id,
                owner_user_id=user["id"],
                query=query,
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
                sequence=payload.sequence,
                description=payload.description,
                version_tag=payload.version_tag,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/projects/{project_id}/proteins/parse-structure")
    def parse_protein_structure_route(
        project_id: int,
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return parse_protein_sequence(
                connection,
                project_id=project_id,
                user_id=user["id"],
                filename=file.filename or "structure.pdb",
                content=file.file.read(),
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
