from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from proteinhub.application.permissions import project_for_protein, require_project_role
from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.domain.experiments import experiment_class_for
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import (
    BatchRepository,
    ExperimentRepository,
    ProteinRepository,
)


PLATE_96_POSITIONS = [
    f"{row}{column:02d}" for row in "ABCDEFGH" for column in range(1, 13)
]


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
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    batch_name = required(name, "Batch name")
    normalized_plate_format = plate_format.strip() or "96"
    if normalized_plate_format != "96":
        raise DomainError("Only 96-well batches are supported")

    normalized_protein_ids = _normalize_protein_ids(protein_ids)
    protein_repository = ProteinRepository(connection)
    existing_ids = protein_repository.existing_ids_for_project(
        project_id=project_id, protein_ids=set(normalized_protein_ids)
    )
    if existing_ids != set(normalized_protein_ids):
        raise DomainError("Batch proteins must belong to this project")

    wells = list(zip(PLATE_96_POSITIONS, normalized_protein_ids, strict=False))
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


def list_protein_batch_results(
    connection: sqlite3.Connection, *, protein_id: int, user_id: int
) -> list[dict]:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return BatchRepository(connection).list_results_for_protein(protein_id)


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
