from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import project_for_protein, require_project_role
from proteinhub.application.reverse_translation import reverse_translate_protein
from proteinhub.application.structure_sequence import extract_structure_sequence
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
    sequence: str,
    description: str = "",
    version_tag: str = "",
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    dna_sequence = reverse_translate_protein(sequence_text)

    with transaction(connection):
        protein_id = ProteinRepository(connection).insert(
            project_id=project_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence=dna_sequence,
            description=description.strip(),
            version_tag=version_tag.strip(),
        )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def update_protein_sequence(
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
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    dna_sequence = reverse_translate_protein(sequence_text)

    with transaction(connection):
        ProteinRepository(connection).update_sequence(
            protein_id=protein_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence=dna_sequence,
            description=description.strip(),
            version_tag=version_tag.strip(),
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return extract_structure_sequence(filename, content)


def get_protein(connection: sqlite3.Connection, *, protein_id: int, user_id: int) -> dict:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein = ProteinRepository(connection).get(protein_id)
    if not protein:
        raise NotFoundError("Protein not found")
    return protein


def normalize_protein_sequence(sequence: str) -> str:
    return required(sequence, "Sequence").upper().replace(" ", "").replace("\n", "")
