from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, Depends, Query

from proteinhub.api.dependencies import ApiContext, map_domain_error
from proteinhub.api.schemas import OrderMonitorResponse
from proteinhub.application.order_monitoring_service import get_order_monitor
from proteinhub.domain.errors import DomainError


def create_order_monitor_router(
    *,
    context: ApiContext,
    get_connection: Callable,
    current_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/order-monitor", response_model=OrderMonitorResponse)
    def order_monitor(
        start_date: date | None = Query(default=None),
        end_date: date | None = Query(default=None),
        user: dict = Depends(current_user),
        connection: sqlite3.Connection = Depends(get_connection),
    ) -> dict:
        try:
            return get_order_monitor(
                connection,
                user_id=user["id"],
                start_date=start_date,
                end_date=end_date,
            )
        except DomainError as error:
            raise map_domain_error(error) from error

    return router
