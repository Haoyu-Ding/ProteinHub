from __future__ import annotations

import sqlite3
from proteinhub.application.permissions import require_batch_read
from proteinhub.domain.errors import NotFoundError
from proteinhub.infrastructure.sqlite.repositories import (
    ExperimentRepository,
    ExperimentRawFileRepository,
)


def list_experiment_raw_files(
    connection: sqlite3.Connection,
    *,
    experiment_id: int,
    user_id: int,
) -> list[dict]:
    batch_id = ExperimentRepository(connection).batch_id_for(experiment_id)
    if batch_id is None:
        raise NotFoundError("Experiment not found")
    require_batch_read(connection, batch_id=batch_id, user_id=user_id)
    return ExperimentRawFileRepository(connection).list_for_experiment(experiment_id)


def get_experiment_raw_file_download(
    connection: sqlite3.Connection,
    *,
    raw_file_id: int,
    user_id: int,
) -> tuple[dict, bytes]:
    raw_files = ExperimentRawFileRepository(connection)
    batch_id = raw_files.batch_id_for(raw_file_id)
    if batch_id is None:
        raise NotFoundError("Experiment raw file not found")
    require_batch_read(connection, batch_id=batch_id, user_id=user_id)
    raw_file = raw_files.get(raw_file_id)
    content = raw_files.get_content(raw_file_id)
    if not raw_file or content is None:
        raise NotFoundError("Experiment raw file not found")
    return raw_file, content
