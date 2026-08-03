from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from proteinhub.application.permissions import project_for_protein, require_project_role
from proteinhub.application.plate_workbook import (
    build_plate_workbook,
    build_summary_workbook,
)
from proteinhub.application.validation import required
from proteinhub.config import Settings
from proteinhub.domain.errors import ConflictError, DomainError, NotFoundError
from proteinhub.domain.experiments import experiment_class_for
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import (
    ArtifactRepository,
    BatchRepository,
    ExperimentRepository,
    ProteinRepository,
)
from proteinhub.infrastructure.akta import render_akta_pngs
from proteinhub.infrastructure.storage.local_file_store import LocalFileStore
from proteinhub.infrastructure.translation.legacy_domesticator import (
    optimize_with_legacy_domesticator,
)


PLATE_96_POSITIONS = [
    f"{row}{column:02d}" for row in "ABCDEFGH" for column in range(1, 13)
]
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
PADDING_FILLER = "GGSGGSGGS"
LONG_PADDING_PREFIX = "GSHHHHHH*"
AKTA_POSITION_FILENAME_RE = re.compile(r"^([A-H])0?([1-9]|1[0-2])$", re.IGNORECASE)


def list_batches(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    return {
        "batch": batch,
        "wells": batch_repository.list_wells(batch_id),
        "experiments": ExperimentRepository(connection).list_for_batch(batch_id),
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
    experiments = ExperimentRepository(connection)
    experiment = experiments.get(experiment_id)
    if not experiment:
        raise NotFoundError("Experiment not found")
    return {
        "experiment": experiment,
        "results": experiments.list_well_results(experiment_id),
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
) -> dict:
    project_id = project_for_batch(connection, batch_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    normalized_run_date = _normalize_run_date(run_date)
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
    uploads = _normalize_akta_uploads(files, wells_by_position)
    existing_positions = experiments.result_positions_for_batch_type(
        batch_id=batch_id,
        experiment_type="AKTA",
        positions={upload["position"] for upload in uploads},
    )
    uploads_to_import = [
        upload for upload in uploads if upload["position"] not in existing_positions
    ]
    if not uploads_to_import:
        raise ConflictError(_akta_duplicate_message(existing_positions))
    rendered_pngs = render_akta_pngs(
        {
            upload["adapter_filename"]: upload["content"]
            for upload in uploads_to_import
        },
        settings=settings,
    )

    artifacts = ArtifactRepository(connection)
    store = LocalFileStore(storage_root)
    with transaction(connection):
        later_existing_positions = experiments.result_positions_for_batch_type(
            batch_id=batch_id,
            experiment_type="AKTA",
            positions={upload["position"] for upload in uploads_to_import},
        )
        skipped_positions = existing_positions | later_existing_positions
        uploads_to_import = [
            upload
            for upload in uploads_to_import
            if upload["position"] not in later_existing_positions
        ]
        if not uploads_to_import:
            raise ConflictError(_akta_duplicate_message(skipped_positions))
        experiment_id = experiments.insert(
            batch_id=batch_id,
            experiment_type="AKTA",
            name=f"AKTA {normalized_run_date}",
            description="AKTA result import",
            created_by=user_id,
            details={
                "source": "AKTA",
                "run_date": normalized_run_date,
                "file_count": len(uploads_to_import),
                "requested_file_count": len(uploads),
                "uploaded_positions": sorted(
                    upload["position"] for upload in uploads_to_import
                ),
                "skipped_positions": sorted(skipped_positions),
            },
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
                result_note=(
                    f"AKTA PNG artifact #{png_artifact_id}; "
                    f"raw ZIP artifact #{zip_artifact_id}"
                ),
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return BatchRepository(connection).list_results_for_protein(protein_id)


def export_batch_plate_workbook(
    connection: sqlite3.Connection,
    *,
    batch_id: int,
    user_id: int,
) -> bytes:
    project_id = project_for_batch(connection, batch_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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


def _normalize_run_date(value: str) -> str:
    normalized = required(value, "AKTA run date")
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise DomainError("AKTA run date must be YYYY-MM-DD") from exc


def _normalize_akta_uploads(
    files: list[tuple[str, str, bytes]],
    wells_by_position: dict[str, dict],
) -> list[dict]:
    uploads = []
    seen_positions: set[str] = set()
    for filename, content_type, content in files:
        position = _position_from_akta_filename(filename)
        if position in seen_positions:
            raise DomainError(f"Duplicate AKTA file for position {position}")
        seen_positions.add(position)
        well = wells_by_position.get(position)
        if well is None:
            raise DomainError(f"AKTA file {filename} does not map to this batch")
        uploads.append(
            {
                "position": position,
                "well": well,
                "adapter_filename": f"{position}.zip",
                "content_type": content_type,
                "content": content,
            }
        )
    return uploads


def _akta_duplicate_message(positions: set[str]) -> str:
    sorted_positions = sorted(positions)
    if len(sorted_positions) == 1:
        return f"AKTA result already uploaded for position {sorted_positions[0]}"
    return f"AKTA results already uploaded for positions: {', '.join(sorted_positions)}"


def _position_from_akta_filename(filename: str) -> str:
    file_name = required(Path(filename.replace("\\", "/")).name, "AKTA filename")
    if not file_name.lower().endswith(".zip"):
        raise DomainError("AKTA result files must be zip files")
    stem = Path(file_name).stem.upper()
    match = AKTA_POSITION_FILENAME_RE.fullmatch(stem)
    if not match:
        raise DomainError("AKTA zip filenames must be well positions like A01.zip")
    row, column = match.groups()
    return f"{row.upper()}{int(column):02d}"


def _store_experiment_artifact(
    *,
    artifacts: ArtifactRepository,
    store: LocalFileStore,
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
