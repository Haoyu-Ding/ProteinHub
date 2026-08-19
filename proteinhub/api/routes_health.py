from __future__ import annotations

from collections.abc import Callable
import sqlite3

from fastapi import APIRouter, Depends

from proteinhub.api.dependencies import ApiContext
from proteinhub.api.schemas import HealthResponse
from proteinhub.application.health_service import get_health_status


def create_health_router(
    *,
    context: ApiContext,
    get_connection: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    def health(connection: sqlite3.Connection = Depends(get_connection)) -> dict:
        return get_health_status(connection, settings=context.settings)

    return router
