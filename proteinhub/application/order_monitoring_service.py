from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from proteinhub.application.permissions import require_admin
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.sqlite.repositories import BatchRepository


ORDERED_STATUSES = {"ordered", "partially_received", "fully_received"}
CADENCE_TARGET_DAYS = 14
RECENT_WEEK_COUNT = 8
OWNER_RANKING_MONTH_DAYS = 30


def get_order_monitor(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    today: date | None = None,
    week_count: int = RECENT_WEEK_COUNT,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    require_admin(connection, user_id=user_id)
    today = today or date.today()
    raw_batches = BatchRepository(connection).list_order_monitor_batches()
    batches = [
        _monitor_batch(row, today=today)
        for row in raw_batches
        if row.get("order_status") in ORDERED_STATUSES
    ]
    range_start, range_end = _resolve_week_range(
        today=today,
        week_count=week_count,
        start_date=start_date,
        end_date=end_date,
    )
    weekly_orders = _weekly_orders(
        batches,
        range_start=range_start,
        range_end=range_end,
    )

    last_ordered_at = batches[0]["ordered_at"] if batches else ""
    days_since_last_order = batches[0]["days_since_order"] if batches else None
    if days_since_last_order is None:
        cadence_status = "no_orders"
        cadence_text = "还没有已 order 的批次"
    elif days_since_last_order <= CADENCE_TARGET_DAYS:
        cadence_status = "on_track"
        cadence_text = "订单节奏正常"
    else:
        cadence_status = "overdue"
        cadence_text = f"距离上次 order 已超过 {CADENCE_TARGET_DAYS} 天"

    return {
        "summary": {
            "total_ordered_batches": len(batches),
            "total_ordered_proteins": sum(batch["well_count"] for batch in batches),
            "last_ordered_at": last_ordered_at,
            "days_since_last_order": days_since_last_order,
            "cadence_target_days": CADENCE_TARGET_DAYS,
            "cadence_status": cadence_status,
            "cadence_text": cadence_text,
        },
        "weekly_orders": weekly_orders,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "batches": batches,
        "owner_rankings": {
            "today": _owner_rankings(
                batches,
                start_date=today,
                end_date=today,
            ),
            "month": _owner_rankings(
                batches,
                start_date=today - timedelta(days=OWNER_RANKING_MONTH_DAYS - 1),
                end_date=today,
            ),
        },
        "batch_receipt_progress": _batch_receipt_progress(batches),
    }


def _monitor_batch(row: dict, *, today: date) -> dict:
    ordered_at = row.get("order_monitor_ordered_at") or row.get("ordered_at") or ""
    ordered_datetime = _parse_timestamp(ordered_at)
    ordered_date = ordered_datetime.date() if ordered_datetime else None
    week_start = _week_start(ordered_date) if ordered_date else None
    well_count = int(row["well_count"])
    received_well_count = int(row.get("received_well_count") or 0)
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "owner_id": row["owner_id"],
        "owner_name": row.get("owner_name") or "",
        "owner_email": row.get("owner_email") or "",
        "name": row["name"],
        "description": row.get("description") or "",
        "plate_format": row["plate_format"],
        "order_status": row["order_status"],
        "ordered_at": ordered_at,
        "ordered_week": _week_key(week_start) if week_start else "",
        "days_since_order": (today - ordered_date).days if ordered_date else None,
        "well_count": well_count,
        "received_well_count": received_well_count,
        "receipt_progress_percent": (
            (received_well_count / well_count) * 100 if well_count else 0
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "created_by_name": row.get("created_by_name") or "",
        "created_by_email": row.get("created_by_email") or "",
    }


def _owner_rankings(
    batches: list[dict],
    *,
    start_date: date,
    end_date: date,
) -> list[dict]:
    rankings_by_owner: dict[int, dict] = {}
    for batch in batches:
        ordered_datetime = _parse_timestamp(batch.get("ordered_at") or "")
        if ordered_datetime is None:
            continue
        ordered_date = ordered_datetime.date()
        if ordered_date < start_date or ordered_date > end_date:
            continue
        owner_id = int(batch["owner_id"])
        ranking = rankings_by_owner.setdefault(
            owner_id,
            {
                "owner_id": owner_id,
                "owner_name": batch.get("owner_name") or "",
                "owner_email": batch.get("owner_email") or "",
                "batch_count": 0,
                "protein_count": 0,
            },
        )
        ranking["batch_count"] += 1
        ranking["protein_count"] += int(batch["well_count"])
    return sorted(
        rankings_by_owner.values(),
        key=lambda ranking: (
            -ranking["protein_count"],
            -ranking["batch_count"],
            (ranking.get("owner_name") or ranking.get("owner_email") or "").lower(),
        ),
    )


def _batch_receipt_progress(batches: list[dict]) -> list[dict]:
    return sorted(
        batches,
        key=lambda batch: (
            _parse_timestamp(batch.get("ordered_at") or "") or datetime.max,
            int(batch["id"]),
        ),
    )


def _weekly_orders(
    batches: list[dict],
    *,
    range_start: date,
    range_end: date,
) -> list[dict]:
    week_starts = []
    current_week_start = range_start
    while current_week_start <= range_end:
        week_starts.append(current_week_start)
        current_week_start += timedelta(weeks=1)
    counts = {
        _week_key(week_start): {
            "week_start": week_start.isoformat(),
            "week_label": _week_key(week_start),
            "order_count": 0,
            "ordered_count": 0,
            "partially_received_count": 0,
            "fully_received_count": 0,
            "protein_count": 0,
            "batch_ids": [],
        }
        for week_start in week_starts
    }
    for batch in batches:
        week = counts.get(batch["ordered_week"])
        if week is None:
            continue
        week["order_count"] += 1
        status_count_key = f"{batch['order_status']}_count"
        if status_count_key in week:
            week[status_count_key] += 1
        week["protein_count"] += batch["well_count"]
        week["batch_ids"].append(batch["id"])
    return list(counts.values())


def _resolve_week_range(
    *,
    today: date,
    week_count: int,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    default_end = _week_start(today)
    default_start = default_end - timedelta(weeks=max(week_count, 1) - 1)
    if start_date is None and end_date is None:
        return default_start, default_end
    if start_date is None:
        start_date = end_date - timedelta(weeks=max(week_count, 1) - 1)
    if end_date is None:
        end_date = today

    range_start = _week_start(start_date)
    range_end = _week_start(end_date)
    if range_start > range_end:
        raise DomainError("Start date must be on or before end date")
    return range_start, range_end


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _week_key(week_start: date) -> str:
    year, week, _weekday = week_start.isocalendar()
    return f"{year}-W{week:02d}"
