from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import project_for_protein, protein_for_sequence, require_project_role
from proteinhub.application.validation import required
from proteinhub.domain.errors import NotFoundError
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import SequenceRepository


def list_sequences(
    connection: sqlite3.Connection, *, protein_id: int, user_id: int
) -> list[dict]:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return SequenceRepository(connection).list_for_protein(protein_id)


def create_sequence(
    connection: sqlite3.Connection,
    *,
    protein_id: int,
    user_id: int,
    name: str,
    sequence: str,
    description: str = "",
    version_tag: str = "",
) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    sequence_name = required(name, "Sequence name")
    sequence_text = required(sequence, "Sequence").upper().replace(" ", "").replace("\n", "")

    with transaction(connection):
        sequence_id = SequenceRepository(connection).insert(
            protein_id=protein_id,
            name=sequence_name,
            sequence=sequence_text,
            description=description.strip(),
            version_tag=version_tag.strip(),
        )

    return get_sequence(connection, sequence_id=sequence_id, user_id=user_id)


def get_sequence(
    connection: sqlite3.Connection, *, sequence_id: int, user_id: int
) -> dict:
    relation = protein_for_sequence(connection, sequence_id)
    require_project_role(connection, project_id=relation["project_id"], user_id=user_id)
    sequence = SequenceRepository(connection).get_with_project(sequence_id)
    if not sequence:
        raise NotFoundError("Sequence not found")
    return sequence
