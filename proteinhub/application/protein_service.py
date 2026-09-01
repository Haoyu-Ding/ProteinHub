from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path

from proteinhub.application.permissions import (
    project_for_protein,
    require_project_owner,
)
from proteinhub.application.structure_sequence import (
    extract_structure_deposit_date,
    extract_structure_sequence,
)
from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import ProteinRepository
from proteinhub.infrastructure.storage.file_store import file_store_for


PROTEIN_TYPES = {"TCR", "cyclic peptide", "nanobody", "minibinder", "enzymes"}
SIMILARITY_THRESHOLD = 0.9
MANUAL_RATINGS = {"unrated", "normal", "rare", "epic", "legendary"}
PROTEIN_LIST_SORTS = {
    "time_desc",
    "time_asc",
    "created_desc",
    "created_asc",
    "effective_date_desc",
    "effective_date_asc",
    "rating_desc",
    "rating_asc",
}


@dataclass(frozen=True)
class SequenceMatch:
    protein_id: int | None
    protein_name: str
    scope: str
    match_type: str
    identity: float
    alignment_length: int


@dataclass(frozen=True)
class SequenceCheckItem:
    name: str
    sequence: str
    matches: list[SequenceMatch]
    has_duplicate: bool
    has_high_similarity: bool


@dataclass(frozen=True)
class SequenceCheckResult:
    items: list[SequenceCheckItem]
    similarity_threshold: float = SIMILARITY_THRESHOLD

    @property
    def has_blocking_duplicates(self) -> bool:
        return False

    @property
    def has_warnings(self) -> bool:
        return any(item.has_duplicate or item.has_high_similarity for item in self.items)


def list_proteins(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    manual_ratings: list[str] | None = None,
    date_from: str = "",
    date_to: str = "",
    sort: str = "time_desc",
) -> list[dict]:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    normalized_ratings = _normalize_manual_rating_filter(manual_ratings or [])
    normalized_date_from = _normalize_filter_date(date_from, "Start date")
    normalized_date_to = _normalize_filter_date(date_to, "End date")
    if normalized_date_from and normalized_date_to and normalized_date_from > normalized_date_to:
        raise DomainError("Start date must be on or before end date")
    normalized_sort = _normalize_protein_list_sort(sort)
    return ProteinRepository(connection).list_for_project(
        project_id,
        manual_ratings=normalized_ratings,
        date_from=normalized_date_from,
        date_to=normalized_date_to,
        sort=normalized_sort,
    )


def create_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str = "",
    protein_type: str = "TCR",
    target: str = "",
    allow_high_similarity: bool = False,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    normalized_type = normalize_protein_type(protein_type)
    sequence_check = _check_project_sequence_items(
        connection,
        project_id=project_id,
        items=[{"name": protein_name, "sequence": sequence_text}],
    )
    similarity_fields = _sequence_similarity_insert_fields(sequence_check.items[0])

    with transaction(connection):
        protein_id = ProteinRepository(connection).insert(
            project_id=project_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence="",
            description=description.strip(),
            protein_type=normalized_type,
            target=target.strip(),
            manual_rating="unrated",
            **similarity_fields,
        )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def create_protein_with_structure_file(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    project_id: int,
    user_id: int,
    name: str,
    sequence: str,
    filename: str,
    content_type: str,
    content: bytes,
    description: str = "",
    protein_type: str = "TCR",
    target: str = "",
    allow_high_similarity: bool = False,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    extract_structure_sequence(filename, content)
    return _create_protein_with_optional_structure(
        connection,
        storage_root=storage_root,
        project_id=project_id,
        user_id=user_id,
        name=name,
        sequence=sequence,
        description=description,
        protein_type=protein_type,
        target=target,
        structure_file=(filename, content_type, content),
        allow_high_similarity=allow_high_similarity,
    )


def import_proteins_from_structures(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    project_id: int,
    user_id: int,
    files: list[tuple[str, str, bytes]],
    description: str = "",
    protein_type: str = "TCR",
    target: str = "",
    allow_high_similarity: bool = False,
    score_file: tuple[str, str, bytes] | None = None,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    if not files:
        raise DomainError("At least one structure file is required")

    normalized_type = normalize_protein_type(protein_type)
    score_details_by_name = _parse_score_details_table(score_file) if score_file else {}
    parsed_proteins = []
    for filename, content_type, content in files:
        sequence = extract_structure_sequence(filename, content)["sequence"]
        protein_name = _protein_name_from_filename(filename)
        parsed_proteins.append(
            {
                "name": protein_name,
                "sequence": normalize_protein_sequence(sequence),
                "filename": filename,
                "content_type": content_type,
                "content": content,
            }
        )
    sequence_check = _check_project_sequence_items(
        connection,
        project_id=project_id,
        items=parsed_proteins,
    )

    protein_ids = []
    proteins_by_score_key: dict[str, list[int]] = {}
    proteins = ProteinRepository(connection)
    store = file_store_for(connection, storage_root)
    with transaction(connection):
        for parsed, check_item in zip(parsed_proteins, sequence_check.items, strict=True):
            protein_id = proteins.insert(
                project_id=project_id,
                name=parsed["name"],
                sequence=parsed["sequence"],
                dna_sequence="",
                description=description.strip(),
                protein_type=normalized_type,
                target=target.strip(),
                manual_rating="unrated",
                **_sequence_similarity_insert_fields(check_item),
            )
            stored = store.save_protein_structure(
                project_id=project_id,
                protein_id=protein_id,
                filename=parsed["filename"],
                source=BytesIO(parsed["content"]),
            )
            proteins.update_structure_file(
                protein_id=protein_id,
                filename=Path(parsed["filename"].replace("\\", "/")).name,
                mime_type=parsed["content_type"] or "application/octet-stream",
                size_bytes=stored.size_bytes,
                storage_path=stored.relative_path,
                storage_backend=getattr(store, "backend", "filesystem"),
                deposit_date=extract_structure_deposit_date(
                    parsed["filename"],
                    parsed["content"],
                ),
            )
            protein_ids.append(protein_id)
            proteins_by_score_key.setdefault(_score_key(parsed["name"]), []).append(
                protein_id
            )
        score_import = _apply_score_details(
            proteins,
            proteins_by_score_key=proteins_by_score_key,
            score_details_by_name=score_details_by_name,
        )

    return {
        "proteins": [
            get_protein(connection, protein_id=protein_id, user_id=user_id)
            for protein_id in protein_ids
        ],
        "score_import": score_import,
    }


def _apply_score_details(
    proteins: ProteinRepository,
    *,
    proteins_by_score_key: dict[str, list[int]],
    score_details_by_name: dict[str, dict[str, str]],
) -> dict:
    matched_keys = [
        key for key in score_details_by_name if key in proteins_by_score_key
    ]
    skipped_names = [
        key for key in score_details_by_name if key not in proteins_by_score_key
    ]
    matched_count = 0
    for key in matched_keys:
        for protein_id in proteins_by_score_key[key]:
            proteins.update_score_details(
                protein_id=protein_id,
                score_details=score_details_by_name[key],
            )
            matched_count += 1
    return {
        "matched_count": matched_count,
        "skipped_count": len(skipped_names),
        "skipped_names": skipped_names,
    }


def get_protein_structure_file(
    connection: sqlite3.Connection, *, protein_id: int, user_id: int
) -> dict:
    protein = get_protein(connection, protein_id=protein_id, user_id=user_id)
    if not protein["structure_storage_path"]:
        raise NotFoundError("Protein structure file not found")
    return protein


def update_protein_sequence(
    connection: sqlite3.Connection,
    *,
    protein_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str = "",
    protein_type: str = "TCR",
    target: str = "",
) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    normalized_type = normalize_protein_type(protein_type)

    with transaction(connection):
        ProteinRepository(connection).update_sequence(
            protein_id=protein_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence="",
            description=description.strip(),
            protein_type=normalized_type,
            target=target.strip(),
        )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def update_protein_manual_rating(
    connection: sqlite3.Connection,
    *,
    protein_id: int,
    user_id: int,
    manual_rating: str,
) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    normalized_rating = normalize_manual_rating(manual_rating)

    with transaction(connection):
        ProteinRepository(connection).update_manual_rating(
            protein_id=protein_id,
            manual_rating=normalized_rating,
        )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def parse_protein_sequence(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    filename: str,
    content: bytes,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    return extract_structure_sequence(filename, content)


def parse_protein_structure_for_existing(
    connection: sqlite3.Connection,
    *,
    protein_id: int,
    user_id: int,
    filename: str,
    content: bytes,
) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    return extract_structure_sequence(filename, content)


def get_protein(connection: sqlite3.Connection, *, protein_id: int, user_id: int) -> dict:
    project_id = project_for_protein(connection, protein_id)
    access_role = require_project_owner(
        connection,
        project_id=project_id,
        user_id=user_id,
    )
    protein = ProteinRepository(connection).get(protein_id)
    if not protein:
        raise NotFoundError("Protein not found")
    protein["access_role"] = access_role
    return protein


def check_project_protein_sequences(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    items: list[dict],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    result = _check_project_sequence_items(
        connection,
        project_id=project_id,
        items=items,
        similarity_threshold=similarity_threshold,
    )
    return _sequence_check_response(result)


def _check_project_sequence_items(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    items: list[dict],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> SequenceCheckResult:
    if not items:
        raise DomainError("At least one protein sequence is required")
    threshold = max(0.0, min(float(similarity_threshold), 1.0))
    existing_proteins = ProteinRepository(connection).list_sequences_for_project(
        project_id
    )
    normalized_existing = [
        {
            "id": protein["id"],
            "name": protein["name"],
            "sequence": normalize_protein_sequence(protein["sequence"]),
        }
        for protein in existing_proteins
    ]

    raw_items = []
    for item in items:
        name = required(str(item.get("name", "")).strip(), "Protein name")
        sequence_text = normalize_protein_sequence(str(item.get("sequence", "")))
        matches = _compare_sequence_against_existing(
            sequence_text,
            normalized_existing,
            threshold=threshold,
        )
        raw_items.append({"name": name, "sequence": sequence_text, "matches": matches})

    for left_index, left_item in enumerate(raw_items):
        for right_item in raw_items[left_index + 1 :]:
            pair_matches = _compare_sequence_pair(
                left_item,
                right_item,
                threshold=threshold,
            )
            if pair_matches is None:
                continue
            left_match, right_match = pair_matches
            left_item["matches"].append(left_match)
            right_item["matches"].append(right_match)

    check_items = []
    for item in raw_items:
        matches = item["matches"]
        has_duplicate = any(match.match_type == "duplicate" for match in matches)
        has_high_similarity = any(
            match.match_type in {"duplicate", "high_similarity"} for match in matches
        )
        check_items.append(
            SequenceCheckItem(
                name=item["name"],
                sequence=item["sequence"],
                matches=matches,
                has_duplicate=has_duplicate,
                has_high_similarity=has_high_similarity,
            )
        )

    return SequenceCheckResult(items=check_items, similarity_threshold=threshold)


def _sequence_check_response(result: SequenceCheckResult) -> dict:
    return {
        "items": [
            {
                "name": item.name,
                "sequence": item.sequence,
                "sequence_length": len(item.sequence),
                "matches": [
                    _sequence_match_response(match)
                    for match in item.matches
                ],
                "has_duplicate": item.has_duplicate,
                "has_high_similarity": item.has_high_similarity,
            }
            for item in result.items
        ],
        "has_blocking_duplicates": result.has_blocking_duplicates,
        "has_warnings": result.has_warnings,
        "similarity_threshold": result.similarity_threshold,
    }


def _sequence_similarity_insert_fields(item: SequenceCheckItem) -> dict:
    return {
        "sequence_similarity_status": "high_similarity"
        if item.has_high_similarity
        else "",
        "sequence_similarity_matches": [
            _sequence_match_response(match) for match in item.matches
        ]
        if item.has_high_similarity
        else [],
    }


def _sequence_match_response(match: SequenceMatch) -> dict:
    return {
        "protein_id": match.protein_id,
        "protein_name": match.protein_name,
        "scope": match.scope,
        "match_type": match.match_type,
        "identity": round(match.identity, 4),
        "alignment_length": match.alignment_length,
    }


def normalize_protein_sequence(sequence: str) -> str:
    return required(sequence, "Sequence").upper().replace(" ", "").replace("\n", "")


def normalize_protein_type(protein_type: str) -> str:
    normalized = required(protein_type, "Protein type")
    if normalized not in PROTEIN_TYPES:
        raise DomainError(
            "Protein type must be TCR, cyclic peptide, nanobody, minibinder, or enzymes"
        )
    return normalized


def normalize_manual_rating(manual_rating: str) -> str:
    normalized = required(manual_rating, "Manual rating")
    if normalized not in MANUAL_RATINGS:
        raise DomainError(
            "Manual rating must be unrated, normal, rare, epic, or legendary"
        )
    return normalized


def _normalize_manual_rating_filter(manual_ratings: list[str]) -> tuple[str, ...]:
    normalized = []
    for rating in manual_ratings:
        value = rating.strip()
        if not value:
            continue
        if value not in MANUAL_RATINGS:
            raise DomainError("Manual rating filter is invalid")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _normalize_filter_date(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise DomainError(f"{field_name} must be YYYY-MM-DD") from exc


def _normalize_protein_list_sort(sort: str) -> str:
    value = (sort or "time_desc").strip()
    if value not in PROTEIN_LIST_SORTS:
        raise DomainError("Protein list sort is invalid")
    return value


def _parse_score_details_table(
    score_file: tuple[str, str, bytes],
) -> dict[str, dict[str, str]]:
    filename, _content_type, content = score_file
    file_name = required(Path(filename.replace("\\", "/")).name, "Score table filename")
    if not file_name.lower().endswith(".csv"):
        raise DomainError("Score table must be a CSV file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainError("Score table must be UTF-8 CSV") from exc

    reader = csv.reader(StringIO(text))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise DomainError("Score table must include a header row") from exc

    pdb_name_column = _pdb_name_column_index(headers)
    detail_columns = [
        (index, header.strip())
        for index, header in enumerate(
            headers[pdb_name_column + 1 :], start=pdb_name_column + 1
        )
        if header.strip()
    ]
    if not detail_columns:
        raise DomainError("Score table must include columns after pdb_name")

    score_details = {}
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        protein_key = (
            _score_key(row[pdb_name_column]) if pdb_name_column < len(row) else ""
        )
        if not protein_key:
            continue
        if protein_key in score_details:
            raise DomainError(f"Duplicate score row for {row[pdb_name_column].strip()}")
        score_details[protein_key] = {
            header: row[index].strip() if index < len(row) else ""
            for index, header in detail_columns
        }
    return score_details


def _pdb_name_column_index(headers: list[str]) -> int:
    for index, header in enumerate(headers):
        if header.strip().lower() == "pdb_name":
            return index
    raise DomainError("Score table must include a pdb_name column")


def _score_key(value: str) -> str:
    name = Path(value.strip().replace("\\", "/")).name
    return Path(name).stem.casefold()


def _create_protein_with_optional_structure(
    connection: sqlite3.Connection,
    *,
    storage_root: Path,
    project_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str,
    protein_type: str,
    target: str,
    structure_file: tuple[str, str, bytes] | None = None,
    allow_high_similarity: bool = False,
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    normalized_type = normalize_protein_type(protein_type)
    sequence_check = _check_project_sequence_items(
        connection,
        project_id=project_id,
        items=[{"name": protein_name, "sequence": sequence_text}],
    )
    similarity_fields = _sequence_similarity_insert_fields(sequence_check.items[0])
    proteins = ProteinRepository(connection)
    store = file_store_for(connection, storage_root)

    with transaction(connection):
        protein_id = proteins.insert(
            project_id=project_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence="",
            description=description.strip(),
            protein_type=normalized_type,
            target=target.strip(),
            manual_rating="unrated",
            score_details={},
            **similarity_fields,
        )
        if structure_file is not None:
            filename, content_type, content = structure_file
            stored = store.save_protein_structure(
                project_id=project_id,
                protein_id=protein_id,
                filename=filename,
                source=BytesIO(content),
            )
            proteins.update_structure_file(
                protein_id=protein_id,
                filename=Path(filename.replace("\\", "/")).name,
                mime_type=content_type or "application/octet-stream",
                size_bytes=stored.size_bytes,
                storage_path=stored.relative_path,
                storage_backend=getattr(store, "backend", "filesystem"),
                deposit_date=extract_structure_deposit_date(filename, content),
            )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def _protein_name_from_filename(filename: str) -> str:
    file_name = Path(filename.replace("\\", "/")).name
    return required(Path(file_name).stem, "Protein name")


def _compare_sequence_against_existing(
    sequence: str,
    existing_proteins: list[dict],
    *,
    threshold: float,
) -> list[SequenceMatch]:
    matches: list[SequenceMatch] = []
    for protein in existing_proteins:
        existing_sequence = protein["sequence"]
        if sequence == existing_sequence:
            matches.append(
                SequenceMatch(
                    protein_id=int(protein["id"]),
                    protein_name=str(protein["name"]),
                    scope="existing",
                    match_type="duplicate",
                    identity=1.0,
                    alignment_length=len(sequence),
                )
            )
            continue
        identity, alignment_length = _sequence_identity(sequence, existing_sequence)
        if identity >= threshold:
            matches.append(
                SequenceMatch(
                    protein_id=int(protein["id"]),
                    protein_name=str(protein["name"]),
                    scope="existing",
                    match_type="high_similarity",
                    identity=identity,
                    alignment_length=alignment_length,
                )
            )
    return matches


def _compare_sequence_pair(
    left_item: dict,
    right_item: dict,
    *,
    threshold: float,
) -> tuple[SequenceMatch, SequenceMatch] | None:
    left_sequence = left_item["sequence"]
    right_sequence = right_item["sequence"]
    if left_sequence == right_sequence:
        match_type = "duplicate"
        identity = 1.0
        alignment_length = len(left_sequence)
    else:
        identity, alignment_length = _sequence_identity(left_sequence, right_sequence)
        if identity < threshold:
            return None
        match_type = "high_similarity"

    return (
        SequenceMatch(
            protein_id=None,
            protein_name=str(right_item["name"]),
            scope="incoming",
            match_type=match_type,
            identity=identity,
            alignment_length=alignment_length,
        ),
        SequenceMatch(
            protein_id=None,
            protein_name=str(left_item["name"]),
            scope="incoming",
            match_type=match_type,
            identity=identity,
            alignment_length=alignment_length,
        ),
    )


def _sequence_identity(sequence_a: str, sequence_b: str) -> tuple[float, int]:
    if not sequence_a or not sequence_b:
        return 0.0, max(len(sequence_a), len(sequence_b))
    if len(sequence_a) > len(sequence_b):
        sequence_a, sequence_b = sequence_b, sequence_a
    if len(sequence_b) > 500:
        return _longest_common_subsequence_identity(sequence_a, sequence_b)
    matches = _global_alignment_best_identity(sequence_a, sequence_b)
    return matches


@lru_cache(maxsize=2048)
def _global_alignment_best_identity(sequence_a: str, sequence_b: str) -> tuple[float, int]:
    m = len(sequence_a)
    n = len(sequence_b)
    if m == 0 or n == 0:
        return 0.0, max(m, n)
    previous = [0] * (n + 1)
    for i, aa in enumerate(sequence_a, start=1):
        current = [0]
        for j, bb in enumerate(sequence_b, start=1):
            match = previous[j - 1] + (1 if aa == bb else 0)
            delete = previous[j]
            insert = current[j - 1]
            current.append(max(match, delete, insert))
        previous = current
    matches = previous[-1]
    alignment_length = max(m, n)
    return (matches / alignment_length if alignment_length else 0.0, alignment_length)


def _longest_common_subsequence_identity(sequence_a: str, sequence_b: str) -> tuple[float, int]:
    m = len(sequence_a)
    n = len(sequence_b)
    if m == 0 or n == 0:
        return 0.0, max(m, n)
    if m > n:
        sequence_a, sequence_b = sequence_b, sequence_a
        m, n = n, m
    previous = [0] * (n + 1)
    for aa in sequence_a:
        current = [0]
        for j, bb in enumerate(sequence_b, start=1):
            if aa == bb:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[-1]))
        previous = current
    matches = previous[-1]
    alignment_length = max(m, n)
    return (matches / alignment_length if alignment_length else 0.0, alignment_length)
