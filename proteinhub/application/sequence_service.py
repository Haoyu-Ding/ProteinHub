from __future__ import annotations

import sqlite3

from proteinhub.application.permissions import (
    project_for_protein,
    protein_for_sequence,
    require_project_role,
)
from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError, NotFoundError
from proteinhub.infrastructure.sqlite.connection import transaction
from proteinhub.infrastructure.sqlite.repositories import (
    ProjectRepository,
    SequenceCommentRepository,
    SequenceRepository,
)


SEQUENCE_STATUSES = {
    "draft",
    "designed",
    "ready_for_synthesis",
    "synthesizing",
    "testing",
    "validated",
    "failed",
}
SEQUENCE_PRIORITIES = {"low", "medium", "high"}
DISCIPLINES = {"", "design", "synthesis", "assay", "other"}


def list_sequences(
    connection: sqlite3.Connection, *, protein_id: int, user_id: int
) -> list[dict]:
    project_id = project_for_protein(connection, protein_id)
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return SequenceRepository(connection).list_for_protein(protein_id)


def list_project_board(
    connection: sqlite3.Connection, *, project_id: int, user_id: int
) -> list[dict]:
    require_project_role(connection, project_id=project_id, user_id=user_id)
    return SequenceRepository(connection).list_board_for_project(project_id)


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


def update_sequence_workflow(
    connection: sqlite3.Connection,
    *,
    sequence_id: int,
    user_id: int,
    status: str,
    priority: str,
    assigned_to: int | None,
    discipline_owner: str,
    design_rationale: str,
    handoff_note: str,
    risk_note: str,
) -> dict:
    relation = protein_for_sequence(connection, sequence_id)
    project_id = int(relation["project_id"])
    require_project_role(connection, project_id=project_id, user_id=user_id)

    normalized_status = status.strip()
    normalized_priority = priority.strip()
    normalized_discipline = discipline_owner.strip()
    if normalized_status not in SEQUENCE_STATUSES:
        raise DomainError("Status is not supported")
    if normalized_priority not in SEQUENCE_PRIORITIES:
        raise DomainError("Priority must be low, medium, or high")
    if normalized_discipline not in DISCIPLINES:
        raise DomainError("Discipline owner is not supported")
    if assigned_to is not None:
        assignee_role = ProjectRepository(connection).get_role(
            project_id=project_id, user_id=assigned_to
        )
        if assignee_role is None:
            raise DomainError("Assignee must be a project member")

    with transaction(connection):
        SequenceRepository(connection).update_workflow(
            sequence_id=sequence_id,
            status=normalized_status,
            priority=normalized_priority,
            assigned_to=assigned_to,
            discipline_owner=normalized_discipline,
            design_rationale=design_rationale.strip(),
            handoff_note=handoff_note.strip(),
            risk_note=risk_note.strip(),
        )

    return get_sequence(connection, sequence_id=sequence_id, user_id=user_id)


def list_sequence_comments(
    connection: sqlite3.Connection, *, sequence_id: int, user_id: int
) -> list[dict]:
    relation = protein_for_sequence(connection, sequence_id)
    require_project_role(connection, project_id=relation["project_id"], user_id=user_id)
    return SequenceCommentRepository(connection).list_for_sequence(sequence_id)


def create_sequence_comment(
    connection: sqlite3.Connection, *, sequence_id: int, user_id: int, body: str
) -> dict:
    relation = protein_for_sequence(connection, sequence_id)
    require_project_role(connection, project_id=relation["project_id"], user_id=user_id)
    comment_body = required(body, "Comment")
    comments = SequenceCommentRepository(connection)

    with transaction(connection):
        comment_id = comments.insert(
            sequence_id=sequence_id, author_id=user_id, body=comment_body
        )

    for comment in comments.list_for_sequence(sequence_id):
        if comment["id"] == comment_id:
            return comment
    raise NotFoundError("Comment not found")
