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

