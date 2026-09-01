from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

from proteinhub.application.batch_service import (
    get_batch_experiment,
    project_for_batch,
)
from proteinhub.application.permissions import require_batch_visibility
from proteinhub.application.position_mapping import (
    parse_position_mapping_file,
    require_mapping_batch_positions,
)
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.infrastructure.hplc import (
    plate_position_from_filename,
    read_hplc_chromatogram_csv,
    read_hplc_vial_fc_csv,
    render_hplc_chromatogram_svg,
    sample_key_from_filename,
)
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import (
    ArtifactRepository,
    BatchRepository,
    ExperimentRepository,
    ExperimentRawFileRepository,
)
from proteinhub.infrastructure.storage.file_store import file_store_for
from proteinhub.infrastructure.storage.paths import safe_filename


def import_hplc_results(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    batch_id: int,
    user_id: int,
    source_name: str = "",
    files: list[tuple[str, str, bytes]],
    position_mapping_file: tuple[str, str, bytes] | None = None,
) -> dict:
    require_batch_visibility(connection, batch_id=batch_id, user_id=user_id)
    project_id = project_for_batch(connection, batch_id)
    batch_repository = BatchRepository(connection)
    batch = batch_repository.get(batch_id)
    if not batch:
        raise NotFoundError("Batch not found")
    wells_by_position = {
        well["position"]: well for well in batch_repository.list_wells(batch_id)
    }
    position_mapping = parse_position_mapping_file(position_mapping_file)
    require_mapping_batch_positions(position_mapping, wells_by_position)

    chromatogram_files = []
    vial_fc_file: tuple[str, str, bytes] | None = None
    seen_positions: set[str] = set()
    observed_result_positions: set[str] = set()
    skipped_result_positions: set[str] = set()
    for filename, content_type, content in files:
        file_name = Path(filename.replace("\\", "/")).name
        if not file_name:
            continue
        if file_name.lower() == "vial_fc.csv":
            if vial_fc_file is not None:
                raise DomainError("Duplicate vial_fc.csv file")
            vial_fc_file = (file_name, content_type, content)
            continue
        if not file_name.lower().endswith(".csv"):
            continue
        result_position = plate_position_from_filename(file_name)
        observed_result_positions.add(result_position)
        plate_position = result_position
        if position_mapping is not None:
            mapped_position = position_mapping.batch_position_for(result_position)
            if mapped_position is None:
                skipped_result_positions.add(result_position)
                continue
            plate_position = mapped_position
        if plate_position not in wells_by_position:
            raise DomainError(f"HPLC file {file_name} does not map to this batch")
        if plate_position in seen_positions:
            raise DomainError(f"Duplicate HPLC file for position {plate_position}")
        seen_positions.add(plate_position)
        chromatogram_files.append(
            {
                "filename": file_name,
                "content_type": content_type,
                "content": content,
                "sample_key": sample_key_from_filename(file_name),
                "result_position": result_position,
                "plate_position": plate_position,
            }
        )

    if not chromatogram_files:
        if position_mapping is not None and skipped_result_positions:
            raise DomainError("Position mapping did not match any HPLC chromatogram CSV")
        raise DomainError("At least one HPLC chromatogram CSV is required")
    if vial_fc_file is None:
        raise DomainError("vial_fc.csv is required")

    blocks_by_sample = read_hplc_vial_fc_csv(vial_fc_file)
    prepared_results = []
    for file_info in sorted(chromatogram_files, key=lambda item: item["plate_position"]):
        blocks = blocks_by_sample.get(file_info["sample_key"])
        if blocks is None:
            raise DomainError(f"vial_fc.csv does not include {file_info['sample_key']}")
        points = read_hplc_chromatogram_csv(
            (
                file_info["filename"],
                file_info["content_type"],
                file_info["content"],
            )
        )
        svg = render_hplc_chromatogram_svg(
            sample_key=file_info["sample_key"],
            plate_position=file_info["plate_position"],
            points=points,
            blocks=blocks,
        )
        prepared_results.append(
            {
                **file_info,
                "blocks": blocks,
                "points": points,
                "svg": svg,
                "artifact_filename": (
                    f"HPLC_{file_info['plate_position']}_"
                    f"{safe_filename(file_info['sample_key'])}.svg"
                ),
            }
        )

    normalized_source_name = source_name.strip()
    experiment_name = f"HPLC {normalized_source_name}" if normalized_source_name else "HPLC import"
    details = {
        "source": "HPLC",
        "source_name": normalized_source_name,
        "vial_fc_filename": vial_fc_file[0],
        "file_count": len(prepared_results),
        "sample_count": len(prepared_results),
        "sample_keys": [result["sample_key"] for result in prepared_results],
        "plate_positions": [result["plate_position"] for result in prepared_results],
    }
    if position_mapping is not None:
        details.update(
            position_mapping.details_for(
                used_result_positions={
                    result["result_position"] for result in prepared_results
                },
                skipped_result_positions=skipped_result_positions,
                observed_result_positions=observed_result_positions,
            )
        )

    experiments = ExperimentRepository(connection)
    artifacts = ArtifactRepository(connection)
    raw_files = ExperimentRawFileRepository(connection)
    store = file_store_for(connection, storage_root)
    with transaction(connection):
        experiment_id = experiments.insert(
            batch_id=batch_id,
            experiment_type="HPLC",
            name=experiment_name,
            description="HPLC chromatogram import",
            created_by=user_id,
            details=details,
        )
        raw_files.insert(
            experiment_id=experiment_id,
            uploaded_by=user_id,
            filename=vial_fc_file[0],
            raw_file_type="hplc_vial_fc_csv",
            mime_type=vial_fc_file[1] or "text/csv",
            content=vial_fc_file[2],
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
        for result in prepared_results:
            well = wells_by_position.get(result["plate_position"])
            if not well:
                raise NotFoundError("Batch well not found")
            raw_files.insert(
                experiment_id=experiment_id,
                uploaded_by=user_id,
                well_id=well["id"],
                filename=result["filename"],
                raw_file_type="hplc_chromatogram_csv",
                mime_type=result["content_type"] or "text/csv",
                content=result["content"],
            )
            artifact_id = _store_hplc_artifact(
                artifacts=artifacts,
                store=store,
                project_id=project_id,
                protein_id=well["protein_id"],
                user_id=user_id,
                filename=result["artifact_filename"],
                content=result["svg"],
            )
            experiments.upsert_well_result(
                experiment_id=experiment_id,
                well_id=well["id"],
                result_value=f"HPLC {result['plate_position']}",
                result_note=json.dumps(
                    {
                        "source": "HPLC",
                        "source_name": normalized_source_name,
                        "sample_key": result["sample_key"],
                        "result_position": result["result_position"],
                        "plate_position": result["plate_position"],
                        "source_filename": result["filename"],
                        "vial_fc_filename": vial_fc_file[0],
                        "block_count": len(result["blocks"]),
                        "blocks": [asdict(block) for block in result["blocks"]],
                        "chart_artifact_id": artifact_id,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )

    return get_batch_experiment(connection, experiment_id=experiment_id, user_id=user_id)


def _store_hplc_artifact(
    *,
    artifacts: ArtifactRepository,
    store,
    project_id: int,
    protein_id: int,
    user_id: int,
    filename: str,
    content: bytes,
) -> int:
    artifact_id = artifacts.insert_pending(
        protein_id=protein_id,
        uploaded_by=user_id,
        filename=filename,
        artifact_type="experimental_result",
        mime_type="image/svg+xml",
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
