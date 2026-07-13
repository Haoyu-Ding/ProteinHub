from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from proteinhub.api.dependencies import ApiContext, build_dependencies
from proteinhub.api.routes_artifacts import create_artifacts_router
from proteinhub.api.routes_auth import create_auth_router
from proteinhub.api.routes_batches import create_batches_router
from proteinhub.api.routes_projects import create_projects_router
from proteinhub.api.routes_proteins import create_proteins_router
from proteinhub.config import Settings


def create_api_router(
    *,
    database_path: Path,
    storage_root: Path,
    settings: Settings,
) -> APIRouter:
    context = ApiContext(
        database_path=database_path,
        storage_root=storage_root,
        settings=settings,
    )
    get_connection, current_user = build_dependencies(context)

    router = APIRouter(prefix="/api")
    router.include_router(
        create_auth_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_projects_router(
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_proteins_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_batches_router(
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_artifacts_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    return router
