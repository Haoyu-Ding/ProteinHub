from __future__ import annotations

import sqlite3

from proteinhub.application.sequence_similarity import normalize_sequence, sequence_identity
from proteinhub.application.permissions import require_admin
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.sqlite.repositories import AdminSequenceRepository

MAX_SEQUENCE_SEARCH_LIMIT = 100
SEARCH_MODE_CONTAINS = "contains"
SEARCH_MODE_SIMILARITY = "similarity"


def search_admin_sequences(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    query: str = "",
    limit: int = 50,
    offset: int = 0,
    mode: str = SEARCH_MODE_CONTAINS,
    similarity_threshold: float = 0.9,
) -> list[dict]:
    require_admin(connection, user_id=user_id)
    normalized_mode = _normalize_search_mode(mode)
    normalized_query = normalize_sequence(query)
    normalized_limit = min(max(int(limit), 1), MAX_SEQUENCE_SEARCH_LIMIT)
    normalized_offset = max(int(offset), 0)
    if normalized_mode == SEARCH_MODE_SIMILARITY:
        threshold = max(0.0, min(float(similarity_threshold), 1.0))
        rows = AdminSequenceRepository(connection).list_searchable_sequences()
        return _search_sequences_by_similarity(
            rows,
            query=normalized_query,
            threshold=threshold,
            limit=normalized_limit,
            offset=normalized_offset,
        )
    rows = AdminSequenceRepository(connection).search_sequences(
        sequence_query=normalized_query,
        limit=normalized_limit,
        offset=normalized_offset,
    )
    return [_sequence_search_result(row) for row in rows]


def _normalize_search_mode(mode: str) -> str:
    value = (mode or SEARCH_MODE_CONTAINS).strip().lower()
    if value not in {SEARCH_MODE_CONTAINS, SEARCH_MODE_SIMILARITY}:
        raise DomainError("Sequence search mode is invalid")
    return value


def _search_sequences_by_similarity(
    rows: list[dict],
    *,
    query: str,
    threshold: float,
    limit: int,
    offset: int,
) -> list[dict]:
    if not query:
        return []
    results = []
    for row in rows:
        identity, alignment_length = sequence_identity(query, normalize_sequence(row["sequence"]))
        if identity < threshold:
            continue
        result = _sequence_search_result(row)
        result["match_type"] = "duplicate" if identity == 1.0 and result["sequence_length"] == len(query) else "high_similarity"
        result["identity"] = round(identity, 4)
        result["alignment_length"] = alignment_length
        results.append(result)
    results.sort(key=lambda item: (-item["identity"], -item["alignment_length"], item["name"]))
    return results[offset : offset + limit]


def _sequence_search_result(row: dict) -> dict:
    result = dict(row)
    result["sequence_length"] = int(
        result.get("sequence_length") or len(result.get("sequence") or "")
    )
    result["batch_count"] = int(result.get("batch_count") or 0)
    result["identity"] = None
    result["alignment_length"] = None
    result["match_type"] = ""
    if result["source_type"] == "batch_protein":
        result["detail_path"] = f"/proteins/{result['protein_id']}"
    else:
        result["detail_path"] = f"/public-proteins/{result['public_protein_id']}"
    return result
