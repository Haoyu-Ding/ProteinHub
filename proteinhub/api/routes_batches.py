from __future__ import annotations

import sqlite3
from collections.abc import Callable
from urllib.parse import quote

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
    ExperimentRawFileResponse,
    ExperimentSummaryResponse,
    ExperimentWellResultResponse,
    ExperimentWellResultUpdateRequest,
)
from proteinhub.application.batch_service import (
    create_batch,
    create_batch_experiment,
    delete_batch,
    export_batch_plate_workbook,
    export_batch_summary_workbook,
    get_batch,
    get_batch_experiment,
    import_akta_results,
    import_batch_translation_csv,
    import_spr_concentrations,
    import_spr_results,
    list_batches,
    list_batch_experiments,
    translate_batch_sequences,
    update_batch_order_status,
    update_batch_well_position,
    update_experiment_well_result,
)
from proteinhub.application.experiment_raw_file_service import (
    get_experiment_raw_file_download,
    list_experiment_raw_files,
)
from proteinhub.application.hplc_service import import_hplc_results
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
                receipt_note=payload.receipt_note,
                received_well_ids=payload.received_well_ids,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.delete("/batches/{batch_id}", status_code=204)
    def delete_batch_route(
        batch_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> None:
        try:
            delete_batch(connection, batch_id=batch_id, user_id=user["id"])
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
        "/batches/{batch_id}/translations/import-csv",
        response_model=BatchTranslationResponse,
    )
    def import_batch_translation_csv_route(
        batch_id: int,
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return import_batch_translation_csv(
                connection,
                batch_id=batch_id,
                user_id=user["id"],
                filename=file.filename or "translations.csv",
                content=file.file.read(),
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
        position_mapping_file: UploadFile | None = File(default=None),
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
                position_mapping_file=(
                    (
                        position_mapping_file.filename or "position-mapping.csv",
                        position_mapping_file.content_type or "text/csv",
                        position_mapping_file.file.read(),
                    )
                    if position_mapping_file is not None
                    else None
                ),
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/batches/{batch_id}/spr-results",
        response_model=ExperimentDetailResponse,
    )
    def import_spr_results_route(
        batch_id: int,
        run_date: str = Form(...),
        file: UploadFile = File(...),
        position_mapping_file: UploadFile | None = File(default=None),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return import_spr_results(
                connection,
                storage_root=context.storage_root,
                batch_id=batch_id,
                user_id=user["id"],
                run_date=run_date,
                filename=file.filename or "spr-results.pptx",
                content_type=file.content_type
                or "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                content=file.file.read(),
                position_mapping_file=(
                    (
                        position_mapping_file.filename or "position-mapping.csv",
                        position_mapping_file.content_type or "text/csv",
                        position_mapping_file.file.read(),
                    )
                    if position_mapping_file is not None
                    else None
                ),
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/batches/{batch_id}/spr-concentrations",
        response_model=ExperimentDetailResponse,
    )
    def import_spr_concentrations_route(
        batch_id: int,
        run_date: str = Form(...),
        file: UploadFile = File(...),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return import_spr_concentrations(
                connection,
                storage_root=context.storage_root,
                batch_id=batch_id,
                user_id=user["id"],
                run_date=run_date,
                filename=file.filename or "spr-concentration.csv",
                content_type=file.content_type or "text/csv",
                content=file.file.read(),
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.post(
        "/batches/{batch_id}/hplc-results",
        response_model=ExperimentDetailResponse,
    )
    def import_hplc_results_route(
        batch_id: int,
        source_name: str = Form(default=""),
        files: list[UploadFile] = File(...),
        position_mapping_file: UploadFile | None = File(default=None),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return import_hplc_results(
                connection,
                storage_root=context.storage_root,
                batch_id=batch_id,
                user_id=user["id"],
                source_name=source_name,
                files=[
                    (
                        file.filename or "hplc.csv",
                        file.content_type or "text/csv",
                        file.file.read(),
                    )
                    for file in files
                ],
                position_mapping_file=(
                    (
                        position_mapping_file.filename or "position-mapping.csv",
                        position_mapping_file.content_type or "text/csv",
                        position_mapping_file.file.read(),
                    )
                    if position_mapping_file is not None
                    else None
                ),
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

    @router.get(
        "/experiments/{experiment_id}/raw-files",
        response_model=list[ExperimentRawFileResponse],
    )
    def experiment_raw_files(
        experiment_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> list[dict]:
        try:
            return list_experiment_raw_files(
                connection,
                experiment_id=experiment_id,
                user_id=user["id"],
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    @router.get("/experiment-raw-files/{raw_file_id}/download")
    def download_experiment_raw_file(
        raw_file_id: int,
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> Response:
        try:
            raw_file, content = get_experiment_raw_file_download(
                connection,
                raw_file_id=raw_file_id,
                user_id=user["id"],
            )
            return Response(
                content=content,
                media_type=raw_file["mime_type"],
                headers={
                    "Content-Disposition": (
                        f"attachment; filename*=UTF-8''{quote(raw_file['filename'])}"
                    )
                },
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
