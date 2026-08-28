from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from proteinhub.api.dependencies import ApiContext, build_dependencies
from proteinhub.api.routes_admin_sequences import create_admin_sequences_router
from proteinhub.api.routes_admin_users import create_admin_users_router
from proteinhub.api.routes_artifacts import create_artifacts_router
from proteinhub.api.routes_auth import create_auth_router
from proteinhub.api.routes_batches import create_batches_router
from proteinhub.api.routes_health import create_health_router
from proteinhub.api.routes_order_monitor import create_order_monitor_router
from proteinhub.api.routes_projects import create_projects_router
from proteinhub.api.routes_public_proteins import create_public_proteins_router
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
        create_health_router(
            context=context,
            get_connection=get_connection,
        )
    )
    router.include_router(
        create_auth_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_admin_sequences_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_admin_users_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_projects_router(
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_public_proteins_router(
            context=context,
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
            context=context,
            get_connection=get_connection,
            current_user=current_user,
        )
    )
    router.include_router(
        create_order_monitor_router(
            context=context,
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
