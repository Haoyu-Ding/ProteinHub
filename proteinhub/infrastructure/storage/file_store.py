from __future__ import annotations

from pathlib import Path

from proteinhub.infrastructure.storage.database_file_store import DatabaseFileStore
from proteinhub.infrastructure.storage.local_file_store import LocalFileStore


def file_store_for(
    connection,
    storage_root: Path,
    *,
    backend: str | None = None,
):
    selected_backend = (
        backend or getattr(connection, "artifact_storage_backend", "")
    ).strip().lower()
    if not selected_backend and getattr(connection, "backend", "") == "postgresql":
        selected_backend = "database"
    if selected_backend == "database":
        return DatabaseFileStore(connection)
    return LocalFileStore(storage_root)
