from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import (
    BatchDetailResponse,
    BatchCreateRequest,
    BatchOrderStatusUpdateRequest,
    BatchSummaryResponse,
    BatchTranslationRequest,
    BatchTranslationResponse,
    BatchWellPositionUpdateRequest,
    ExperimentDetailResponse,
    ExperimentCreateRequest,
    ExperimentSummaryResponse,
    ExperimentWellResultResponse,
    ExperimentWellResultUpdateRequest,
)
from proteinhub.application.batch_service import (
    create_batch,
    create_batch_experiment,
    export_batch_plate_workbook,
    export_batch_summary_workbook,
    get_batch,
    get_batch_experiment,
    import_akta_results,
    list_batches,
    list_batch_experiments,
    translate_batch_sequences,
    update_batch_order_status,
    update_batch_well_position,
    update_experiment_well_result,
)
from proteinhub.domain.errors import DomainError


def create_batches_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/projects/{project_id}/batches",
        response_model=list[BatchSummaryResponse],
    )
    def project_batches(
        project_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_batches(connection, project_id=project_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post("/projects/{project_id}/batches", response_model=BatchDetailResponse)
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
                start_position=payload.start_position,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/batches/{batch_id}", response_model=BatchDetailResponse)
    def batch_detail(
        batch_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return get_batch(connection, batch_id=batch_id, user_id=user["id"])
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch(
        "/batches/{batch_id}/status",
        response_model=BatchDetailResponse,
    )
    def update_batch_status(
        batch_id: int,
        payload: BatchOrderStatusUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_batch_order_status(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
                order_status=payload.order_status,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.patch(
        "/batches/{batch_id}/wells/{well_id}/position",
        response_model=BatchDetailResponse,
    )
    def update_well_position(
        batch_id: int,
        well_id: int,
        payload: BatchWellPositionUpdateRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return update_batch_well_position(
                connection,
                batch_id=batch_id,
                well_id=well_id,
                user_id=user["id"],
                position=payload.position,
                mode=payload.mode,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/batches/{batch_id}/plate/export")
    def batch_plate_export(
        batch_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> Response:
        try:
            content = export_batch_plate_workbook(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
            )
            filename = f"batch-{batch_id}-plate.xlsx"
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/batches/{batch_id}/summary/export")
    def batch_summary_export(
        batch_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> Response:
        try:
            content = export_batch_summary_workbook(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
            )
            filename = f"batch-{batch_id}-summary.xlsx"
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/batches/{batch_id}/translations",
        response_model=BatchTranslationResponse,
    )
    def create_batch_translation(
        batch_id: int,
        payload: BatchTranslationRequest,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return translate_batch_sequences(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
                padding=payload.padding,
                add_additional_w=payload.add_additional_w,
                organism=payload.organism,
                backbone=payload.backbone,
                resistance=payload.resistance,
                settings=context.settings,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/batches/{batch_id}/akta-results",
        response_model=ExperimentDetailResponse,
    )
    def import_akta_results_route(
        batch_id: int,
        run_date: str = Form(...),
        files: list[UploadFile] = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return import_akta_results(
                connection,
                storage_root=context.storage_root,
                batch_id=batch_id,
                user_id=user["id"],
                run_date=run_date,
                files=[
                    (
                        file.filename or "akta.zip",
                        file.content_type or "application/zip",
                        file.file.read(),
                    )
                    for file in files
                ],
                settings=context.settings,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get(
        "/batches/{batch_id}/experiments",
        response_model=list[ExperimentSummaryResponse],
    )
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

    @router.post(
        "/batches/{batch_id}/experiments",
        response_model=ExperimentDetailResponse,
    )
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

    @router.get("/experiments/{experiment_id}", response_model=ExperimentDetailResponse)
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

    @router.patch(
        "/experiments/{experiment_id}/wells/{well_id}/result",
        response_model=ExperimentWellResultResponse,
    )
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
