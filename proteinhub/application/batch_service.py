from __future__ import annotations

import json
import math
import re
import sqlite3
from collections.abc import Mapping
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from proteinhub.application.permissions import (
    project_for_protein,
    require_project_read,
    require_project_write,
)
from proteinhub.application.position_mapping import (
    PositionMapping,
    parse_position_mapping_file,
    require_mapping_batch_positions,
)
from proteinhub.application.plate_workbook import (
    build_plate_workbook,
    build_summary_workbook,
)
from proteinhub.application.validation import required
from proteinhub.config import Settings
from proteinhub.domain.errors import ConflictError, DomainError, NotFoundError
from proteinhub.domain.experiments import experiment_class_for
from proteinhub.domain.plate_positions import (
    PLATE_96_POSITIONS,
    extract_unique_plate_position,
)
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import (
    ArtifactRepository,
    BatchRepository,
    ExperimentRepository,
    ExperimentRawFileRepository,
    ProteinRepository,
)
from proteinhub.infrastructure.akta import render_akta_pngs
from proteinhub.infrastructure.plots import render_score_density_svg
from proteinhub.infrastructure.storage.database_file_store import DatabaseFileStore
from proteinhub.infrastructure.storage.file_store import file_store_for
from proteinhub.infrastructure.spr import (
    extract_spr_chart_spec,
    format_spr_concentration_text,
    read_spr_concentration_csv,
    read_spr_pptx,
    render_spr_chart_svg,
)
from proteinhub.infrastructure.translation.legacy_domesticator import (
    optimize_with_legacy_domesticator,
)


POSITION_UPDATE_MODES = {"move", "swap"}
TRANSLATION_ORGANISMS = {"E. coli"}
TRANSLATION_RESISTANCES = {"Amp", "Kan", "Tet", "Cam", "Sep"}
BATCH_ORDER_STATUSES = {
    "not_ordered",
    "ordered",
    "partially_received",
    "fully_received",
}
BATCH_ORDER_STATUS_TRANSITIONS = {
    "not_ordered": {"not_ordered", "ordered"},
    "ordered": {"ordered", "partially_received", "fully_received"},
    "partially_received": {"partially_received", "fully_received"},
    "fully_received": {"fully_received"},
}
SCORE_DENSITY_PREFERRED_ORDER = (
    "plddt_binder",
    "binder_aligned_rmsd",
    "pae_interaction",
    "target_aligned_rmsd",
    "contact_molecular_surface",
    "ddg",
    "sap_score",
    "norm_ddg",
)
SCORE_DENSITY_LABELS = {
    "plddt_binder": "pLDDT binder",
    "binder_aligned_rmsd": "binder aligned RMSD",
    "pae_interaction": "PAE interaction",
    "target_aligned_rmsd": "target aligned RMSD",
    "contact_molecular_surface": "contact molecular surface",
    "ddg": "ddG",
    "sap_score": "SAP score",
    "norm_ddg": "normalized ddG",
}
PADDING_FILLER = "GGSGGSGGS"
LONG_PADDING_PREFIX = "GSHHHHHH*"


def list_batches(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_read(connection, project_id=project_id, user_id=user_id)
    return BatchRepository(connection).list_for_project(project_id)


def create_batch(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    name: str,
    protein_ids: list[int],
    description: str = "",
    plate_format: str = "96",
    start_position: str = "A01",
) -> dict:
    require_project_write(connection, project_id=project_id, user_id=user_id)
    batch_name = required(name, "Batch name")
    normalized_plate_format = plate_format.strip() or "96"
    if normalized_plate_format != "96":
        raise DomainError("Only 96-well batches are supported")
    normalized_start_position = _normalize_plate_position(start_position)

    normalized_protein_ids = _normalize_protein_ids(protein_ids)
    available_positions = _positions_from_start(normalized_start_position)
    if len(normalized_protein_ids) > len(available_positions):
        raise DomainError("Not enough wells are available from the start position")
    protein_repository = ProteinRepository(connection)
    existing_ids = protein_repository.existing_ids_for_project(
        project_id=project_id, protein_ids=set(normalized_protein_ids)
    )
    if existing_ids != set(normalized_protein_ids):
        raise DomainError("Batch proteins must belong to this project")

    wells = list(zip(available_positions, normalized_protein_ids, strict=False))
    batch_repository = BatchRepository(connection)
    with transaction(connection):
        batch_id = batch_repository.insert(
            project_id=project_id,
            name=batch_name,
            description=description.strip(),
            plate_format=normalized_plate_format,
            created_by=user_id,
        )
        batch_repository.insert_wells(batch_id=batch_id, wells=wells)

    return get_batch(connection, batch_id=batch_id, user_id=user_id)


def get_batch(
    connection: sqlite3.Connection, *, batch_id: int, user_id: int
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    access_role = require_project_read(
        connection,
        project_id=project_id,
        user_id=user_id,
    )
    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    wells = batch_repository.list_wells(batch_id)
    return {
        "batch": batch,
        "wells": wells,
        "experiments": ExperimentRepository(connection).list_for_batch(batch_id),
        "score_density_plots": _batch_score_density_plots(wells),
        "access_role": access_role,
    }


def update_batch_well_position(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    well_id: int,
    user_id: int,
    position: str,
    mode: str = "move",
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    normalized_position = _normalize_plate_position(position)
    normalized_mode = mode.strip().lower() or "move"
    if normalized_mode not in POSITION_UPDATE_MODES:
        raise DomainError("Position update mode must be move or swap")

    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    _require_batch_editable(batch)
    well = batch_repository.get_well(batch_id=batch_id, well_id=well_id)
    if not well:
        raise NotFoundError("Batch well not found")
    if well["position"] == normalized_position:
        return get_batch(connection, batch_id=batch_id, user_id=user_id)
    if batch_repository.has_recorded_results(batch_id):
        raise DomainError("Batch well positions cannot be changed after results are recorded")

    target_well = batch_repository.get_well_by_position(
        batch_id=batch_id,
        position=normalized_position,
    )
    with transaction(connection):
        if target_well is None:
            batch_repository.update_well_position(
                well_id=well_id,
                position=normalized_position,
            )
        elif normalized_mode == "swap":
            batch_repository.swap_well_positions(
                first_well=well,
                second_well=target_well,
            )
        else:
            raise ConflictError("Target well position is already occupied")

    return get_batch(connection, batch_id=batch_id, user_id=user_id)


def update_batch_order_status(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
    order_status: str,
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    normalized_status = _normalize_batch_order_status(order_status)
    current_status = _normalize_batch_order_status(
        batch.get("order_status") or "not_ordered"
    )
    _validate_batch_order_status_transition(
        current_status=current_status,
        next_status=normalized_status,
    )
    if normalized_status != current_status:
        with transaction(connection):
            batch_repository.update_order_status(
                batch_id=batch_id,
                order_status=normalized_status,
            )
    return get_batch(connection, batch_id=batch_id, user_id=user_id)


def list_batch_experiments(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
) -> list[dict]:
    project_id = project_for_batch(connection, batch_id)
    require_project_read(connection, project_id=project_id, user_id=user_id)
    return ExperimentRepository(connection).list_for_batch(batch_id)


def create_batch_experiment(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
    experiment_type: str,
    name: str,
    description: str = "",
    details: Mapping[str, Any] | None = None,
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    experiment_class = experiment_class_for(experiment_type)
    experiment_name = required(name, "Experiment name")
    normalized_details = experiment_class.normalize_details(details)
    experiments = ExperimentRepository(connection)
    with transaction(connection):
        experiment_id = experiments.insert(
            batch_id=batch_id,
            experiment_type=experiment_class.experiment_type,
            name=experiment_name,
            description=description.strip(),
            created_by=user_id,
            details=normalized_details,
        )

    return get_batch_experiment(
        connection, experiment_id=experiment_id, user_id=user_id
    )


def get_batch_experiment(
    connection: sqlite3.Connection,
    *,
    experiment_id: int,
    user_id: int,
) -> dict:
    project_id = project_for_experiment(connection, experiment_id)
    access_role = require_project_read(
        connection,
        project_id=project_id,
        user_id=user_id,
    )
    experiments = ExperimentRepository(connection)
    experiment = experiments.get(experiment_id)
    if not experiment:
        raise NotFoundError("Experiment not found")
    return {
        "experiment": experiment,
        "results": experiments.list_well_results(experiment_id),
        "access_role": access_role,
    }


def update_experiment_well_result(
    connection: sqlite3.Connection,
    *,
    experiment_id: int,
    well_id: int,
    user_id: int,
    result_value: str = "",
    result_note: str = "",
) -> dict:
    project_id = project_for_experiment(connection, experiment_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    experiments = ExperimentRepository(connection)
    well = experiments.get_well_for_experiment(
        experiment_id=experiment_id, well_id=well_id
    )
    if not well:
        raise NotFoundError("Experiment well not found")

    with transaction(connection):
        experiments.upsert_well_result(
            experiment_id=experiment_id,
            well_id=well_id,
            result_value=result_value.strip(),
            result_note=result_note.strip(),
        )

    for result in experiments.list_well_results(experiment_id):
        if result["well_id"] == well_id:
            return result
    raise NotFoundError("Experiment well not found")


def import_akta_results(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    batch_id: int,
    user_id: int,
    run_date: str,
    files: list[tuple[str, str, bytes]],
    settings: Settings,
    position_mapping_file: tuple[str, str, bytes] | None = None,
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    normalized_run_date = _normalize_run_date(run_date, source="AKTA")
    if not files:
        raise DomainError("At least one AKTA zip file is required")

    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    experiments = ExperimentRepository(connection)
    wells_by_position = {
        well["position"]: well for well in batch_repository.list_wells(batch_id)
    }
    position_mapping = parse_position_mapping_file(position_mapping_file)
    require_mapping_batch_positions(position_mapping, wells_by_position)
    uploads, skipped_result_positions, observed_result_positions = _normalize_akta_uploads(
        files,
        wells_by_position,
        position_mapping=position_mapping,
    )
    if not uploads and position_mapping is not None and skipped_result_positions:
        raise DomainError("Position mapping did not match any AKTA zip file")
    upload_positions = {upload["position"] for upload in uploads}
    existing_experiment = experiments.find_for_batch_type_run_date(
        batch_id=batch_id,
        experiment_type="AKTA",
        run_date=normalized_run_date,
    )
    existing_positions = (
        experiments.result_positions_for_experiment(
            experiment_id=existing_experiment["id"],
            positions=upload_positions,
        )
        if existing_experiment
        else set()
    )
    uploads_to_import = [
        upload for upload in uploads if upload["position"] not in existing_positions
    ]
    if not uploads_to_import:
        raise ConflictError(
            _duplicate_result_message("AKTA", existing_positions, normalized_run_date)
        )
    rendered_pngs = render_akta_pngs(
        {
            upload["adapter_filename"]: upload["content"]
            for upload in uploads_to_import
        },
        settings=settings,
    )

    artifacts = ArtifactRepository(connection)
    raw_files = ExperimentRawFileRepository(connection)
    store = file_store_for(connection, storage_root)
    with transaction(connection):
        current_experiment = experiments.find_for_batch_type_run_date(
            batch_id=batch_id,
            experiment_type="AKTA",
            run_date=normalized_run_date,
        )
        if current_experiment:
            experiment_id = current_experiment["id"]
            previous_details = current_experiment.get("details") or {}
            later_existing_positions = experiments.result_positions_for_experiment(
                experiment_id=experiment_id,
                positions={upload["position"] for upload in uploads_to_import},
            )
        else:
            previous_details = {}
            later_existing_positions = set()
            experiment_id = 0
        skipped_positions = existing_positions | later_existing_positions
        uploads_to_import = [
            upload
            for upload in uploads_to_import
            if upload["position"] not in later_existing_positions
        ]
        if not uploads_to_import:
            raise ConflictError(
                _duplicate_result_message("AKTA", skipped_positions, normalized_run_date)
            )
        current_uploaded_positions = sorted(
            upload["position"] for upload in uploads_to_import
        )
        details = _akta_import_details(
            previous_details,
            run_date=normalized_run_date,
            uploaded_positions=current_uploaded_positions,
            skipped_positions=sorted(skipped_positions),
            requested_file_count=len(files),
        )
        if position_mapping is not None:
            details.update(
                position_mapping.details_for(
                    used_result_positions={
                        upload["result_position"] for upload in uploads_to_import
                    },
                    skipped_result_positions=skipped_result_positions,
                    observed_result_positions=observed_result_positions,
                )
            )
        if experiment_id:
            experiments.update_details(
                experiment_id=experiment_id,
                experiment_type="AKTA",
                details=details,
            )
        else:
            experiment_id = experiments.insert(
                batch_id=batch_id,
                experiment_type="AKTA",
                name=f"AKTA {normalized_run_date}",
                description="AKTA result import",
                created_by=user_id,
                details=details,
            )
        if position_mapping is not None:
            raw_files.insert(
                experiment_id=experiment_id,
                uploaded_by=user_id,
                filename=position_mapping.filename,
                raw_file_type="position_mapping_csv",
                mime_type=position_mapping.content_type or "text/csv",
                content=position_mapping.content,
            )
        for upload in uploads_to_import:
            well = upload["well"]
            position = upload["position"]
            zip_filename = f"AKTA_{normalized_run_date}_{position}.zip"
            png_filename = f"AKTA_{normalized_run_date}_{position}.png"
            zip_artifact_id = _store_experiment_artifact(
                artifacts=artifacts,
                store=store,
                project_id=project_id,
                protein_id=well["protein_id"],
                user_id=user_id,
                filename=zip_filename,
                mime_type=upload["content_type"] or "application/zip",
                content=upload["content"],
            )
            png_artifact_id = _store_experiment_artifact(
                artifacts=artifacts,
                store=store,
                project_id=project_id,
                protein_id=well["protein_id"],
                user_id=user_id,
                filename=png_filename,
                mime_type="image/png",
                content=rendered_pngs[upload["adapter_filename"]],
            )
            experiments.upsert_well_result(
                experiment_id=experiment_id,
                well_id=well["id"],
                result_value=f"AKTA {normalized_run_date}",
                result_note=json.dumps(
                    {
                        "source": "AKTA",
                        "run_date": normalized_run_date,
                        "result_position": upload["result_position"],
                        "plate_position": position,
                        "png_artifact_id": png_artifact_id,
                        "raw_zip_artifact_id": zip_artifact_id,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    return get_batch_experiment(
        connection,
        experiment_id=experiment_id,
        user_id=user_id,
    )


def import_spr_results(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    batch_id: int,
    user_id: int,
    run_date: str,
    filename: str,
    content_type: str,
    content: bytes,
    position_mapping_file: tuple[str, str, bytes] | None = None,
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    normalized_run_date = _normalize_run_date(run_date, source="SPR")
    file_name = required(Path(filename.replace("\\", "/")).name, "SPR filename")
    if not file_name.lower().endswith(".pptx"):
        raise DomainError("SPR result file must be a PowerPoint .pptx file")

    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    wells_by_position = {
        well["position"]: well for well in batch_repository.list_wells(batch_id)
    }
    position_mapping = parse_position_mapping_file(position_mapping_file)
    require_mapping_batch_positions(position_mapping, wells_by_position)
    experiments = ExperimentRepository(connection)
    existing_experiment = experiments.find_for_batch_type_run_date(
        batch_id=batch_id,
        experiment_type="SPR",
        run_date=normalized_run_date,
    )
    previous_details = (
        dict(existing_experiment.get("details") or {}) if existing_experiment else {}
    )
    concentration_details_by_protein = _spr_concentrations_from_details(previous_details)
    concentration_filename = str(previous_details.get("concentration_filename") or "")
    spr_results = read_spr_pptx(
        content,
        sample_annotation_for_id=lambda sample_id: _spr_concentration_text_for_sample_id(
            sample_id,
            wells_by_position=wells_by_position,
            concentrations_by_protein=concentration_details_by_protein,
            position_mapping=position_mapping,
        ),
    )
    (
        mapped_results,
        skipped_result_positions,
        observed_result_positions,
    ) = _map_spr_results_to_wells(
        spr_results,
        wells_by_position,
        position_mapping=position_mapping,
    )
    if not mapped_results and position_mapping is not None and skipped_result_positions:
        raise DomainError("Position mapping did not match any SPR result")
    mapped_positions = {result["position"] for result in mapped_results}
    existing_positions = (
        experiments.result_positions_for_experiment(
            experiment_id=existing_experiment["id"],
            positions=mapped_positions,
        )
        if existing_experiment
        else set()
    )
    results_to_import = [
        result
        for result in mapped_results
        if result["position"] not in existing_positions
    ]
    if not results_to_import:
        raise ConflictError(
            _duplicate_result_message("SPR", existing_positions, normalized_run_date)
        )

    artifacts = ArtifactRepository(connection)
    raw_files = ExperimentRawFileRepository(connection)
    store = file_store_for(connection, storage_root)
    with transaction(connection):
        current_experiment = experiments.find_for_batch_type_run_date(
            batch_id=batch_id,
            experiment_type="SPR",
            run_date=normalized_run_date,
        )
        if current_experiment:
            experiment_id = current_experiment["id"]
            later_existing_positions = experiments.result_positions_for_experiment(
                experiment_id=experiment_id,
                positions={result["position"] for result in results_to_import},
            )
        else:
            later_existing_positions = set()
            experiment_id = 0
        skipped_positions = existing_positions | later_existing_positions
        results_to_import = [
            result
            for result in results_to_import
            if result["position"] not in later_existing_positions
        ]
        if not results_to_import:
            raise ConflictError(
                _duplicate_result_message("SPR", skipped_positions, normalized_run_date)
            )
        current_uploaded_positions = sorted(
            result["position"] for result in results_to_import
        )
        current_sample_ids = [result["sample_id"] for result in results_to_import]
        details = _spr_import_details(
            previous_details,
            run_date=normalized_run_date,
            filename=file_name,
            content_type=content_type
            or "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            uploaded_positions=current_uploaded_positions,
            skipped_positions=sorted(skipped_positions),
            sample_ids=current_sample_ids,
            requested_sample_count=len(spr_results),
            concentration_filename=concentration_filename,
            concentrations_by_protein=concentration_details_by_protein,
        )
        if position_mapping is not None:
            details.update(
                position_mapping.details_for(
                    used_result_positions={
                        result["result_position"] for result in results_to_import
                    },
                    skipped_result_positions=skipped_result_positions,
                    observed_result_positions=observed_result_positions,
                )
            )
        if experiment_id:
            experiments.update_details(
                experiment_id=experiment_id,
                experiment_type="SPR",
                details=details,
            )
        else:
            experiment_id = experiments.insert(
                batch_id=batch_id,
                experiment_type="SPR",
                name=f"SPR {normalized_run_date}",
                description="SPR result import",
                created_by=user_id,
                details=details,
            )
        raw_files.insert(
            experiment_id=experiment_id,
            uploaded_by=user_id,
            filename=file_name,
            raw_file_type="spr_results_pptx",
            mime_type=content_type
            or "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            content=content,
        )
        if position_mapping is not None:
            raw_files.insert(
                experiment_id=experiment_id,
                uploaded_by=user_id,
                filename=position_mapping.filename,
                raw_file_type="position_mapping_csv",
                mime_type=position_mapping.content_type or "text/csv",
                content=position_mapping.content,
            )
        for result in results_to_import:
            well = result["well"]
            position = result["position"]
            sample_id = result["sample_id"]
            concentration_row = concentration_details_by_protein.get(
                _spr_concentration_key(well["protein_name"]),
                {},
            )
            artifact_id = _store_experiment_artifact(
                artifacts=artifacts,
                store=store,
                project_id=project_id,
                protein_id=well["protein_id"],
                user_id=user_id,
                filename=(
                    f"SPR_{normalized_run_date}_"
                    f"{_safe_artifact_token(sample_id)}_{position}.svg"
                ),
                mime_type="image/svg+xml",
                content=result["svg"],
            )
            experiments.upsert_well_result(
                experiment_id=experiment_id,
                well_id=well["id"],
                result_value=f"SPR {sample_id}",
                result_note=json.dumps(
                    {
                        "source": "SPR",
                        "run_date": normalized_run_date,
                        "sample_id": sample_id,
                        "result_position": result["result_position"],
                        "plate_position": position,
                        "chart_artifact_id": artifact_id,
                        "slide_number": result["slide_number"],
                        "table_row": result["table_row"],
                        "concentrations": concentration_row,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    return get_batch_experiment(
        connection,
        experiment_id=experiment_id,
        user_id=user_id,
    )


def import_spr_concentrations(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    batch_id: int,
    user_id: int,
    run_date: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    normalized_run_date = _normalize_run_date(run_date, source="SPR")
    file_name = required(
        Path(filename.replace("\\", "/")).name, "SPR concentration filename"
    )
    if not file_name.lower().endswith(".csv"):
        raise DomainError("SPR concentration table must be a CSV file")

    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")

    parsed_concentrations = read_spr_concentration_csv((file_name, content_type, content))
    experiments = ExperimentRepository(connection)
    artifacts = ArtifactRepository(connection)
    raw_files = ExperimentRawFileRepository(connection)
    store = file_store_for(connection, storage_root)

    with transaction(connection):
        current_experiment = experiments.find_for_batch_type_run_date(
            batch_id=batch_id,
            experiment_type="SPR",
            run_date=normalized_run_date,
        )
        if current_experiment:
            experiment_id = current_experiment["id"]
            previous_details = dict(current_experiment.get("details") or {})
        else:
            experiment_id = 0
            previous_details = {}

        concentration_details_by_protein = _spr_concentrations_from_details(
            previous_details
        )
        concentration_details_by_protein.update(parsed_concentrations)
        details = dict(previous_details)
        details.update(
            {
                "source": "SPR",
                "run_date": normalized_run_date,
                "concentration_filename": file_name,
                "concentrations_by_protein": concentration_details_by_protein,
                "concentration_count": len(concentration_details_by_protein),
            }
        )
        if experiment_id:
            experiments.update_details(
                experiment_id=experiment_id,
                experiment_type="SPR",
                details=details,
            )
        else:
            experiment_id = experiments.insert(
                batch_id=batch_id,
                experiment_type="SPR",
                name=f"SPR {normalized_run_date}",
                description="SPR concentration table import",
                created_by=user_id,
                details=details,
            )

        _refresh_spr_artifacts_for_concentrations(
            experiments=experiments,
            artifacts=artifacts,
            store=store,
            experiment_id=experiment_id,
            concentrations_by_protein=concentration_details_by_protein,
        )
        raw_files.insert(
            experiment_id=experiment_id,
            uploaded_by=user_id,
            filename=file_name,
            raw_file_type="spr_concentrations_csv",
            mime_type=content_type or "text/csv",
            content=content,
        )

    return get_batch_experiment(
        connection,
        experiment_id=experiment_id,
        user_id=user_id,
    )


def list_protein_batch_results(
    connection: sqlite3.Connection, *, protein_id: int, user_id: int
) -> list[dict]:
    project_id = project_for_protein(connection, protein_id)
    require_project_read(connection, project_id=project_id, user_id=user_id)
    return BatchRepository(connection).list_results_for_protein(protein_id)


def export_batch_plate_workbook(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
) -> bytes:
    project_id = project_for_batch(connection, batch_id)
    require_project_read(connection, project_id=project_id, user_id=user_id)
    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    return build_plate_workbook(batch, batch_repository.list_wells(batch_id))


def export_batch_summary_workbook(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
) -> bytes:
    project_id = project_for_batch(connection, batch_id)
    require_project_read(connection, project_id=project_id, user_id=user_id)
    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    return build_summary_workbook(batch, batch_repository.list_wells(batch_id))


def translate_batch_sequences(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
    settings: Settings,
    padding: bool = False,
    add_additional_w: bool = False,
    organism: str = "E. coli",
    backbone: str = "5",
    resistance: str = "Amp",
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_write(connection, project_id=project_id, user_id=user_id)
    normalized_organism = _normalize_translation_organism(organism)
    normalized_backbone = required(str(backbone), "Backbone")
    normalized_resistance = _normalize_translation_resistance(resistance)

    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    _require_batch_editable(batch)
    rows = batch_repository.list_sequence_exports(batch_id)
    translated_rows = [
        {
            "well_id": row["well_id"],
            "position": row["position"],
            "protein_id": row["protein_id"],
            "protein_name": row["protein_name"],
            "source_aa_sequence": row["protein_sequence"],
            "translated_aa_sequence": _add_additional_w(
                row["protein_sequence"], add_additional_w
            ),
        }
        for row in rows
    ]

    if padding and translated_rows:
        max_length = max(
            len(row["translated_aa_sequence"]) for row in translated_rows
        )
        for row in translated_rows:
            row["translated_aa_sequence"] = _pad_aa_sequence(
                row["translated_aa_sequence"], max_length
            )

    dna_sequences = optimize_with_legacy_domesticator(
        {
            _domesticator_record_id(row): row["translated_aa_sequence"]
            for row in translated_rows
        },
        settings=settings,
    )
    for row in translated_rows:
        row["dna_sequence"] = dna_sequences[_domesticator_record_id(row)]

    with transaction(connection):
        batch_repository.update_translation_settings(
            batch_id=batch_id,
            padding=padding,
            add_additional_w=add_additional_w,
            organism=normalized_organism,
            backbone=normalized_backbone,
            resistance=normalized_resistance,
        )
        for row in translated_rows:
            batch_repository.update_well_translation_result(
                well_id=row["well_id"],
                source_aa_sequence=row["source_aa_sequence"],
                translated_aa_sequence=row["translated_aa_sequence"],
                dna_sequence=row["dna_sequence"],
            )

    return {
        "padding": padding,
        "add_additional_w": add_additional_w,
        "organism": normalized_organism,
        "backbone": normalized_backbone,
        "resistance": normalized_resistance,
        "sequences": translated_rows,
        "dna_fasta": _sequence_fasta(translated_rows, "dna_sequence"),
    }


def project_for_batch(connection: sqlite3.Connection, batch_id: int) -> int:
    project_id = BatchRepository(connection).project_id_for(batch_id)
    if project_id is None:
        raise NotFoundError("Batch not found")
    return project_id


def project_for_experiment(connection: sqlite3.Connection, experiment_id: int) -> int:
    batch_id = ExperimentRepository(connection).batch_id_for(experiment_id)
    if batch_id is None:
        raise NotFoundError("Experiment not found")
    return project_for_batch(connection, batch_id)


def _normalize_protein_ids(protein_ids: list[int]) -> list[int]:
    if not protein_ids:
        raise DomainError("Batch must include at least one protein")
    if len(protein_ids) > len(PLATE_96_POSITIONS):
        raise DomainError("A 96-well batch can include at most 96 proteins")
    normalized = [int(protein_id) for protein_id in protein_ids]
    if any(protein_id <= 0 for protein_id in normalized):
        raise DomainError("Protein ids must be positive")
    return normalized


def _normalize_plate_position(position: str) -> str:
    normalized = position.strip().upper()
    if normalized not in PLATE_96_POSITIONS:
        raise DomainError("Position must be between A01 and H12")
    return normalized


def _normalize_run_date(value: str, *, source: str) -> str:
    normalized = required(value, f"{source} run date")
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise DomainError(f"{source} run date must be YYYY-MM-DD") from exc


def _akta_import_details(
    previous_details: dict,
    *,
    run_date: str,
    uploaded_positions: list[str],
    skipped_positions: list[str],
    requested_file_count: int,
) -> dict:
    all_positions = _merge_detail_values(
        previous_details,
        key="all_positions",
        fallback_key="uploaded_positions",
        values=uploaded_positions,
    )
    return {
        "source": "AKTA",
        "run_date": run_date,
        "file_count": len(uploaded_positions),
        "requested_file_count": requested_file_count,
        "uploaded_positions": uploaded_positions,
        "skipped_positions": skipped_positions,
        "all_positions": all_positions,
        "total_result_count": len(all_positions),
    }


def _spr_import_details(
    previous_details: dict,
    *,
    run_date: str,
    filename: str,
    content_type: str,
    uploaded_positions: list[str],
    skipped_positions: list[str],
    sample_ids: list[str],
    requested_sample_count: int,
    concentration_filename: str,
    concentrations_by_protein: dict[str, dict[str, str]],
) -> dict:
    all_positions = _merge_detail_values(
        previous_details,
        key="all_positions",
        fallback_key="uploaded_positions",
        values=uploaded_positions,
    )
    all_sample_ids = _merge_detail_values(
        previous_details,
        key="all_sample_ids",
        fallback_key="sample_ids",
        values=sample_ids,
    )
    filenames = _merge_detail_values(
        previous_details,
        key="filenames",
        fallback_key="filename",
        values=[filename],
    )
    return {
        "source": "SPR",
        "run_date": run_date,
        "filename": filename,
        "filenames": filenames,
        "content_type": content_type,
        "sample_count": len(sample_ids),
        "requested_sample_count": requested_sample_count,
        "sample_ids": sample_ids,
        "all_sample_ids": all_sample_ids,
        "uploaded_positions": uploaded_positions,
        "skipped_positions": skipped_positions,
        "all_positions": all_positions,
        "total_result_count": len(all_positions),
        "concentration_filename": concentration_filename,
        "concentration_count": len(concentrations_by_protein),
        "concentrations_by_protein": concentrations_by_protein,
    }


def _spr_concentrations_from_details(details: dict) -> dict[str, dict[str, str]]:
    raw = details.get("concentrations_by_protein")
    if not isinstance(raw, dict):
        return {}
    concentrations: dict[str, dict[str, str]] = {}
    for protein_key, row in raw.items():
        if not isinstance(row, dict):
            continue
        normalized_row = {
            str(label): str(value)
            for label, value in row.items()
            if str(label).strip()
        }
        if normalized_row:
            concentrations[str(protein_key)] = normalized_row
    return concentrations


def _spr_concentration_text_for_sample_id(
    sample_id: str,
    *,
    wells_by_position: dict[str, dict],
    concentrations_by_protein: dict[str, dict[str, str]],
    position_mapping: PositionMapping | None = None,
) -> str:
    result_position = _position_from_spr_sample_id(sample_id)
    position = result_position
    if position_mapping is not None:
        mapped_position = position_mapping.batch_position_for(result_position)
        if mapped_position is None:
            return ""
        position = mapped_position
    well = wells_by_position.get(position)
    if not well:
        return ""
    concentration_row = concentrations_by_protein.get(
        _spr_concentration_key(well["protein_name"]),
        {},
    )
    return format_spr_concentration_text(concentration_row)


def _refresh_spr_artifacts_for_concentrations(
    *,
    experiments: ExperimentRepository,
    artifacts: ArtifactRepository,
    store,
    experiment_id: int,
    concentrations_by_protein: dict[str, dict[str, str]],
) -> None:
    for result in experiments.list_well_results(experiment_id):
        result_note = result.get("result_note") or ""
        if not result_note or not result.get("result_value"):
            continue
        note = _spr_result_note_from_json(result_note)
        if note is None:
            continue
        chart_artifact_id = note.get("chart_artifact_id")
        if not isinstance(chart_artifact_id, int):
            continue
        artifact = artifacts.get(chart_artifact_id)
        if not artifact or artifact.get("mime_type") != "image/svg+xml":
            continue
        storage_path = str(artifact.get("storage_path") or "")
        if not storage_path:
            continue
        concentration_row = concentrations_by_protein.get(
            _spr_concentration_key(result["protein_name"]),
            {},
        )
        if not concentration_row:
            continue
        if isinstance(store, DatabaseFileStore):
            existing_svg = store.read_artifact(chart_artifact_id)
            if existing_svg is None:
                raise NotFoundError("SPR chart artifact file not found")
        else:
            svg_path = store.resolve(storage_path)
            if not svg_path.exists():
                raise NotFoundError("SPR chart artifact file not found")
            existing_svg = svg_path.read_bytes()
        spec = extract_spr_chart_spec(existing_svg)
        sample_id = str(note.get("sample_id") or "").strip()
        slide_number = note.get("slide_number")
        if not sample_id or not isinstance(slide_number, int):
            continue
        new_svg = render_spr_chart_svg(
            sample_id=sample_id,
            slide_number=slide_number,
            series=spec.series,
            x_axis=spec.x_axis,
            y_axis=spec.y_axis,
            header_text=format_spr_concentration_text(concentration_row),
        )
        if isinstance(store, DatabaseFileStore):
            store.replace_artifact(
                artifact_id=chart_artifact_id,
                storage_path=storage_path,
                content=new_svg,
            )
        else:
            store.replace(storage_path, new_svg)
            artifacts.mark_stored(
                artifact_id=chart_artifact_id,
                size_bytes=len(new_svg),
                storage_path=storage_path,
                storage_backend=getattr(store, "backend", "filesystem"),
            )
        note["concentrations"] = concentration_row
        experiments.upsert_well_result(
            experiment_id=experiment_id,
            well_id=result["well_id"],
            result_value=result["result_value"],
            result_note=json.dumps(note, ensure_ascii=False, sort_keys=True),
        )


def _spr_result_note_from_json(result_note: str) -> dict | None:
    try:
        parsed = json.loads(result_note)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict) or parsed.get("source") != "SPR":
        return None
    return parsed


def _merge_detail_values(
    details: dict,
    *,
    key: str,
    fallback_key: str,
    values: list[str],
) -> list[str]:
    existing = details.get(key)
    if existing is None:
        existing = details.get(fallback_key, [])
    if isinstance(existing, str):
        existing_values = [existing]
    elif isinstance(existing, list):
        existing_values = [str(value) for value in existing if value]
    else:
        existing_values = []
    return sorted({*existing_values, *values})


def _batch_score_density_plots(wells: list[dict]) -> list[dict]:
    values_by_metric: dict[str, list[float]] = {}
    first_seen: dict[str, int] = {}
    for well in wells:
        details = _score_details_from_json(well.get("score_details_json"))
        for metric, raw_value in details.items():
            numeric_value = _parse_score_value(raw_value)
            if numeric_value is None:
                continue
            if metric not in first_seen:
                first_seen[metric] = len(first_seen)
            values_by_metric.setdefault(metric, []).append(numeric_value)

    plots = []
    for metric in _score_density_metric_order(values_by_metric, first_seen):
        values = values_by_metric.get(metric, [])
        if not values:
            continue
        label = _score_density_label(metric)
        plots.append(
            {
                "metric": metric,
                "label": label,
                "sample_count": len(values),
                "svg": render_score_density_svg(
                    title=f"Distribution of {label}",
                    x_label=label,
                    values=values,
                ),
            }
        )
    return plots


def _score_details_from_json(details_json: object) -> dict[str, str]:
    if not isinstance(details_json, str) or not details_json:
        return {}
    try:
        details = json.loads(details_json)
    except json.JSONDecodeError:
        return {}
    return details if isinstance(details, dict) else {}


def _parse_score_value(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _score_density_metric_order(
    values_by_metric: dict[str, list[float]],
    first_seen: dict[str, int],
) -> list[str]:
    preferred = {metric: index for index, metric in enumerate(SCORE_DENSITY_PREFERRED_ORDER)}
    return sorted(
        values_by_metric,
        key=lambda metric: (
            preferred.get(metric, len(preferred)),
            first_seen.get(metric, 0),
            metric,
        ),
    )


def _score_density_label(metric: str) -> str:
    return SCORE_DENSITY_LABELS.get(metric, metric.replace("_", " "))


def _normalize_akta_uploads(
    files: list[tuple[str, str, bytes]],
    wells_by_position: dict[str, dict],
    *,
    position_mapping: PositionMapping | None = None,
) -> tuple[list[dict], set[str], set[str]]:
    uploads = []
    seen_positions: set[str] = set()
    observed_result_positions: set[str] = set()
    skipped_result_positions: set[str] = set()
    for filename, content_type, content in files:
        result_position = _position_from_akta_filename(filename)
        observed_result_positions.add(result_position)
        position = result_position
        if position_mapping is not None:
            mapped_position = position_mapping.batch_position_for(result_position)
            if mapped_position is None:
                skipped_result_positions.add(result_position)
                continue
            position = mapped_position
        if position in seen_positions:
            raise DomainError(f"Duplicate AKTA file for position {position}")
        seen_positions.add(position)
        well = wells_by_position.get(position)
        if well is None:
            raise DomainError(f"AKTA file {filename} does not map to this batch")
        uploads.append(
            {
                "position": position,
                "result_position": result_position,
                "well": well,
                "adapter_filename": f"{position}.zip",
                "content_type": content_type,
                "content": content,
            }
        )
    return uploads, skipped_result_positions, observed_result_positions


def _duplicate_result_message(source: str, positions: set[str], run_date: str) -> str:
    sorted_positions = sorted(positions)
    if len(sorted_positions) == 1:
        return (
            f"{source} result already uploaded for position "
            f"{sorted_positions[0]} on {run_date}"
        )
    return (
        f"{source} results already uploaded for positions on {run_date}: "
        f"{', '.join(sorted_positions)}"
    )


def _position_from_akta_filename(filename: str) -> str:
    file_name = required(Path(filename.replace("\\", "/")).name, "AKTA filename")
    if not file_name.lower().endswith(".zip"):
        raise DomainError("AKTA result files must be zip files")
    return extract_unique_plate_position(
        Path(file_name).stem,
        label="AKTA zip filename",
    )


def _map_spr_results_to_wells(
    results: list[dict],
    wells_by_position: dict[str, dict],
    *,
    position_mapping: PositionMapping | None = None,
) -> tuple[list[dict], set[str], set[str]]:
    mapped = []
    seen_positions: set[str] = set()
    observed_result_positions: set[str] = set()
    skipped_result_positions: set[str] = set()
    for result in results:
        sample_id = required(str(result.get("sample_id") or ""), "SPR sample id")
        result_position = _position_from_spr_sample_id(sample_id)
        observed_result_positions.add(result_position)
        position = result_position
        if position_mapping is not None:
            mapped_position = position_mapping.batch_position_for(result_position)
            if mapped_position is None:
                skipped_result_positions.add(result_position)
                continue
            position = mapped_position
        if position in seen_positions:
            raise DomainError(f"Duplicate SPR result for position {position}")
        seen_positions.add(position)
        well = wells_by_position.get(position)
        if well is None:
            raise DomainError(f"SPR sample {sample_id} does not map to this batch")
        mapped.append(
            {
                **result,
                "position": position,
                "result_position": result_position,
                "well": well,
            }
        )
    if not mapped:
        if position_mapping is not None and skipped_result_positions:
            return mapped, skipped_result_positions, observed_result_positions
        raise DomainError("SPR PowerPoint did not include importable results")
    return mapped, skipped_result_positions, observed_result_positions


def _position_from_spr_sample_id(sample_id: str) -> str:
    return extract_unique_plate_position(
        sample_id,
        label=f"SPR sample {sample_id}",
        allow_linear_a_labels=True,
        allow_letter_suffix=True,
    )


def _spr_concentration_key(value: str) -> str:
    name = Path(value.strip().replace("\\", "/")).name
    return Path(name).stem.casefold()


def _safe_artifact_token(value: str) -> str:
    return re.sub(r"[^\w.-]+", "_", value).strip("._") or "sample"


def _store_experiment_artifact(
    *,
    artifacts: ArtifactRepository,
    store,
    project_id: int,
    protein_id: int,
    user_id: int,
    filename: str,
    mime_type: str,
    content: bytes,
) -> int:
    artifact_id = artifacts.insert_pending(
        protein_id=protein_id,
        uploaded_by=user_id,
        filename=filename,
        artifact_type="experimental_result",
        mime_type=mime_type,
        storage_backend=getattr(store, "backend", "filesystem"),
    )
    stored = store.save_artifact(
        project_id=project_id,
        protein_id=protein_id,
        artifact_id=artifact_id,
        filename=filename,
        source=BytesIO(content),
    )
    artifacts.mark_stored(
        artifact_id=artifact_id,
        size_bytes=stored.size_bytes,
        storage_path=stored.relative_path,
        storage_backend=getattr(store, "backend", "filesystem"),
    )
    return artifact_id


def _normalize_batch_order_status(order_status: str) -> str:
    normalized = required(order_status, "Batch order status").strip().lower()
    if normalized not in BATCH_ORDER_STATUSES:
        raise DomainError(
            "Batch order status must be not_ordered, ordered, partially_received, or fully_received"
        )
    return normalized


def _validate_batch_order_status_transition(
    *, current_status: str, next_status: str
) -> None:
    allowed_statuses = BATCH_ORDER_STATUS_TRANSITIONS[current_status]
    if next_status not in allowed_statuses:
        raise DomainError("Batch order status cannot move backwards or skip ordering")


def _require_batch_editable(batch: dict) -> None:
    order_status = _normalize_batch_order_status(
        batch.get("order_status") or "not_ordered"
    )
    if order_status != "not_ordered":
        raise DomainError("Batch cannot be changed after it has been ordered")


def _positions_from_start(start_position: str) -> list[str]:
    return PLATE_96_POSITIONS[PLATE_96_POSITIONS.index(start_position) :]


def _fasta_header(row: dict) -> str:
    return f">{row['position']} {row['protein_name']}"


def _domesticator_record_id(row: dict) -> str:
    return f"well_{row['well_id']}"


def _sequence_fasta(rows: list[dict], sequence_key: str) -> str:
    lines: list[str] = []
    for row in rows:
        lines.append(_fasta_header(row))
        lines.extend(_wrap_fasta_sequence(row[sequence_key]))
    return "\n".join(lines) + ("\n" if lines else "")


def _wrap_fasta_sequence(sequence: str, width: int = 60) -> list[str]:
    return [sequence[index : index + width] for index in range(0, len(sequence), width)]


def _add_additional_w(sequence: str, add_additional_w: bool) -> str:
    return f"{sequence}W" if add_additional_w else sequence


def _pad_aa_sequence(sequence: str, target_length: int) -> str:
    missing_length = target_length - len(sequence)
    if missing_length <= 0:
        return sequence
    if missing_length >= len(LONG_PADDING_PREFIX):
        return (
            f"{sequence}{LONG_PADDING_PREFIX}"
            f"{_repeated_prefix(PADDING_FILLER, missing_length - len(LONG_PADDING_PREFIX))}"
        )
    return f"{sequence}{PADDING_FILLER[:missing_length]}"


def _repeated_prefix(sequence: str, length: int) -> str:
    if length <= 0:
        return ""
    return (sequence * ((length // len(sequence)) + 1))[:length]


def _normalize_translation_organism(organism: str) -> str:
    normalized = required(organism, "Organism")
    if normalized not in TRANSLATION_ORGANISMS:
        raise DomainError("Organism must be E. coli")
    return normalized


def _normalize_translation_resistance(resistance: str) -> str:
    normalized = required(resistance, "Resistance")
    if normalized not in TRANSLATION_RESISTANCES:
        raise DomainError("Resistance must be Amp, Kan, Tet, Cam, or Sep")
    return normalized
