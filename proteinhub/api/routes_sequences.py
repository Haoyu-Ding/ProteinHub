from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, UploadFile

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import (
    SequenceCommentCreateRequest,
    SequenceWorkflowUpdateRequest,
)
from proteinhub.application.artifact_service import create_artifact, list_artifacts
from proteinhub.application.project_service import list_project_members
from proteinhub.application.sequence_service import (
    create_sequence_comment,
    get_sequence,
    list_sequence_comments,
    update_sequence_workflow,
)
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
                "project_members": list_project_members(
                    connection,
                    project_id=sequence["project_id"],
                    user_id=user["id"],
                ),
                "artifacts": list_artifacts(
                    connection, sequence_id=sequence_id, user_id=user["id"]
                ),
                "comments": list_sequence_comments(
                    connection, sequence_id=sequence_id, user_id=user["id"]
                ),
            }
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch("/sequences/{sequence_id}/workflow")
    def update_workflow(
        sequence_id: int,
        payload: SequenceWorkflowUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_sequence_workflow(
                connection,
                sequence_id=sequence_id,
                user_id=user["id"],
                status=payload.status,
                priority=payload.priority,
                assigned_to=payload.assigned_to,
                discipline_owner=payload.discipline_owner,
                design_rationale=payload.design_rationale,
                handoff_note=payload.handoff_note,
                risk_note=payload.risk_note,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/sequences/{sequence_id}/comments")
    def create_comment(
        sequence_id: int,
        payload: SequenceCommentCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_sequence_comment(
                connection,
                sequence_id=sequence_id,
                user_id=user["id"],
                body=payload.body,
            )
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
