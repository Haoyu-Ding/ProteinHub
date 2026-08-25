from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import (
    MemberCreateRequest,
    MemberUpdateRequest,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectMemberResponse,
    ProjectProteinResponse,
    ProjectResponse,
    ProteinCreateRequest,
    ProteinResponse,
    ProteinSequenceCheckRequest,
    ProteinSequenceCheckResponse,
    ProteinStructureImportResponse,
    PublicProteinCreateRequest,
    PublicProteinResponse,
    PublicProteinUpdateRequest,
    StructureSequenceResponse,
    UserResponse,
)
from proteinhub.application.project_service import (
    add_project_member,
    create_project,
    delete_project,
    get_project,
    list_project_members,
    list_projects,
    search_project_member_candidates,
    update_project_member,
)
from proteinhub.application.protein_service import (
    check_project_protein_sequences,
    create_protein,
    create_protein_with_structure_file,
    import_proteins_from_structures,
    list_proteins,
    parse_protein_sequence,
)
from proteinhub.application.public_protein_service import (
    create_public_protein,
    delete_public_protein,
    list_public_proteins,
    update_public_protein,
)
from proteinhub.domain.errors import DomainError


def create_projects_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/projects", response_model=list[ProjectResponse])
    def projects(
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        return list_projects(connection, user["id"])

    @router.post("/projects", response_model=ProjectResponse)
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

    @router.delete("/projects/{project_id}", status_code=204)
    def delete_project_route(
        project_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> None:
        try:
            delete_project(connection, project_id=project_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
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

    @router.post("/projects/{project_id}/members", response_model=ProjectMemberResponse)
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

    @router.patch(
        "/projects/{project_id}/members/{member_user_id}",
        response_model=ProjectMemberResponse,
    )
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
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get(
        "/projects/{project_id}/member-candidates",
        response_model=list[UserResponse],
    )
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

    @router.get(
        "/projects/{project_id}/proteins",
        response_model=list[ProjectProteinResponse],
    )
    def proteins(
        project_id: int,
        ratings: list[str] = Query(default=[]),
        date_from: str = Query(default=""),
        date_to: str = Query(default=""),
        sort: str = Query(default="time_desc"),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_proteins(
                connection,
                project_id=project_id,
                user_id=user["id"],
                manual_ratings=ratings,
                date_from=date_from,
                date_to=date_to,
                sort=sort,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/projects/{project_id}/proteins", response_model=ProteinResponse)
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
                protein_type=payload.protein_type,
                target=payload.target,
                allow_high_similarity=payload.allow_high_similarity,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get(
        "/projects/{project_id}/public-proteins",
        response_model=list[PublicProteinResponse],
    )
    def public_proteins(
        project_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_public_proteins(
                connection,
                project_id=project_id,
                user_id=user["id"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/projects/{project_id}/public-proteins",
        response_model=PublicProteinResponse,
    )
    def create_public_protein_route(
        project_id: int,
        payload: PublicProteinCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_public_protein(
                connection,
                project_id=project_id,
                user_id=user["id"],
                name=payload.name,
                sequence=payload.sequence,
                description=payload.description,
                protein_type=payload.protein_type,
                target=payload.target,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch(
        "/projects/{project_id}/public-proteins/{public_protein_id}",
        response_model=PublicProteinResponse,
    )
    def update_public_protein_route(
        project_id: int,
        public_protein_id: int,
        payload: PublicProteinUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_public_protein(
                connection,
                project_id=project_id,
                public_protein_id=public_protein_id,
                user_id=user["id"],
                name=payload.name,
                sequence=payload.sequence,
                description=payload.description,
                protein_type=payload.protein_type,
                target=payload.target,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.delete(
        "/projects/{project_id}/public-proteins/{public_protein_id}",
        status_code=204,
    )
    def delete_public_protein_route(
        project_id: int,
        public_protein_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> None:
        try:
            delete_public_protein(
                connection,
                project_id=project_id,
                public_protein_id=public_protein_id,
                user_id=user["id"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/projects/{project_id}/proteins/sequence-check",
        response_model=ProteinSequenceCheckResponse,
    )
    def check_protein_sequences_route(
        project_id: int,
        payload: ProteinSequenceCheckRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return check_project_protein_sequences(
                connection,
                project_id=project_id,
                user_id=user["id"],
                items=[
                    {"name": item.name, "sequence": item.sequence}
                    for item in payload.items
                ],
                similarity_threshold=payload.similarity_threshold,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/projects/{project_id}/proteins/import-structures",
        response_model=ProteinStructureImportResponse,
    )
    def import_protein_structures_route(
        project_id: int,
        files: list[UploadFile] = File(...),
        score_file: UploadFile | None = File(default=None),
        protein_type: str = Form(default="TCR"),
        target: str = Form(default=""),
        description: str = Form(default=""),
        allow_high_similarity: bool = Form(default=False),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return import_proteins_from_structures(
                connection,
                storage_root=context.storage_root,
                project_id=project_id,
                user_id=user["id"],
                files=[
                    (
                        file.filename or "protein.pdb",
                        file.content_type or "application/octet-stream",
                        file.file.read(),
                    )
                    for file in files
                ],
                description=description,
                protein_type=protein_type,
                target=target,
                allow_high_similarity=allow_high_similarity,
                score_file=(
                    (
                        score_file.filename or "scores.csv",
                        score_file.content_type or "text/csv",
                        score_file.file.read(),
                    )
                    if score_file is not None
                    else None
                ),
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/projects/{project_id}/proteins/with-structure",
        response_model=ProteinResponse,
    )
    def create_protein_with_structure_route(
        project_id: int,
        name: str = Form(...),
        sequence: str = Form(...),
        protein_type: str = Form(default="TCR"),
        target: str = Form(default=""),
        description: str = Form(default=""),
        allow_high_similarity: bool = Form(default=False),
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_protein_with_structure_file(
                connection,
                storage_root=context.storage_root,
                project_id=project_id,
                user_id=user["id"],
                name=name,
                sequence=sequence,
                description=description,
                protein_type=protein_type,
                target=target,
                filename=file.filename or "structure.pdb",
                content_type=file.content_type or "application/octet-stream",
                content=file.file.read(),
                allow_high_similarity=allow_high_similarity,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/projects/{project_id}/proteins/parse-structure",
        response_model=StructureSequenceResponse,
    )
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
