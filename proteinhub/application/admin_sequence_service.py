from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import require_admin
from proteinhub.infrastructure.sqlite.repositories import AdminSequenceRepository


MAX_SEQUENCE_SEARCH_LIMIT = 100


def search_admin_sequences(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    require_admin(connection, user_id=user_id)
    normalized_query = _normalize_sequence_query(query)
    normalized_limit = min(max(int(limit), 1), MAX_SEQUENCE_SEARCH_LIMIT)
    normalized_offset = max(int(offset), 0)
    rows = AdminSequenceRepository(connection).search_sequences(
        sequence_query=normalized_query,
        limit=normalized_limit,
        offset=normalized_offset,
    )
    return [_sequence_search_result(row) for row in rows]


def _normalize_sequence_query(query: str) -> str:
    return "".join((query or "").split()).upper()


def _sequence_search_result(row: dict) -> dict:
    result = dict(row)
    result["sequence_length"] = int(
        result.get("sequence_length") or len(result.get("sequence") or "")
    )
    result["batch_count"] = int(result.get("batch_count") or 0)
    if result["source_type"] == "batch_protein":
        result["detail_path"] = f"/proteins/{result['protein_id']}"
    else:
        result["detail_path"] = f"/public-proteins/{result['public_protein_id']}"
    return result
