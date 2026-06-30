from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends

from proteinhub.api.dependencies import map_domain_error
from proteinhub.api.schemas import (
    MemberCreateRequest,
    ProjectCreateRequest,
    ProteinCreateRequest,
)
from proteinhub.application.project_service import (
    add_project_member,
    create_project,
    get_project,
    list_project_members,
    list_projects,
)
from proteinhub.application.protein_service import (
    create_protein,
    list_proteins,
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

    return router
