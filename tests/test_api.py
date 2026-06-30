from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from proteinhub.api import create_api_router
from proteinhub.config import Settings
from proteinhub.db import init_db


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "proteinhub.sqlite3",
        storage_root=tmp_path / "storage",
        jwt_secret="test-secret",
        nicegui_storage_secret="test-storage-secret",
    )
    init_db(settings.database_path)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(
        create_api_router(
            database_path=settings.database_path,
            storage_root=settings.storage_root,
            settings=settings,
        )
    )
    return TestClient(app)


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_user_cannot_list_projects(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/projects")

    assert response.status_code == 401


def test_project_to_artifact_integration_flow(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Kinase designs", "description": "MVP test"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "Protein A", "description": ""},
    ).json()
    sequence = client.post(
        f"/api/proteins/{protein['id']}/sequences",
        headers=auth(owner_token),
        json={
            "name": "seq-001",
            "sequence": "acdefg",
            "description": "first",
            "version_tag": "v1",
        },
    ).json()

    upload = client.post(
        f"/api/sequences/{sequence['id']}/artifacts",
        headers=auth(owner_token),
        files={"file": ("model.pdb", b"ATOM", "chemical/x-pdb")},
    )

    assert upload.status_code == 200, upload.text
    artifact = upload.json()
    assert artifact["storage_path"].startswith("projects/")
    assert artifact["storage_path"].endswith("/model.pdb")
    assert "storage/" not in artifact["storage_path"]

    download = client.get(
        f"/api/artifacts/{artifact['id']}/download",
        headers=auth(owner_token),
    )
    assert download.status_code == 200
    assert download.content == b"ATOM"


def test_project_permissions_for_members_and_non_members(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Secret project"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "Protein A"},
    ).json()
    sequence = client.post(
        f"/api/proteins/{protein['id']}/sequences",
        headers=auth(owner_token),
        json={"name": "seq-001", "sequence": "ACD"},
    ).json()

    denied = client.get(
        f"/api/sequences/{sequence['id']}",
        headers=auth(outsider_token),
    )
    assert denied.status_code == 403

    added = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "member"},
    )
    assert added.status_code == 200, added.text

    member_upload = client.post(
        f"/api/sequences/{sequence['id']}/artifacts",
        headers=auth(member_token),
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert member_upload.status_code == 200, member_upload.text

    member_cannot_add_member = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(member_token),
        json={"email": "outsider@example.com", "role": "member"},
    )
    assert member_cannot_add_member.status_code == 403

    artifact_id = member_upload.json()["id"]
    member_cannot_delete = client.delete(
        f"/api/artifacts/{artifact_id}",
        headers=auth(member_token),
    )
    assert member_cannot_delete.status_code == 403

    owner_delete = client.delete(
        f"/api/artifacts/{artifact_id}",
        headers=auth(owner_token),
    )
    assert owner_delete.status_code == 204

    deleted_download = client.get(
        f"/api/artifacts/{artifact_id}/download",
        headers=auth(owner_token),
    )
    assert deleted_download.status_code == 404


def test_sequence_workflow_board_and_comments(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    synthesis_token = register(client, "synthesis@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Binder collaboration"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "Target A"},
    ).json()
    sequence = client.post(
        f"/api/proteins/{protein['id']}/sequences",
        headers=auth(owner_token),
        json={"name": "candidate-7", "sequence": "ACDEFGHIK"},
    ).json()
    added = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={
            "email": "synthesis@example.com",
            "role": "member",
            "discipline": "synthesis",
        },
    )
    assert added.status_code == 200, added.text
    synthesis_user_id = added.json()["id"]

    workflow = client.patch(
        f"/api/sequences/{sequence['id']}/workflow",
        headers=auth(owner_token),
        json={
            "status": "ready_for_synthesis",
            "priority": "high",
            "assigned_to": synthesis_user_id,
            "discipline_owner": "synthesis",
            "design_rationale": "Strong interface score.",
            "handoff_note": "Order codon-optimized construct.",
            "risk_note": "Watch hydrophobic N-terminus.",
        },
    )
    assert workflow.status_code == 200, workflow.text
    updated = workflow.json()
    assert updated["status"] == "ready_for_synthesis"
    assert updated["priority"] == "high"
    assert updated["assigned_to"] == synthesis_user_id
    assert updated["assigned_to_email"] == "synthesis@example.com"

    board = client.get(f"/api/projects/{project['id']}/board", headers=auth(synthesis_token))
    assert board.status_code == 200, board.text
    row = board.json()[0]
    assert row["name"] == "candidate-7"
    assert row["protein_name"] == "Target A"
    assert row["status"] == "ready_for_synthesis"
    assert row["artifact_count"] == 0

    comment = client.post(
        f"/api/sequences/{sequence['id']}/comments",
        headers=auth(synthesis_token),
        json={"body": "Synthesis team picked this up."},
    )
    assert comment.status_code == 200, comment.text
    assert comment.json()["author_email"] == "synthesis@example.com"

    detail = client.get(f"/api/sequences/{sequence['id']}", headers=auth(owner_token))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    synthesis_member = next(
        member
        for member in payload["project_members"]
        if member["email"] == "synthesis@example.com"
    )
    assert synthesis_member["discipline"] == "synthesis"
    assert payload["comments"][0]["body"] == "Synthesis team picked this up."

    outsider_board = client.get(
        f"/api/projects/{project['id']}/board",
        headers=auth(outsider_token),
    )
    assert outsider_board.status_code == 403

    bad_assignee = client.patch(
        f"/api/sequences/{sequence['id']}/workflow",
        headers=auth(owner_token),
        json={
            "status": "testing",
            "priority": "medium",
            "assigned_to": 999,
            "discipline_owner": "assay",
        },
    )
    assert bad_assignee.status_code == 400
