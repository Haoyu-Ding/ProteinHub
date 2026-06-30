from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import project_for_protein, require_project_role
from proteinhub.application.validation import required
from proteinhub.domain.errors import NotFoundError
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import ProteinRepository


def list_proteins(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return ProteinRepository(connection).list_for_project(project_id)


def create_protein(
    connection: sqlite3.Connection,
    *,
    project_id: int,
    user_id: int,
    name: str,
    description: str = "",
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")

    with transaction(connection):
        protein_id = ProteinRepository(connection).insert(
            project_id=project_id,
            name=protein_name,
            description=description.strip(),
        )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def get_protein(connection: sqlite3.Connection, *, protein_id: int, user_id: int) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein = ProteinRepository(connection).get(protein_id)
    if not protein:
        raise NotFoundError("Protein not found")
    return protein
