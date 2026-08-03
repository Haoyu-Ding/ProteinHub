from __future__ import annotations

import sqlite3
import sys
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from fastapi.testclient import TestClient

from proteinhub.api import create_api_router
from proteinhub.application.reverse_translation import translate_dna
from proteinhub.config import Settings
from proteinhub.db import init_db


def make_client(tmp_path: Path) -> TestClient:
    domesticator_script, domesticator_database = write_fake_domesticator(tmp_path)
    akta_script = write_fake_akta_hap(tmp_path)
    settings = Settings(
        database_path=tmp_path / "proteinhub.sqlite3",
        storage_root=tmp_path / "storage",
        jwt_secret="test-secret",
        nicegui_storage_secret="test-storage-secret",
        legacy_domesticator_python=Path(sys.executable),
        legacy_domesticator_script=domesticator_script,
        legacy_domesticator_database=domesticator_database,
        legacy_domesticator_timeout_seconds=30,
        akta_hap_python=Path(sys.executable),
        akta_hap_script=akta_script,
        akta_hap_timeout_seconds=30,
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


def write_fake_domesticator(tmp_path: Path) -> tuple[Path, Path]:
    database = tmp_path / "fake_domesticator_database"
    database.mkdir()
    script = tmp_path / "fake_domesticator.py"
    script.write_text(
"""
from pathlib import Path
import os
import sys

EXPECTED_PATTERNS = {
    "AGGAGG", "TAAGGAG", "GCTGGTGG", "TTTTTT", "AAAAAAA", "ATCTGTT",
    "GGRGGT", "MAGGTRAG", "YYYYNTAGG", "GGTCTC", "GAGACC",
}
CODONS = {
    "A": "GCT", "C": "TGT", "D": "GAT", "E": "GAA", "F": "TTT",
    "G": "GGT", "H": "CAT", "I": "ATT", "K": "AAA", "L": "CTG",
    "M": "ATG", "N": "AAT", "P": "CCG", "Q": "CAG", "R": "CGT",
    "S": "AGC", "T": "ACC", "V": "GTG", "W": "TGG", "Y": "TAT",
    "*": "TAA",
}

def require(flag, value):
    if flag not in sys.argv:
        raise SystemExit(f"missing {flag}")
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv) or sys.argv[index + 1] != value:
        raise SystemExit(f"unexpected {flag}")

def require_all_after(flag, values):
    if flag not in sys.argv:
        raise SystemExit(f"missing {flag}")
    index = sys.argv.index(flag)
    observed = set()
    for value in sys.argv[index + 1:]:
        if value.startswith("--"):
            break
        observed.add(value)
    if observed != set(values):
        raise SystemExit(f"unexpected {flag}: {observed}")

def read_fasta(path):
    records = []
    current_id = ""
    sequence_lines = []
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id:
                records.append((current_id, "".join(sequence_lines)))
            current_id = line[1:].split()[0]
            sequence_lines = []
        else:
            sequence_lines.append(line)
    if current_id:
        records.append((current_id, "".join(sequence_lines)))
    return records

def wrap(sequence, width=60):
    return "\\n".join(sequence[index:index + width] for index in range(0, len(sequence), width))

require_all_after("--avoid_restriction_sites", ["XhoI", "NdeI"])
require_all_after("--avoid_patterns", EXPECTED_PATTERNS)
require("--species", "e_coli")
require("--avoid_kmers", "8")
require("--avoid_kmers_boost", "25")
require("--output_mode", "fasta")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[sys.argv.index("--output_filename") + 1])
bad_translation = os.environ.get("FAKE_DOMESTICATOR_BAD_TRANSLATION") == "1"
with output_path.open("w") as handle:
    for record_id, protein_sequence in read_fasta(input_path):
        dna_sequence = "TAA" if bad_translation else "".join(CODONS[aa] for aa in protein_sequence)
        handle.write(f">{record_id}\\n{wrap(dna_sequence)}\\n")
""".lstrip(),
        encoding="utf-8",
    )
    return script, database


def write_fake_akta_hap(tmp_path: Path) -> Path:
    script = tmp_path / "fake_akta_hap.py"
    script.write_text(
"""
from pathlib import Path
import sys

if "--output" not in sys.argv:
    raise SystemExit("missing --output")
output = sys.argv[sys.argv.index("--output") + 1]
if output != "png":
    raise SystemExit("unexpected output")

for argument in sys.argv[1:sys.argv.index("--output")]:
    path = Path(argument)
    if path.suffix.lower() != ".zip":
        raise SystemExit("only zip inputs are supported")
    output_path = Path.cwd() / f"{path.stem}.png"
    output_path.write_bytes(f"PNG for {path.name}".encode())
""".lstrip(),
        encoding="utf-8",
    )
    return script


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


def xlsx_sheet_values(content: bytes) -> dict[str, str | int]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(content)) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml")
    root = ElementTree.fromstring(sheet_xml)
    values = {}
    for cell in root.findall(".//main:c", namespace):
        reference = cell.attrib["r"]
        if cell.attrib.get("t") == "inlineStr":
            text = cell.find("main:is/main:t", namespace)
            values[reference] = text.text if text is not None and text.text else ""
            continue
        value = cell.find("main:v", namespace)
        if value is not None and value.text:
            values[reference] = int(value.text) if value.text.isdigit() else value.text
    return values


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
    assert "akta_experiments" in tables
    assert "experiment_well_results" in tables
    assert "schema_migrations" in tables
    assert "0001_current_schema" in applied_migrations
    assert "protein_type" in protein_columns
    assert "target" in protein_columns
    assert "structure_filename" in protein_columns
    assert "structure_mime_type" in protein_columns
    assert "structure_size_bytes" in protein_columns
    assert "structure_storage_path" in protein_columns
    assert "version_tag" not in protein_columns
    assert "experiment_type" not in batch_columns
    assert "order_status" in batch_columns
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


def test_init_db_expands_experiment_type_constraint_for_akta(tmp_path: Path) -> None:
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
            CREATE TABLE batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                plate_format TEXT NOT NULL DEFAULT '96',
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE batch_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                experiment_type TEXT NOT NULL CHECK (experiment_type IN ('FPLC', 'SPR', 'HPLC')),
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE fplc_experiments (
                experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE spr_experiments (
                experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE hplc_experiments (
                experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            INSERT INTO users (id, name, email, password_hash)
            VALUES (1, 'Owner', 'owner@example.com', 'hash');
            INSERT INTO projects (id, name, owner_id)
            VALUES (3, 'Legacy project', 1);
            INSERT INTO batches (id, project_id, name, plate_format, created_by)
            VALUES (9, 3, 'legacy batch', '96', 1);
            INSERT INTO batch_experiments (id, batch_id, experiment_type, name, created_by)
            VALUES (5, 9, 'FPLC', 'old fplc', 1);
            INSERT INTO fplc_experiments (experiment_id, details_json)
            VALUES (5, '{"column": "old"}');
            """
        )

    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        table_sql = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'batch_experiments'
            """
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        preserved = connection.execute(
            """
            SELECT id, experiment_type, name
            FROM batch_experiments
            WHERE id = 5
            """
        ).fetchone()
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO batch_experiments (
                id, batch_id, experiment_type, name, created_by
            )
            VALUES (6, 9, 'AKTA', 'akta import', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO akta_experiments (experiment_id, details_json)
            VALUES (6, '{}')
            """
        )

    assert "'AKTA'" in table_sql
    assert "akta_experiments" in tables
    assert preserved == (5, "FPLC", "old fplc")


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
                'nanobody',
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
            """
            SELECT
                id,
                name,
                sequence,
                dna_sequence,
                description,
                protein_type,
                target,
                structure_filename,
                structure_mime_type,
                structure_size_bytes,
                structure_storage_path
            FROM proteins
            """
        ).fetchone()
        batch = connection.execute(
            "SELECT id, name, description, plate_format, order_status FROM batches"
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
    assert "protein_type" in protein_columns
    assert "target" in protein_columns
    assert "structure_filename" in protein_columns
    assert "structure_mime_type" in protein_columns
    assert "structure_size_bytes" in protein_columns
    assert "structure_storage_path" in protein_columns
    assert "version_tag" not in protein_columns
    assert "order_status" in batch_columns
    assert protein == (
        7,
        "legacy protein",
        "ACD",
        "GCTTGTGAT",
        "kept",
        "nanobody",
        "",
        "",
        "application/octet-stream",
        0,
        "",
    )
    assert batch == (9, "legacy batch", "kept batch", "96", "not_ordered")
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
            "protein_type": "nanobody",
            "target": "EGFR",
        },
    ).json()
    assert protein["sequence"] == "ACDEFG"
    assert protein["protein_type"] == "nanobody"
    assert protein["target"] == "EGFR"
    assert protein["structure_storage_path"] == ""
    assert protein["structure_filename"] == ""
    assert protein["structure_size_bytes"] == 0
    assert "dna_sequence" not in protein

    no_structure_download = client.get(
        f"/api/proteins/{protein['id']}/structure/download",
        headers=auth(owner_token),
    )
    assert no_structure_download.status_code == 404

    invalid_type = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "bad type", "sequence": "ACD", "protein_type": "antibody"},
    )
    assert invalid_type.status_code == 400

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


def test_create_protein_with_structure_file_can_download_structure(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Structure-backed protein"},
    ).json()
    pdb = b"HEADER    TEST\nSEQRES   1 A    3  MET GLY LYS\n"
    created = client.post(
        f"/api/projects/{project['id']}/proteins/with-structure",
        headers=auth(owner_token),
        data={
            "name": "binder-with-pdb",
            "sequence": "MGK",
            "protein_type": "minibinder",
            "target": "CD3",
            "description": "from PDB",
        },
        files={"file": ("folder/source.pdb", pdb, "chemical/x-pdb")},
    )

    assert created.status_code == 200, created.text
    protein = created.json()
    assert protein["name"] == "binder-with-pdb"
    assert protein["sequence"] == "MGK"
    assert protein["protein_type"] == "minibinder"
    assert protein["target"] == "CD3"
    assert protein["structure_filename"] == "source.pdb"
    assert protein["structure_mime_type"] == "chemical/x-pdb"
    assert protein["structure_size_bytes"] == len(pdb)
    assert protein["structure_storage_path"].endswith("/source.pdb")

    download = client.get(
        f"/api/proteins/{protein['id']}/structure/download",
        headers=auth(owner_token),
    )
    assert download.status_code == 200, download.text
    assert download.content == pdb

    outsider_download = client.get(
        f"/api/proteins/{protein['id']}/structure/download",
        headers=auth(outsider_token),
    )
    assert outsider_download.status_code == 403

    chain_b_only = client.post(
        f"/api/projects/{project['id']}/proteins/with-structure",
        headers=auth(owner_token),
        data={"name": "bad", "sequence": "MG", "protein_type": "TCR"},
        files={"file": ("bad.pdb", b"SEQRES   1 B    2  MET GLY\n", "chemical/x-pdb")},
    )
    assert chain_b_only.status_code == 400


def test_import_proteins_from_structure_folder(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Folder import"},
    ).json()
    pdb = b"HEADER    TEST\nSEQRES   1 A    3  MET GLY LYS\n"
    mmcif = b"""data_target
_entity_poly.entity_id 1
_entity_poly.type 'polypeptide(L)'
_entity_poly.pdbx_strand_id A
_entity_poly.pdbx_seq_one_letter_code_can
;ACD
EFG
;
"""

    imported = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(owner_token),
        data={
            "protein_type": "TCR",
            "target": "MAGE-A4",
            "description": "folder import",
        },
        files=[
            ("files", ("folder/binder-a.pdb", pdb, "chemical/x-pdb")),
            ("files", ("folder/binder-b.cif", mmcif, "chemical/x-mmcif")),
        ],
    )
    assert imported.status_code == 200, imported.text
    proteins = imported.json()
    assert [protein["name"] for protein in proteins] == ["binder-a", "binder-b"]
    assert [protein["sequence"] for protein in proteins] == ["MGK", "ACDEFG"]
    assert {protein["protein_type"] for protein in proteins} == {"TCR"}
    assert {protein["target"] for protein in proteins} == {"MAGE-A4"}
    assert {protein["description"] for protein in proteins} == {"folder import"}
    assert [protein["structure_filename"] for protein in proteins] == [
        "binder-a.pdb",
        "binder-b.cif",
    ]
    assert [protein["structure_size_bytes"] for protein in proteins] == [
        len(pdb),
        len(mmcif),
    ]
    assert "dna_sequence" not in proteins[0]

    pdb_download = client.get(
        f"/api/proteins/{proteins[0]['id']}/structure/download",
        headers=auth(owner_token),
    )
    assert pdb_download.status_code == 200, pdb_download.text
    assert pdb_download.content == pdb

    rejected = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(owner_token),
        data={"protein_type": "nanobody", "target": "bad"},
        files=[
            (
                "files",
                ("folder/chain-b-only.pdb", b"SEQRES   1 B    2  MET GLY\n", "chemical/x-pdb"),
            )
        ],
    )
    assert rejected.status_code == 400
    assert "chain A" in rejected.json()["detail"]

    project_proteins = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
    )
    assert project_proteins.status_code == 200
    assert len(project_proteins.json()) == 2

    outsider_import = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(outsider_token),
        data={"protein_type": "TCR"},
        files=[("files", ("folder/outsider.pdb", pdb, "chemical/x-pdb"))],
    )
    assert outsider_import.status_code == 403


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
        json={
            "name": "candidate-7",
            "sequence": "ACDEFGHIK",
            "protein_type": "minibinder",
            "target": "PD-L1",
        },
    ).json()

    detail = client.get(f"/api/proteins/{protein['id']}", headers=auth(owner_token))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert set(payload) == {"protein", "artifacts", "batch_results"}
    assert payload["protein"]["name"] == "candidate-7"
    assert payload["protein"]["protein_name"] == "candidate-7"
    assert payload["protein"]["protein_type"] == "minibinder"
    assert payload["protein"]["target"] == "PD-L1"
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
        "version_tag",
        "dna_sequence",
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


def test_batch_well_positions_can_move_and_swap_before_results(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Plate layout"},
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

    created = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Position edit batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    )
    assert created.status_code == 200, created.text
    batch_payload = created.json()
    batch = batch_payload["batch"]
    well_a = next(
        well for well in batch_payload["wells"] if well["protein_id"] == protein_a["id"]
    )

    invalid_position = client.patch(
        f"/api/batches/{batch['id']}/wells/{well_a['id']}/position",
        headers=auth(owner_token),
        json={"position": "I01"},
    )
    assert invalid_position.status_code == 400

    outsider_move = client.patch(
        f"/api/batches/{batch['id']}/wells/{well_a['id']}/position",
        headers=auth(outsider_token),
        json={"position": "A03"},
    )
    assert outsider_move.status_code == 403

    moved = client.patch(
        f"/api/batches/{batch['id']}/wells/{well_a['id']}/position",
        headers=auth(member_token),
        json={"position": "A03", "mode": "move"},
    )
    assert moved.status_code == 200, moved.text
    positions = {
        well["protein_id"]: well["position"] for well in moved.json()["wells"]
    }
    assert positions == {protein_a["id"]: "A03", protein_b["id"]: "A02"}

    occupied_move = client.patch(
        f"/api/batches/{batch['id']}/wells/{well_a['id']}/position",
        headers=auth(owner_token),
        json={"position": "A02", "mode": "move"},
    )
    assert occupied_move.status_code == 409

    swapped = client.patch(
        f"/api/batches/{batch['id']}/wells/{well_a['id']}/position",
        headers=auth(owner_token),
        json={"position": "A02", "mode": "swap"},
    )
    assert swapped.status_code == 200, swapped.text
    positions = {
        well["protein_id"]: well["position"] for well in swapped.json()["wells"]
    }
    assert positions == {protein_a["id"]: "A02", protein_b["id"]: "A03"}

    fplc = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "FPLC", "name": "FPLC run"},
    )
    assert fplc.status_code == 200, fplc.text
    result = client.patch(
        f"/api/experiments/{fplc.json()['experiment']['id']}/wells/{well_a['id']}/result",
        headers=auth(owner_token),
        json={"result_value": "peak=1.0"},
    )
    assert result.status_code == 200, result.text

    locked_move = client.patch(
        f"/api/batches/{batch['id']}/wells/{well_a['id']}/position",
        headers=auth(owner_token),
        json={"position": "A04", "mode": "move"},
    )
    assert locked_move.status_code == 400


def test_batch_creation_can_start_from_selected_well(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Offset plate"},
    ).json()
    protein_a = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-a", "sequence": "ACD"},
    ).json()
    protein_b = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-b", "sequence": "EFG"},
    ).json()

    created = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Starts at C01",
            "protein_ids": [protein_a["id"], protein_b["id"]],
            "start_position": "C01",
        },
    )
    assert created.status_code == 200, created.text
    assert [
        (well["position"], well["protein_id"]) for well in created.json()["wells"]
    ] == [
        ("C01", protein_a["id"]),
        ("C02", protein_b["id"]),
    ]

    invalid_start = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Bad start",
            "protein_ids": [protein_a["id"]],
            "start_position": "I01",
        },
    )
    assert invalid_start.status_code == 400

    overflow = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Too few wells",
            "protein_ids": [protein_a["id"], protein_b["id"]],
            "start_position": "H12",
        },
    )
    assert overflow.status_code == 400


def test_batch_order_status_moves_forward_and_locks_ordered_batch_edits(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Order status plate"},
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

    created = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Order status batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    )
    assert created.status_code == 200, created.text
    batch_payload = created.json()
    batch = batch_payload["batch"]
    well = batch_payload["wells"][0]
    assert batch["order_status"] == "not_ordered"

    listed = client.get(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["order_status"] == "not_ordered"

    outsider_update = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(outsider_token),
        json={"order_status": "ordered"},
    )
    assert outsider_update.status_code == 403

    skipped_ordering = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "partially_received"},
    )
    assert skipped_ordering.status_code == 400

    ordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(member_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text
    assert ordered.json()["batch"]["order_status"] == "ordered"

    backwards = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "not_ordered"},
    )
    assert backwards.status_code == 400

    locked_move = client.patch(
        f"/api/batches/{batch['id']}/wells/{well['id']}/position",
        headers=auth(owner_token),
        json={"position": "A03", "mode": "move"},
    )
    assert locked_move.status_code == 400

    locked_translation = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(owner_token),
        json={"organism": "E. coli"},
    )
    assert locked_translation.status_code == 400

    fplc = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "FPLC", "name": "FPLC after order"},
    )
    assert fplc.status_code == 200, fplc.text

    result = client.patch(
        f"/api/experiments/{fplc.json()['experiment']['id']}/wells/{well['id']}/result",
        headers=auth(member_token),
        json={"result_value": "received", "result_note": "usable"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["result_value"] == "received"

    fully_received = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "fully_received"},
    )
    assert fully_received.status_code == 200, fully_received.text
    assert fully_received.json()["batch"]["order_status"] == "fully_received"

    back_from_fully_received = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "partially_received"},
    )
    assert back_from_fully_received.status_code == 400


def test_batch_order_status_can_move_through_partial_receipt(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Partial receipt plate"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder", "sequence": "ACDEFG"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Partial receipt batch", "protein_ids": [protein["id"]]},
    ).json()["batch"]

    ordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text

    partial = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "partially_received"},
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["batch"]["order_status"] == "partially_received"

    fully_received = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "fully_received"},
    )
    assert fully_received.status_code == 200, fully_received.text
    assert fully_received.json()["batch"]["order_status"] == "fully_received"


def test_batch_akta_results_upload_maps_pngs_to_batch_proteins(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "AKTA batch"},
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
    protein_c = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-c", "sequence": "PQRSTV"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "AKTA plate",
            "protein_ids": [protein_a["id"], protein_b["id"], protein_c["id"]],
        },
    ).json()["batch"]

    outsider_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(outsider_token),
        data={"run_date": "2026-08-01"},
        files=[("files", ("A01.zip", b"zip-a", "application/zip"))],
    )
    assert outsider_upload.status_code == 403

    bad_filename = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[("files", ("sample-1.zip", b"zip-a", "application/zip"))],
    )
    assert bad_filename.status_code == 400

    imported = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[
            ("files", ("A01.zip", b"zip-a", "application/zip")),
            ("files", ("A2.zip", b"zip-b", "application/zip")),
        ],
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    experiment = payload["experiment"]
    assert experiment["experiment_type"] == "AKTA"
    assert experiment["name"] == "AKTA 2026-08-01"
    assert experiment["details"] == {
        "file_count": 2,
        "requested_file_count": 2,
        "run_date": "2026-08-01",
        "skipped_positions": [],
        "source": "AKTA",
        "uploaded_positions": ["A01", "A02"],
    }
    assert {
        result["position"]: result["result_value"]
        for result in payload["results"]
        if result["result_value"]
    } == {
        "A01": "AKTA 2026-08-01",
        "A02": "AKTA 2026-08-01",
    }

    duplicate_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-02"},
        files=[("files", ("A01.zip", b"zip-a-again", "application/zip"))],
    )
    assert duplicate_upload.status_code == 409
    assert duplicate_upload.json()["detail"] == (
        "AKTA result already uploaded for position A01"
    )

    partial_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-02"},
        files=[
            ("files", ("A01.zip", b"zip-a-again", "application/zip")),
            ("files", ("A03.zip", b"zip-c", "application/zip")),
        ],
    )
    assert partial_upload.status_code == 200, partial_upload.text
    assert partial_upload.json()["experiment"]["details"] == {
        "file_count": 1,
        "requested_file_count": 2,
        "run_date": "2026-08-02",
        "skipped_positions": ["A01"],
        "source": "AKTA",
        "uploaded_positions": ["A03"],
    }
    assert {
        result["position"]: result["result_value"]
        for result in partial_upload.json()["results"]
        if result["result_value"]
    } == {
        "A03": "AKTA 2026-08-02",
    }

    duplicate_batch_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-03"},
        files=[
            ("files", ("A01.zip", b"zip-a-third", "application/zip")),
            ("files", ("A03.zip", b"zip-c-again", "application/zip")),
        ],
    )
    assert duplicate_batch_upload.status_code == 409
    assert duplicate_batch_upload.json()["detail"] == (
        "AKTA results already uploaded for positions: A01, A03"
    )

    batch_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(owner_token),
    )
    assert batch_detail.status_code == 200, batch_detail.text
    assert [
        experiment["experiment_type"]
        for experiment in batch_detail.json()["experiments"]
        if experiment["experiment_type"] == "AKTA"
    ] == ["AKTA", "AKTA"]

    protein_detail = client.get(
        f"/api/proteins/{protein_a['id']}",
        headers=auth(owner_token),
    )
    assert protein_detail.status_code == 200, protein_detail.text
    protein_payload = protein_detail.json()
    artifact_filenames = {
        artifact["filename"]: artifact
        for artifact in protein_payload["artifacts"]
    }
    assert "AKTA_2026-08-01_A01.zip" in artifact_filenames
    assert "AKTA_2026-08-01_A01.png" in artifact_filenames
    assert artifact_filenames["AKTA_2026-08-01_A01.png"]["artifact_type"] == "experimental_result"
    assert protein_payload["batch_results"][0]["result_value"] == "AKTA 2026-08-01"

    png_download = client.get(
        f"/api/artifacts/{artifact_filenames['AKTA_2026-08-01_A01.png']['id']}/download",
        headers=auth(owner_token),
    )
    assert png_download.status_code == 200, png_download.text
    assert png_download.content == b"PNG for A01.zip"


def test_batch_translation_generates_dna_on_demand(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Translation batch"},
    ).json()
    short_protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "short", "sequence": "MGK"},
    ).json()
    long_protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "long", "sequence": "ACDEFG"},
    ).json()
    assert "dna_sequence" not in short_protein

    created = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Translation plate",
            "protein_ids": [short_protein["id"], long_protein["id"]],
        },
    )
    assert created.status_code == 200, created.text
    batch = created.json()["batch"]

    summary_export = client.get(
        f"/api/batches/{batch['id']}/summary/export",
        headers=auth(owner_token),
    )
    assert summary_export.status_code == 200, summary_export.text
    assert summary_export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "batch-" in summary_export.headers["content-disposition"]
    summary_values = xlsx_sheet_values(summary_export.content)
    assert summary_values["A1"] == "Batch Summary"
    assert summary_values["B2"] == "Translation plate"
    assert summary_values["B3"] == "96 wells"
    assert summary_values["B4"] == "未设置"
    assert summary_values["B5"] == "未设置"
    assert summary_values["B6"] == 2
    assert summary_values["B7"] == 6
    assert summary_values["B8"] == 3
    assert summary_values["B9"] == "6-3"
    assert summary_values["A11"] == "Position"
    assert summary_values["B11"] == "Protein"
    assert summary_values["C11"] == "AA length"
    assert summary_values["A12"] == "A01"
    assert summary_values["B12"] == "short"
    assert summary_values["C12"] == 3
    assert summary_values["A13"] == "A02"
    assert summary_values["B13"] == "long"
    assert summary_values["C13"] == 6

    outsider_summary_export = client.get(
        f"/api/batches/{batch['id']}/summary/export",
        headers=auth(outsider_token),
    )
    assert outsider_summary_export.status_code == 403

    translated = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(owner_token),
        json={
            "padding": True,
            "add_additional_w": True,
            "organism": "E. coli",
            "backbone": "5",
            "resistance": "Kan",
        },
    )
    assert translated.status_code == 200, translated.text
    payload = translated.json()
    assert payload["padding"] is True
    assert payload["add_additional_w"] is True
    assert payload["organism"] == "E. coli"
    assert payload["backbone"] == "5"
    assert payload["resistance"] == "Kan"

    sequences = payload["sequences"]
    assert [sequence["translated_aa_sequence"] for sequence in sequences] == [
        "MGKWGGS",
        "ACDEFGW",
    ]
    assert translate_dna(sequences[0]["dna_sequence"]) == "MGKWGGS"
    assert translate_dna(sequences[1]["dna_sequence"]) == "ACDEFGW"
    assert payload["dna_fasta"].startswith(">A01 short\n")
    assert ">A02 long\n" in payload["dna_fasta"]

    batch_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(owner_token),
    )
    assert batch_detail.status_code == 200, batch_detail.text
    batch_payload = batch_detail.json()
    assert batch_payload["batch"]["translation_padding"] is True
    assert batch_payload["batch"]["translation_additional_w"] is True
    assert batch_payload["batch"]["translation_organism"] == "E. coli"
    assert batch_payload["batch"]["translation_backbone"] == "5"
    assert batch_payload["batch"]["translation_resistance"] == "Kan"
    assert batch_payload["wells"][0]["source_aa_sequence"] == "MGK"
    assert batch_payload["wells"][0]["translated_aa_sequence"] == "MGKWGGS"
    assert translate_dna(batch_payload["wells"][0]["dna_sequence"]) == "MGKWGGS"
    assert batch_payload["wells"][1]["source_aa_sequence"] == "ACDEFG"
    assert batch_payload["wells"][1]["translated_aa_sequence"] == "ACDEFGW"
    assert translate_dna(batch_payload["wells"][1]["dna_sequence"]) == "ACDEFGW"

    translated_summary_export = client.get(
        f"/api/batches/{batch['id']}/summary/export",
        headers=auth(owner_token),
    )
    assert translated_summary_export.status_code == 200, translated_summary_export.text
    translated_summary_values = xlsx_sheet_values(translated_summary_export.content)
    assert translated_summary_values["B4"] == "5"
    assert translated_summary_values["B5"] == "Kan"
    assert translated_summary_values["B6"] == 2
    assert translated_summary_values["B7"] == 7
    assert translated_summary_values["B8"] == 7
    assert translated_summary_values["B9"] == "7-7"
    assert translated_summary_values["A12"] == "A01"
    assert translated_summary_values["B12"] == "short"
    assert translated_summary_values["C12"] == 7
    assert translated_summary_values["A13"] == "A02"
    assert translated_summary_values["B13"] == "long"
    assert translated_summary_values["C13"] == 7

    invalid_organism = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(owner_token),
        json={"organism": "Yeast"},
    )
    assert invalid_organism.status_code == 400

    invalid_resistance = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(owner_token),
        json={"resistance": "Puro"},
    )
    assert invalid_resistance.status_code == 400

    outsider_translation = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(outsider_token),
        json={"organism": "E. coli"},
    )
    assert outsider_translation.status_code == 403


def test_batch_translation_uses_script_long_padding_rule(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Long padding batch"},
    ).json()
    short_protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "short", "sequence": "MGK"},
    ).json()
    long_protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "long", "sequence": "ACDEFGHIKLMNPQR"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Long padding plate",
            "protein_ids": [short_protein["id"], long_protein["id"]],
        },
    ).json()["batch"]

    translated = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(owner_token),
        json={
            "padding": True,
            "add_additional_w": True,
            "organism": "E. coli",
        },
    )
    assert translated.status_code == 200, translated.text
    sequences = translated.json()["sequences"]

    assert [sequence["translated_aa_sequence"] for sequence in sequences] == [
        "MGKWGSHHHHHH*GGS",
        "ACDEFGHIKLMNPQRW",
    ]
    assert translate_dna(sequences[0]["dna_sequence"]) == "MGKWGSHHHHHH*GGS"
    assert translate_dna(sequences[1]["dna_sequence"]) == "ACDEFGHIKLMNPQRW"


def test_batch_translation_rejects_dna_that_does_not_translate_back(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FAKE_DOMESTICATOR_BAD_TRANSLATION", "1")
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Verified translation batch"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder", "sequence": "MGK"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Verification plate", "protein_ids": [protein["id"]]},
    ).json()["batch"]

    translated = client.post(
        f"/api/batches/{batch['id']}/translations",
        headers=auth(owner_token),
        json={"organism": "E. coli"},
    )

    assert translated.status_code == 500
    assert "Legacy domesticator DNA verification failed" in translated.json()["detail"]


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
        json={
            "name": "binder-a",
            "sequence": "ACDEFG",
            "protein_type": "cyclic peptide",
            "target": "HER2",
        },
    ).json()
    protein_b = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={
            "name": "binder-b",
            "sequence": "HIKLMN",
            "protein_type": "enzymes",
            "target": "CD19",
        },
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
    assert wells[0]["protein_type"] == "cyclic peptide"

    plate_export = client.get(
        f"/api/batches/{batch['id']}/plate/export",
        headers=auth(member_token),
    )
    assert plate_export.status_code == 200, plate_export.text
    assert plate_export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "batch-" in plate_export.headers["content-disposition"]
    plate_values = xlsx_sheet_values(plate_export.content)
    assert plate_values["A1"] == "Screening batch 1\nfirst screening plate\nPlate 1"
    assert plate_values["B1"] == 1
    assert plate_values["M1"] == 12
    assert plate_values["A2"] == "A"
    assert plate_values["A9"] == "H"
    assert plate_values["B2"] == "binder-a"
    assert plate_values["C2"] == "binder-b"

    outsider_plate_export = client.get(
        f"/api/batches/{batch['id']}/plate/export",
        headers=auth(outsider_token),
    )
    assert outsider_plate_export.status_code == 403

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
    assert result_row["protein_type"] == "cyclic peptide"

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

    atom_only_pdb = b"""HEADER    TEST
ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  MET A   1       1.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   MET A   1       2.000   0.000   0.000  1.00 20.00           C
ATOM      4  CA  GLY A   2       3.000   0.000   0.000  1.00 20.00           C
ATOM      5  CA  LYS A   3       4.000   0.000   0.000  1.00 20.00           C
ATOM      6  CA  SER B   5       5.000   0.000   0.000  1.00 20.00           C
TER
"""
    atom_only_parse = client.post(
        f"/api/projects/{project['id']}/proteins/parse-structure",
        headers=auth(owner_token),
        files={"file": ("atom_only.pdb", atom_only_pdb, "chemical/x-pdb")},
    )
    assert atom_only_parse.status_code == 200, atom_only_parse.text
    assert atom_only_parse.json()["sequence"] == "MGK"
    assert atom_only_parse.json()["chain_id"] == "A"
    assert atom_only_parse.json()["source"] == "PDB ATOM chain A"
    assert atom_only_parse.json()["sequence_count"] == 2

    mmcif = b"""data_target
_entity_poly.entity_id 1
_entity_poly.type 'polypeptide(L)'
_entity_poly.pdbx_strand_id A
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
    assert mmcif_parse.json()["chain_id"] == "A"

    no_chain_a_pdb = b"HEADER    TEST\nSEQRES   1 B    2  MET GLY\n"
    no_chain_a_parse = client.post(
        f"/api/projects/{project['id']}/proteins/parse-structure",
        headers=auth(owner_token),
        files={"file": ("chain_b.pdb", no_chain_a_pdb, "chemical/x-pdb")},
    )
    assert no_chain_a_parse.status_code == 400
    assert "chain A" in no_chain_a_parse.json()["detail"]

    outsider_parse = client.post(
        f"/api/projects/{project['id']}/proteins/parse-structure",
        headers=auth(outsider_token),
        files={"file": ("target.pdb", pdb, "chemical/x-pdb")},
    )
    assert outsider_parse.status_code == 403
