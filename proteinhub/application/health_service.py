from __future__ import annotations

import os

from proteinhub.config import Settings
from proteinhub.infrastructure.database.health import database_is_available


def get_health_status(connection, *, settings: Settings) -> dict:
    database_ok = database_is_available(connection)
    storage_ok = _storage_root_is_available(settings)
    return {
        "status": "ok" if database_ok and storage_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "database_backend": getattr(connection, "backend", "sqlite"),
        "storage": "ok" if storage_ok else "unavailable",
        "artifact_storage_backend": settings.artifact_storage_backend,
    }


def _storage_root_is_available(settings: Settings) -> bool:
    storage_root = settings.storage_root
    target = storage_root if storage_root.exists() else storage_root.parent
    return target.exists() and os.access(target, os.W_OK)
