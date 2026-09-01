from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import (
    require_project_owner,
)
from proteinhub.application.protein_service import normalize_protein_sequence
from proteinhub.application.validation import required
from proteinhub.domain.errors import NotFoundError
from proteinhub.infrastructure.database.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import PublicProteinRepository


def list_public_proteins(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
) -> list[dict]:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    return PublicProteinRepository(connection).list_for_project(project_id)


def create_public_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str = "",
    protein_type: str = "",
    target: str = "",
) -> dict:
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Public protein name")
    sequence_text = normalize_protein_sequence(sequence)

    with transaction(connection):
        public_protein_id = PublicProteinRepository(connection).insert(
            project_id=project_id,
            name=protein_name,
            sequence=sequence_text,
            description=description.strip(),
            protein_type=protein_type.strip(),
            target=target.strip(),
            created_by=user_id,
        )

    return get_public_protein(
        connection,
        project_id=project_id,
        public_protein_id=public_protein_id,
        user_id=user_id,
    )


def update_public_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    public_protein_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str = "",
    protein_type: str = "",
    target: str = "",
) -> dict:
    _require_public_protein_project(
        connection,
        project_id=project_id,
        public_protein_id=public_protein_id,
    )
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Public protein name")
    sequence_text = normalize_protein_sequence(sequence)

    with transaction(connection):
        PublicProteinRepository(connection).update(
            public_protein_id=public_protein_id,
            name=protein_name,
            sequence=sequence_text,
            description=description.strip(),
            protein_type=protein_type.strip(),
            target=target.strip(),
        )

    return get_public_protein(
        connection,
        project_id=project_id,
        public_protein_id=public_protein_id,
        user_id=user_id,
    )


def delete_public_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    public_protein_id: int,
    user_id: int,
) -> None:
    _require_public_protein_project(
        connection,
        project_id=project_id,
        public_protein_id=public_protein_id,
    )
    require_project_owner(connection, project_id=project_id, user_id=user_id)

    with transaction(connection):
        PublicProteinRepository(connection).delete(public_protein_id)


def get_public_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    public_protein_id: int,
    user_id: int,
) -> dict:
    _require_public_protein_project(
        connection,
        project_id=project_id,
        public_protein_id=public_protein_id,
    )
    require_project_owner(connection, project_id=project_id, user_id=user_id)
    public_protein = PublicProteinRepository(connection).get(public_protein_id)
    if not public_protein:
        raise NotFoundError("Public protein not found")
    return public_protein


def get_public_protein_detail(
    connection: sqlite3.Connection,
    *,
    public_protein_id: int,
    user_id: int,
) -> dict:
    repository = PublicProteinRepository(connection)
    project_id = repository.project_id_for(public_protein_id)
    if project_id is None:
        raise NotFoundError("Public protein not found")
    access_role = require_project_owner(
        connection,
        project_id=project_id,
        user_id=user_id,
    )
    public_protein = repository.get(public_protein_id)
    if not public_protein:
        raise NotFoundError("Public protein not found")
    return {
        "public_protein": public_protein,
        "access_role": access_role,
    }


def _require_public_protein_project(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    public_protein_id: int,
) -> None:
    actual_project_id = PublicProteinRepository(connection).project_id_for(
        public_protein_id
    )
    if actual_project_id is None or actual_project_id != project_id:
        raise NotFoundError("Public protein not found")
