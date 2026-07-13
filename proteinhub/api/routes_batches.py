from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends

from proteinhub.api.dependencies import map_domain_error
from proteinhub.api.schemas import (
    BatchCreateRequest,
    ExperimentCreateRequest,
    ExperimentWellResultUpdateRequest,
)
from proteinhub.application.batch_service import (
    create_batch,
    create_batch_experiment,
    get_batch,
    get_batch_experiment,
    list_batches,
    list_batch_experiments,
    update_experiment_well_result,
)
from proteinhub.domain.errors import DomainError


def create_batches_router(
    *,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/projects/{project_id}/batches")
    def project_batches(
        project_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_batches(connection, project_id=project_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/projects/{project_id}/batches")
    def create_project_batch(
        project_id: int,
        payload: BatchCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_batch(
                connection,
                project_id=project_id,
                user_id=user["id"],
                name=payload.name,
                protein_ids=payload.protein_ids,
                description=payload.description,
                plate_format=payload.plate_format,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/batches/{batch_id}")
    def batch_detail(
        batch_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return get_batch(connection, batch_id=batch_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/batches/{batch_id}/experiments")
    def batch_experiments(
        batch_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_batch_experiments(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/batches/{batch_id}/experiments")
    def create_experiment(
        batch_id: int,
        payload: ExperimentCreateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return create_batch_experiment(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
                experiment_type=payload.experiment_type,
                name=payload.name,
                description=payload.description,
                details=payload.details,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/experiments/{experiment_id}")
    def experiment_detail(
        experiment_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return get_batch_experiment(
                connection, experiment_id=experiment_id, user_id=user["id"]
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch("/experiments/{experiment_id}/wells/{well_id}/result")
    def update_experiment_result(
        experiment_id: int,
        well_id: int,
        payload: ExperimentWellResultUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_experiment_well_result(
                connection,
                experiment_id=experiment_id,
                well_id=well_id,
                user_id=user["id"],
                result_value=payload.result_value,
                result_note=payload.result_note,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
