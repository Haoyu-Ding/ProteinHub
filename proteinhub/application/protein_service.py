from __future__ import annotations

import sqlite3
from io import BytesIO
from pathlib import Path

from proteinhub.application.permissions import project_for_protein, require_project_role
from proteinhub.application.structure_sequence import extract_structure_sequence
from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import ProteinRepository
from proteinhub.infrastructure.storage.local_file_store import LocalFileStore


PROTEIN_TYPES = {"TCR", "cyclic peptide", "nanobody", "minibinder", "enzymes"}


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
    protein_type: str = "TCR",
    target: str = "",
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    normalized_type = normalize_protein_type(protein_type)

    with transaction(connection):
        protein_id = ProteinRepository(connection).insert(
            project_id=project_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence="",
            description=description.strip(),
            protein_type=normalized_type,
            target=target.strip(),
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
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
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
) -> list[dict]:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    if not files:
        raise DomainError("At least one structure file is required")

    normalized_type = normalize_protein_type(protein_type)
    parsed_proteins = []
    for filename, content_type, content in files:
        sequence = extract_structure_sequence(filename, content)["sequence"]
        parsed_proteins.append(
            {
                "name": _protein_name_from_filename(filename),
                "sequence": normalize_protein_sequence(sequence),
                "filename": filename,
                "content_type": content_type,
                "content": content,
            }
        )

    protein_ids = []
    proteins = ProteinRepository(connection)
    store = LocalFileStore(storage_root)
    with transaction(connection):
        for parsed in parsed_proteins:
            protein_id = proteins.insert(
                project_id=project_id,
                name=parsed["name"],
                sequence=parsed["sequence"],
                dna_sequence="",
                description=description.strip(),
                protein_type=normalized_type,
                target=target.strip(),
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
            )
            protein_ids.append(protein_id)

    return [
        get_protein(connection, protein_id=protein_id, user_id=user_id)
        for protein_id in protein_ids
    ]


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
    require_project_role(connection, project_id=project_id, user_id=user_id)
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


def normalize_protein_type(protein_type: str) -> str:
    normalized = required(protein_type, "Protein type")
    if normalized not in PROTEIN_TYPES:
        raise DomainError(
            "Protein type must be TCR, cyclic peptide, nanobody, minibinder, or enzymes"
        )
    return normalized


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
) -> dict:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    protein_name = required(name, "Protein name")
    sequence_text = normalize_protein_sequence(sequence)
    normalized_type = normalize_protein_type(protein_type)
    proteins = ProteinRepository(connection)
    store = LocalFileStore(storage_root)

    with transaction(connection):
        protein_id = proteins.insert(
            project_id=project_id,
            name=protein_name,
            sequence=sequence_text,
            dna_sequence="",
            description=description.strip(),
            protein_type=normalized_type,
            target=target.strip(),
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
            )

    return get_protein(connection, protein_id=protein_id, user_id=user_id)


def _protein_name_from_filename(filename: str) -> str:
    file_name = Path(filename.replace("\\", "/")).name
    return required(Path(file_name).stem, "Protein name")
