from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from proteinhub.api import create_api_router
from proteinhub.application.reverse_translation import translate_dna
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


def register(client: TestClient, email: str, name: str = "") -> str:
    payload = {
        "name": name or email.split("@", 1)[0],
        "email": email,
        "password": "password123",
    }
    response = client.post(
        "/api/auth/register",
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_user_cannot_list_projects(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/projects")

    assert response.status_code == 401


def test_database_schema_has_no_sequence_or_collaboration_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"
    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        protein_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(proteins)")
        }
        batch_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(batches)")
        }
        batch_well_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(batch_wells)")
        }
        applied_migrations = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        }

    assert "sequences" not in tables
    assert "sequence_comments" not in tables
    assert "protein_comments" not in tables
    assert "batches" in tables
    assert "batch_wells" in tables
    assert "batch_experiments" in tables
    assert "fplc_experiments" in tables
    assert "spr_experiments" in tables
    assert "hplc_experiments" in tables
    assert "experiment_well_results" in tables
    assert "schema_migrations" in tables
    assert "0001_current_schema" in applied_migrations
    assert "experiment_type" not in batch_columns
    assert "result_value" not in batch_well_columns
    assert "result_note" not in batch_well_columns
    assert not {
        "status",
        "priority",
        "assigned_to",
        "discipline_owner",
        "design_rationale",
        "handoff_note",
        "risk_note",
    }.intersection(protein_columns)


def test_init_db_removes_retired_collaboration_schema_from_existing_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                owner_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE proteins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                sequence TEXT NOT NULL,
                dna_sequence TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                version_tag TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                priority TEXT NOT NULL DEFAULT 'medium',
                assigned_to INTEGER REFERENCES users(id),
                discipline_owner TEXT NOT NULL DEFAULT '',
                design_rationale TEXT NOT NULL DEFAULT '',
                handoff_note TEXT NOT NULL DEFAULT '',
                risk_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE protein_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
                author_id INTEGER NOT NULL REFERENCES users(id),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE sequences (id INTEGER PRIMARY KEY AUTOINCREMENT);
            CREATE TABLE sequence_comments (id INTEGER PRIMARY KEY AUTOINCREMENT);
            CREATE TABLE batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                experiment_type TEXT NOT NULL DEFAULT '',
                plate_format TEXT NOT NULL DEFAULT '96',
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE batch_wells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
                position TEXT NOT NULL,
                result_value TEXT NOT NULL DEFAULT '',
                result_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT '',
                UNIQUE (batch_id, position)
            );

            INSERT INTO users (id, name, email, password_hash)
            VALUES (1, 'Owner', 'owner@example.com', 'hash');
            INSERT INTO projects (id, name, owner_id)
            VALUES (3, 'Legacy project', 1);
            INSERT INTO proteins (
                id,
                project_id,
                name,
                sequence,
                dna_sequence,
                description,
                version_tag,
                status,
                priority,
                assigned_to,
                discipline_owner,
                design_rationale,
                handoff_note,
                risk_note
            )
            VALUES (
                7,
                3,
                'legacy protein',
                'ACD',
                'GCTTGTGAT',
                'kept',
                'v0',
                'testing',
                'high',
                1,
                'assay',
                'drop me',
                'drop me too',
                'also drop'
            );
            INSERT INTO protein_comments (protein_id, author_id, body)
            VALUES (7, 1, 'old dynamic note');
            INSERT INTO batches (
                id,
                project_id,
                name,
                description,
                experiment_type,
                plate_format,
                created_by
            )
            VALUES (9, 3, 'legacy batch', 'kept batch', 'FPLC', '96', 1);
            INSERT INTO batch_wells (
                id,
                batch_id,
                protein_id,
                position,
                result_value,
                result_note
            )
            VALUES (11, 9, 7, 'A01', 'old result', 'old note');
            """
        )

    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        protein_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(proteins)")
        }
        batch_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(batches)")
        }
        batch_well_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(batch_wells)")
        }
        protein = connection.execute(
            "SELECT id, name, sequence, dna_sequence, description, version_tag FROM proteins"
        ).fetchone()
        batch = connection.execute(
            "SELECT id, name, description, plate_format FROM batches"
        ).fetchone()
        well = connection.execute(
            "SELECT id, batch_id, protein_id, position FROM batch_wells"
        ).fetchone()

    assert "protein_comments" not in tables
    assert "sequences" not in tables
    assert "sequence_comments" not in tables
    assert not {
        "status",
        "priority",
        "assigned_to",
        "discipline_owner",
        "design_rationale",
        "handoff_note",
        "risk_note",
    }.intersection(protein_columns)
    assert "experiment_type" not in batch_columns
    assert "result_value" not in batch_well_columns
    assert "result_note" not in batch_well_columns
    assert protein == (7, "legacy protein", "ACD", "GCTTGTGAT", "kept", "v0")
    assert batch == (9, "legacy batch", "kept batch", "96")
    assert well == (11, 9, 7, "A01")


def test_register_requires_name_but_login_does_not(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    missing_name = client.post(
        "/api/auth/register",
        json={"email": "noname@example.com", "password": "password123"},
    )
    assert missing_name.status_code == 422

    blank_name = client.post(
        "/api/auth/register",
        json={"name": " ", "email": "blank@example.com", "password": "password123"},
    )
    assert blank_name.status_code == 400

    token = register(client, "named@example.com", "有姓名用户")
    login = client.post(
        "/api/auth/login",
        json={"email": "named@example.com", "password": "password123"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
    assert login.json()["user"]["name"] == "有姓名用户"
    assert token


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
        json={
            "name": "Protein A",
            "sequence": "acdefg",
            "description": "first",
            "version_tag": "v1",
        },
    ).json()
    assert protein["sequence"] == "ACDEFG"
    assert translate_dna(protein["dna_sequence"]) == "ACDEFG"

    upload = client.post(
        f"/api/proteins/{protein['id']}/artifacts",
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


def test_legacy_sequence_api_routes_are_removed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Protein-only project"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "Protein A", "sequence": "ACD"},
    ).json()

    legacy_protein_sequences = client.get(
        f"/api/proteins/{protein['id']}/sequences",
        headers=auth(owner_token),
    )
    get_sequence = client.get(
        f"/api/sequences/{protein['id']}",
        headers=auth(owner_token),
    )

    assert legacy_protein_sequences.status_code == 404
    assert get_sequence.status_code == 404


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
        json={"name": "Protein A", "sequence": "ACD"},
    ).json()

    denied = client.get(
        f"/api/proteins/{protein['id']}",
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
        f"/api/proteins/{protein['id']}/artifacts",
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


def test_owner_can_search_member_candidates_by_name(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com", "项目负责人")
    synthesis_token = register(client, "synthesis@example.com", "合成组")
    register(client, "assay@example.com", "测试组")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Search project"},
    ).json()

    search = client.get(
        f"/api/projects/{project['id']}/member-candidates",
        headers=auth(owner_token),
        params={"query": "合成"},
    )

    assert search.status_code == 200, search.text
    candidates = search.json()
    assert len(candidates) == 1
    assert candidates[0]["name"] == "合成组"
    assert candidates[0]["email"] == "synthesis@example.com"

    denied = client.get(
        f"/api/projects/{project['id']}/member-candidates",
        headers=auth(synthesis_token),
        params={"query": "测试"},
    )
    assert denied.status_code == 403

    added = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "synthesis@example.com", "role": "member"},
    )
    assert added.status_code == 200, added.text
    assert added.json()["name"] == "合成组"

    members = client.get(
        f"/api/projects/{project['id']}",
        headers=auth(owner_token),
    ).json()["members"]
    assert any(member["name"] == "合成组" for member in members)

    search_after_add = client.get(
        f"/api/projects/{project['id']}/member-candidates",
        headers=auth(owner_token),
        params={"query": "合成"},
    )
    assert search_after_add.status_code == 200
    assert search_after_add.json() == []


def test_owner_can_update_project_member_role_and_discipline(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com", "项目负责人")
    member_token = register(client, "member@example.com", "计算设计")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Member settings"},
    ).json()
    members = client.get(
        f"/api/projects/{project['id']}",
        headers=auth(owner_token),
    ).json()["members"]
    owner_id = next(
        member["id"] for member in members if member["email"] == "owner@example.com"
    )

    sole_owner_demote = client.patch(
        f"/api/projects/{project['id']}/members/{owner_id}",
        headers=auth(owner_token),
        json={"role": "member", "discipline": "design"},
    )
    assert sole_owner_demote.status_code == 400

    added = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "member", "discipline": "other"},
    )
    assert added.status_code == 200, added.text
    member_id = added.json()["id"]

    member_cannot_update = client.patch(
        f"/api/projects/{project['id']}/members/{member_id}",
        headers=auth(member_token),
        json={"role": "owner", "discipline": "design"},
    )
    assert member_cannot_update.status_code == 403

    updated = client.patch(
        f"/api/projects/{project['id']}/members/{member_id}",
        headers=auth(owner_token),
        json={"role": "owner", "discipline": "design"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "owner"
    assert updated.json()["discipline"] == "design"

    refreshed_members = client.get(
        f"/api/projects/{project['id']}",
        headers=auth(owner_token),
    ).json()["members"]
    design_member = next(
        member for member in refreshed_members if member["email"] == "member@example.com"
    )
    assert design_member["role"] == "owner"
    assert design_member["discipline"] == "design"


def test_collaboration_routes_are_removed_from_protein_flow(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Binder records"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "candidate-7", "sequence": "ACDEFGHIK", "version_tag": "screen-1"},
    ).json()

    detail = client.get(f"/api/proteins/{protein['id']}", headers=auth(owner_token))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert set(payload) == {"protein", "artifacts", "batch_results"}
    assert payload["protein"]["name"] == "candidate-7"
    assert payload["protein"]["protein_name"] == "candidate-7"
    assert payload["protein"]["version_tag"] == "screen-1"
    assert payload["artifacts"] == []
    assert payload["batch_results"] == []

    project_proteins = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
    ).json()
    assert project_proteins[0]["artifact_count"] == 0

    retired_fields = {
        "status",
        "priority",
        "assigned_to",
        "assigned_to_email",
        "discipline_owner",
        "design_rationale",
        "handoff_note",
        "risk_note",
    }
    assert not retired_fields.intersection(payload["protein"])
    assert not retired_fields.intersection(project_proteins[0])

    board = client.get(f"/api/projects/{project['id']}/board", headers=auth(owner_token))
    workflow = client.patch(
        f"/api/proteins/{protein['id']}/workflow",
        headers=auth(owner_token),
        json={"status": "testing"},
    )
    comment = client.post(
        f"/api/proteins/{protein['id']}/comments",
        headers=auth(owner_token),
        json={"body": "no longer supported"},
    )

    assert board.status_code == 404
    assert workflow.status_code == 404
    assert comment.status_code == 404


def test_batch_wells_map_results_back_to_project_proteins(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Plate experiment"},
    ).json()
    protein_a = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-a", "sequence": "ACDEFG"},
    ).json()
    protein_b = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-b", "sequence": "HIKLMN"},
    ).json()
    added_member = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "member"},
    )
    assert added_member.status_code == 200, added_member.text

    outsider_project = client.post(
        "/api/projects",
        headers=auth(outsider_token),
        json={"name": "Other project"},
    ).json()
    outsider_protein = client.post(
        f"/api/projects/{outsider_project['id']}/proteins",
        headers=auth(outsider_token),
        json={"name": "other-protein", "sequence": "QRSTVW"},
    ).json()

    cross_project_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "bad plate",
            "protein_ids": [protein_a["id"], outsider_protein["id"]],
        },
    )
    assert cross_project_batch.status_code == 400

    empty_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "empty plate", "protein_ids": []},
    )
    assert empty_batch.status_code == 400

    created = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Screening batch 1",
            "description": "first screening plate",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    )
    assert created.status_code == 200, created.text
    batch_payload = created.json()
    batch = batch_payload["batch"]
    wells = batch_payload["wells"]
    assert batch["name"] == "Screening batch 1"
    assert batch["plate_format"] == "96"
    assert batch_payload["experiments"] == []
    assert [(well["position"], well["protein_id"]) for well in wells] == [
        ("A01", protein_a["id"]),
        ("A02", protein_b["id"]),
    ]
    assert wells[0]["protein_name"] == "binder-a"

    listed = client.get(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["well_count"] == 2
    assert listed.json()[0]["experiment_count"] == 0
    assert listed.json()[0]["result_count"] == 0

    member_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(member_token),
    )
    assert member_detail.status_code == 200, member_detail.text

    outsider_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(outsider_token),
    )
    assert outsider_detail.status_code == 403

    unsupported_experiment = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "ELISA", "name": "ELISA run"},
    )
    assert unsupported_experiment.status_code == 400

    fplc = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={
            "experiment_type": "FPLC",
            "name": "FPLC run 1",
            "description": "SEC purification",
            "details": {"column": "Superdex 200"},
        },
    )
    assert fplc.status_code == 200, fplc.text
    fplc_payload = fplc.json()
    fplc_experiment = fplc_payload["experiment"]
    assert fplc_experiment["experiment_type"] == "FPLC"
    assert fplc_experiment["details"] == {"column": "Superdex 200"}
    assert [(row["position"], row["protein_id"]) for row in fplc_payload["results"]] == [
        ("A01", protein_a["id"]),
        ("A02", protein_b["id"]),
    ]

    spr = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "SPR", "name": "SPR kinetics"},
    )
    hplc = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "HPLC", "name": "HPLC purity"},
    )
    assert spr.status_code == 200, spr.text
    assert hplc.status_code == 200, hplc.text

    experiments = client.get(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(member_token),
    )
    assert experiments.status_code == 200, experiments.text
    assert {experiment["experiment_type"] for experiment in experiments.json()} == {
        "FPLC",
        "SPR",
        "HPLC",
    }

    outsider_experiment = client.get(
        f"/api/experiments/{fplc_experiment['id']}",
        headers=auth(outsider_token),
    )
    assert outsider_experiment.status_code == 403

    well_a_id = wells[0]["id"]
    updated_result = client.patch(
        f"/api/experiments/{fplc_experiment['id']}/wells/{well_a_id}/result",
        headers=auth(member_token),
        json={"result_value": "peak=1.42 AU", "result_note": "clean monomer"},
    )
    assert updated_result.status_code == 200, updated_result.text
    assert updated_result.json()["result_value"] == "peak=1.42 AU"

    outsider_update = client.patch(
        f"/api/experiments/{fplc_experiment['id']}/wells/{well_a_id}/result",
        headers=auth(outsider_token),
        json={"result_value": "tamper"},
    )
    assert outsider_update.status_code == 403

    listed_after_result = client.get(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
    )
    assert listed_after_result.status_code == 200
    assert listed_after_result.json()[0]["experiment_count"] == 3
    assert listed_after_result.json()[0]["result_count"] == 1

    experiment_detail = client.get(
        f"/api/experiments/{fplc_experiment['id']}",
        headers=auth(owner_token),
    )
    assert experiment_detail.status_code == 200, experiment_detail.text
    result_row = experiment_detail.json()["results"][0]
    assert result_row["well_id"] == well_a_id
    assert result_row["result_value"] == "peak=1.42 AU"

    protein_detail = client.get(
        f"/api/proteins/{protein_a['id']}",
        headers=auth(owner_token),
    )
    assert protein_detail.status_code == 200, protein_detail.text
    result = protein_detail.json()["batch_results"][0]
    assert result["batch_id"] == batch["id"]
    assert result["batch_name"] == "Screening batch 1"
    assert result["experiment_id"] == fplc_experiment["id"]
    assert result["experiment_name"] == "FPLC run 1"
    assert result["experiment_type"] == "FPLC"
    assert result["position"] == "A01"
    assert result["result_value"] == "peak=1.42 AU"
    assert result["result_note"] == "clean monomer"


def test_parse_sequence_from_pdb_and_mmcif_structure_files(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Structure import"},
    ).json()
    pdb = b"HEADER    TEST\nSEQRES   1 A    5  MET GLY SER THR LYS\n"
    pdb_parse = client.post(
        f"/api/projects/{project['id']}/proteins/parse-structure",
        headers=auth(owner_token),
        files={"file": ("target.pdb", pdb, "chemical/x-pdb")},
    )
    assert pdb_parse.status_code == 200, pdb_parse.text
    assert pdb_parse.json()["sequence"] == "MGSTK"
    assert pdb_parse.json()["chain_id"] == "A"
    assert pdb_parse.json()["source"] == "PDB SEQRES chain A"

    mmcif = b"""data_target
_entity_poly.entity_id 1
_entity_poly.type 'polypeptide(L)'
_entity_poly.pdbx_strand_id B
_entity_poly.pdbx_seq_one_letter_code_can
;ACD
EFG
;
    """
    mmcif_parse = client.post(
        f"/api/projects/{project['id']}/proteins/parse-structure",
        headers=auth(owner_token),
        files={"file": ("target.cif", mmcif, "chemical/x-mmcif")},
    )
    assert mmcif_parse.status_code == 200, mmcif_parse.text
    assert mmcif_parse.json()["sequence"] == "ACDEFG"
    assert mmcif_parse.json()["entity_id"] == "1"
    assert mmcif_parse.json()["chain_id"] == "B"

    outsider_parse = client.post(
        f"/api/projects/{project['id']}/proteins/parse-structure",
        headers=auth(outsider_token),
        files={"file": ("target.pdb", pdb, "chemical/x-pdb")},
    )
    assert outsider_parse.status_code == 403
