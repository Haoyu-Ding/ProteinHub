from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from fastapi.testclient import TestClient

from proteinhub.api import create_api_router
from proteinhub.application.auth_service import create_user
from proteinhub.application.reverse_translation import translate_dna
from proteinhub.config import Settings
from proteinhub.db import init_db
from proteinhub.infrastructure.database.connection import connect
from proteinhub.infrastructure.spr.pptx import _chart_svg


def make_client(
    tmp_path: Path,
    *,
    admin_emails: tuple[str, ...] | None = None,
) -> TestClient:
    domesticator_script, domesticator_database = write_fake_domesticator(tmp_path)
    akta_script = write_fake_akta_hap(tmp_path)
    settings_kwargs = {
        "database_path": tmp_path / "proteinhub.sqlite3",
        "storage_root": tmp_path / "storage",
        "jwt_secret": "test-secret",
        "nicegui_storage_secret": "test-storage-secret",
        "legacy_domesticator_python": Path(sys.executable),
        "legacy_domesticator_script": domesticator_script,
        "legacy_domesticator_database": domesticator_database,
        "legacy_domesticator_timeout_seconds": 30,
        "akta_hap_python": Path(sys.executable),
        "akta_hap_script": akta_script,
        "akta_hap_timeout_seconds": 30,
    }
    if admin_emails is not None:
        settings_kwargs["admin_emails"] = admin_emails
    settings = Settings(**settings_kwargs)
    init_db(settings.database_path)

    from fastapi import FastAPI

    app = FastAPI()
    app.state.settings = settings
    app.include_router(
        create_api_router(
            database_path=settings.database_path,
            storage_root=settings.storage_root,
            settings=settings,
        )
    )
    return TestClient(app)


def test_health_endpoint_reports_database_and_storage(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "database_backend": "sqlite",
        "storage": "ok",
        "artifact_storage_backend": "filesystem",
    }


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
if "--no_normalize" not in sys.argv:
    raise SystemExit("missing --no_normalize")

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


def make_fake_spr_pptx(
    samples: list[tuple[str, str]],
    *,
    chart_slide_numbers: list[int] | None = None,
    table_slide_number: int = 24,
    include_thumbnail_decoys: bool = False,
    use_relative_chart_targets: bool = False,
) -> bytes:
    chart_slide_numbers = chart_slide_numbers or list(range(9, 9 + len(samples)))
    assert len(chart_slide_numbers) == len(samples)
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for slide_number, (sample_id, _kd_value) in zip(
            chart_slide_numbers,
            samples,
            strict=True,
        ):
            chart_path = (
                f"ppt/charts/chart{slide_number}.xml"
                if use_relative_chart_targets
                else f"ppt/slides/charts/chart{slide_number}.xml"
            )
            chart_target = (
                f"../charts/chart{slide_number}.xml"
                if use_relative_chart_targets
                else f"/{chart_path}"
            )
            archive.writestr(
                f"ppt/slides/slide{slide_number}.xml",
                _spr_slide_xml(sample_id),
            )
            archive.writestr(
                f"ppt/slides/_rels/slide{slide_number}.xml.rels",
                _spr_slide_rels_xml(chart_target),
            )
            archive.writestr(chart_path, _spr_chart_xml(sample_id))
        archive.writestr(
            f"ppt/slides/slide{table_slide_number}.xml",
            _spr_table_slide_xml(samples),
        )
        if include_thumbnail_decoys:
            archive.writestr("docProps/thumbnail.jpeg", b"not a slide")
            archive.writestr(
                "ppt/slides/THUMBNAILS/slide3.xml",
                _spr_table_slide_xml([("A99XXX", "9.90e-09")]),
            )
            archive.writestr(
                "ppt/slides/slide99_thumbnail.xml",
                _spr_slide_xml("A98XXX"),
            )
    return buffer.getvalue()


def _spr_slide_xml(sample_id: str) -> str:
    return f"""
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:bodyPr/>
          <a:p><a:r><a:t>{sample_id}; BMPR2; 1:1 binding</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
      <p:graphicFrame>
        <a:graphic>
          <a:graphicData>
            <c:chart r:id="rId1"/>
          </a:graphicData>
        </a:graphic>
      </p:graphicFrame>
    </p:spTree>
  </p:cSld>
</p:sld>
""".strip()


def _spr_slide_rels_xml(chart_target: str) -> str:
    return f"""
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
                Target="{chart_target}"/>
</Relationships>
""".strip()


def _spr_chart_xml(sample_id: str) -> str:
    return f"""
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <c:chart>
    <c:plotArea>
      <c:scatterChart>
        <c:ser>
          <c:idx val="0"/>
          <c:spPr><a:ln><a:solidFill><a:srgbClr val="2563EB"/></a:solidFill></a:ln></c:spPr>
          <c:tx><c:strRef><c:strCache><c:pt idx="0"><c:v>{sample_id}</c:v></c:pt></c:strCache></c:strRef></c:tx>
          <c:xVal><c:numRef><c:numCache>
            <c:pt idx="0"><c:v>0</c:v></c:pt>
            <c:pt idx="1"><c:v>1</c:v></c:pt>
            <c:pt idx="2"><c:v>2</c:v></c:pt>
          </c:numCache></c:numRef></c:xVal>
          <c:yVal><c:numRef><c:numCache>
            <c:pt idx="0"><c:v>0</c:v></c:pt>
            <c:pt idx="1"><c:v>8</c:v></c:pt>
            <c:pt idx="2"><c:v>3</c:v></c:pt>
          </c:numCache></c:numRef></c:yVal>
        </c:ser>
      </c:scatterChart>
      <c:valAx><c:title><c:tx><c:rich><a:p><a:r><a:t>Time (s)</a:t></a:r></a:p></c:rich></c:tx></c:title></c:valAx>
      <c:valAx><c:title><c:tx><c:rich><a:p><a:r><a:t>Relative response (RU)</a:t></a:r></a:p></c:rich></c:tx></c:title></c:valAx>
    </c:plotArea>
  </c:chart>
</c:chartSpace>
""".strip()


def _spr_table_slide_xml(samples: list[tuple[str, str]]) -> str:
    headers = [
        "Group",
        "General\nKinetics model",
        "Curve markers",
        "Channel",
        "Injection variables\nCapture 1 Solution",
        "Single cycle kinetics 1 Solution",
        "Quality\nKinetics Chi² (RU²)",
        "1:1 binding\nka (1/Ms)",
        "kd (1/s)",
        "KD (M)",
        "Rmax (RU)",
        "tc",
    ]
    rows = [_spr_table_row_xml(headers)]
    for index, (sample_id, kd_value) in enumerate(samples, start=1):
        rows.append(
            _spr_table_row_xml(
                [
                    str(index),
                    "1:1 binding",
                    "",
                    str(index),
                    "BMPR2",
                    sample_id,
                    f"{index}.00e+00",
                    "1.00e+05",
                    "1.00e-03",
                    kd_value,
                    "25.0",
                    "1.00e+08",
                ]
            )
        )
    return f"""
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree><p:graphicFrame><a:graphic><a:graphicData><a:tbl>
    {"".join(rows)}
  </a:tbl></a:graphicData></a:graphic></p:graphicFrame></p:spTree></p:cSld>
</p:sld>
""".strip()


def _spr_table_row_xml(values: list[str]) -> str:
    cells = []
    for value in values:
        text = "".join(f"<a:r><a:t>{part}</a:t></a:r>" for part in value.split("\n"))
        cells.append(f"<a:tc><a:txBody><a:p>{text}</a:p></a:txBody></a:tc>")
    return f"<a:tr>{''.join(cells)}</a:tr>"


def register(client: TestClient, email: str, name: str = "") -> str:
    settings = client.app.state.settings
    connection = connect(settings)
    try:
        create_user(
            connection,
            name=name or email.split("@", 1)[0],
            email=email,
            password="password123",
            admin_emails=settings.admin_emails,
        )
    finally:
        connection.close()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def unique_test_sequence(index: int) -> str:
    amino_acids = "ACDEFGHIKLMNPQRSTVWY"
    return amino_acids[index % len(amino_acids)] * 6


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
        user_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        protein_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(proteins)")
        }
        public_protein_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(public_proteins)")
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
    assert "public_proteins" in tables
    assert "schema_migrations" in tables
    assert "0001_current_schema" in applied_migrations
    assert {
        "global_role",
        "is_active",
        "disabled_at",
        "disabled_by",
        "disabled_reason",
        "last_login_at",
        "password_updated_at",
    }.issubset(user_columns)
    assert "protein_type" in protein_columns
    assert "target" in protein_columns
    assert "manual_rating" in protein_columns
    assert "score_details_json" in protein_columns
    assert "sequence_similarity_status" in protein_columns
    assert "sequence_similarity_matches_json" in protein_columns
    assert "structure_filename" in protein_columns
    assert "structure_mime_type" in protein_columns
    assert "structure_size_bytes" in protein_columns
    assert "structure_storage_path" in protein_columns
    assert "structure_deposit_date" in protein_columns
    assert {
        "project_id",
        "name",
        "sequence",
        "description",
        "protein_type",
        "target",
        "created_by",
        "updated_at",
    }.issubset(public_protein_columns)
    assert "version_tag" not in protein_columns
    assert "experiment_type" not in batch_columns
    assert "order_status" in batch_columns
    assert "ordered_at" in batch_columns
    assert "receipt_note" in batch_columns
    assert "receipt_updated_by" in batch_columns
    assert "receipt_updated_at" in batch_columns
    assert "received_at" in batch_well_columns
    assert "received_by" in batch_well_columns
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
        user_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
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
                manual_rating,
                structure_filename,
                structure_mime_type,
                structure_size_bytes,
                structure_storage_path,
                structure_deposit_date
            FROM proteins
            """
        ).fetchone()
        batch = connection.execute(
            """
            SELECT
                id,
                name,
                description,
                plate_format,
                order_status,
                receipt_note,
                receipt_updated_by,
                receipt_updated_at
            FROM batches
            """
        ).fetchone()
        well = connection.execute(
            """
            SELECT id, batch_id, protein_id, position, received_at, received_by
            FROM batch_wells
            """
        ).fetchone()

    assert "protein_comments" not in tables
    assert "sequences" not in tables
    assert "sequence_comments" not in tables
    assert {
        "global_role",
        "is_active",
        "disabled_at",
        "disabled_by",
        "disabled_reason",
        "last_login_at",
        "password_updated_at",
    }.issubset(user_columns)
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
    assert "receipt_note" in batch_columns
    assert "receipt_updated_by" in batch_columns
    assert "receipt_updated_at" in batch_columns
    assert "received_at" in batch_well_columns
    assert "received_by" in batch_well_columns
    assert "result_value" not in batch_well_columns
    assert "result_note" not in batch_well_columns
    assert "ordered_at" in batch_columns
    assert "protein_type" in protein_columns
    assert "target" in protein_columns
    assert "manual_rating" in protein_columns
    assert "sequence_similarity_status" in protein_columns
    assert "sequence_similarity_matches_json" in protein_columns
    assert "structure_filename" in protein_columns
    assert "structure_mime_type" in protein_columns
    assert "structure_size_bytes" in protein_columns
    assert "structure_storage_path" in protein_columns
    assert "structure_deposit_date" in protein_columns
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
        "unrated",
        "",
        "application/octet-stream",
        0,
        "",
        "",
    )
    assert batch == (9, "legacy batch", "kept batch", "96", "not_ordered", "", None, "")
    assert well == (11, 9, 7, "A01", "", None)


def test_init_db_backfills_fully_received_batch_wells(tmp_path: Path) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"
    init_db(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users (id, name, email, password_hash) VALUES (1, 'Owner', 'owner@example.com', 'hash')"
        )
        connection.execute(
            "INSERT INTO projects (id, name, owner_id) VALUES (3, 'Project', 1)"
        )
        connection.execute(
            """
            INSERT INTO proteins (id, project_id, name, sequence)
            VALUES (7, 3, 'binder', 'ACD')
            """
        )
        connection.execute(
            """
            INSERT INTO batches (
                id,
                project_id,
                name,
                order_status,
                ordered_at,
                receipt_updated_by,
                receipt_updated_at,
                created_by
            )
            VALUES (
                9,
                3,
                'full batch',
                'fully_received',
                '2026-01-01 00:00:00',
                1,
                '2026-01-02 03:04:00',
                1
            )
            """
        )
        connection.execute(
            """
            INSERT INTO batch_wells (id, batch_id, protein_id, position)
            VALUES (11, 9, 7, 'A01')
            """
        )
        connection.commit()

    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        well = connection.execute(
            "SELECT received_at, received_by FROM batch_wells WHERE id = 11"
        ).fetchone()

    assert well == ("2026-01-02 03:04:00", 1)


def test_public_registration_route_is_not_available(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/register",
        json={
            "name": "公网访客",
            "email": "visitor@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 404


def test_admin_created_user_can_login(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    token = register(client, "named@example.com", "有姓名用户")

    login = client.post(
        "/api/auth/login",
        json={"email": "named@example.com", "password": "password123"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
    assert login.json()["user"]["name"] == "有姓名用户"
    assert token


def test_configured_admin_email_gets_global_role(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")
    admin_me = client.get("/api/me", headers=auth(admin_token))
    assert admin_me.status_code == 200, admin_me.text
    assert admin_me.json()["global_role"] == "admin"

    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "ruolan.chen@northstar-bio.local",
            "password": "password123",
        },
    )
    assert admin_login.status_code == 200, admin_login.text
    assert admin_login.json()["user"]["global_role"] == "admin"

    normal_token = register(client, "normal@example.com", "普通用户")
    normal_me = client.get("/api/me", headers=auth(normal_token))
    assert normal_me.status_code == 200, normal_me.text
    assert normal_me.json()["global_role"] == "user"


def test_internal_user_creation_can_assign_admin_role(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    settings = client.app.state.settings
    connection = connect(settings)
    try:
        user = create_user(
            connection,
            name="运维管理员",
            email="ops@example.com",
            password="password123",
            global_role="admin",
            admin_emails=settings.admin_emails,
        )
    finally:
        connection.close()

    assert user["global_role"] == "admin"
    login = client.post(
        "/api/auth/login",
        json={"email": "ops@example.com", "password": "password123"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["global_role"] == "admin"


def test_admin_can_manage_user_lifecycle(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")
    owner_token = register(client, "owner@example.com", "项目负责人")
    admin_user = client.get("/api/me", headers=auth(admin_token)).json()

    denied = client.get("/api/admin/users", headers=auth(owner_token))
    assert denied.status_code == 403

    created = client.post(
        "/api/admin/users",
        headers=auth(admin_token),
        json={
            "name": "新成员",
            "email": "new.member@example.com",
            "global_role": "user",
        },
    )
    assert created.status_code == 200, created.text
    created_payload = created.json()
    temporary_password = created_payload["temporary_password"]
    managed_user = created_payload["user"]
    assert len(temporary_password) >= 8
    assert managed_user["name"] == "新成员"
    assert managed_user["global_role"] == "user"
    assert managed_user["is_active"] is True
    assert managed_user["password_updated_at"]

    login = client.post(
        "/api/auth/login",
        json={"email": "new.member@example.com", "password": temporary_password},
    )
    assert login.status_code == 200, login.text
    managed_token = login.json()["access_token"]
    assert login.json()["user"]["last_login_at"]

    listed = client.get(
        "/api/admin/users",
        headers=auth(admin_token),
        params={"q": "new.member", "status": "active", "global_role": "user"},
    )
    assert listed.status_code == 200, listed.text
    assert [user["email"] for user in listed.json()] == ["new.member@example.com"]

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Candidate project"},
    ).json()

    disabled = client.post(
        f"/api/admin/users/{managed_user['id']}/disable",
        headers=auth(admin_token),
        json={"reason": "成员离职"},
    )
    assert disabled.status_code == 200, disabled.text
    disabled_user = disabled.json()
    assert disabled_user["is_active"] is False
    assert disabled_user["disabled_by"] == admin_user["id"]
    assert disabled_user["disabled_reason"] == "成员离职"
    assert disabled_user["disabled_at"]

    disabled_login = client.post(
        "/api/auth/login",
        json={"email": "new.member@example.com", "password": temporary_password},
    )
    assert disabled_login.status_code == 401

    stale_token_me = client.get("/api/me", headers=auth(managed_token))
    assert stale_token_me.status_code == 401

    candidates = client.get(
        f"/api/projects/{project['id']}/member-candidates",
        headers=auth(owner_token),
        params={"query": "新成员"},
    )
    assert candidates.status_code == 200, candidates.text
    assert candidates.json() == []

    add_disabled_member = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "new.member@example.com", "role": "member"},
    )
    assert add_disabled_member.status_code == 400

    disabled_list = client.get(
        "/api/admin/users",
        headers=auth(admin_token),
        params={"q": "new.member", "status": "disabled"},
    )
    assert disabled_list.status_code == 200, disabled_list.text
    assert [user["id"] for user in disabled_list.json()] == [managed_user["id"]]

    enabled = client.post(
        f"/api/admin/users/{managed_user['id']}/enable",
        headers=auth(admin_token),
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["is_active"] is True

    enabled_login = client.post(
        "/api/auth/login",
        json={"email": "new.member@example.com", "password": temporary_password},
    )
    assert enabled_login.status_code == 200, enabled_login.text

    reset = client.post(
        f"/api/admin/users/{managed_user['id']}/reset-password",
        headers=auth(admin_token),
    )
    assert reset.status_code == 200, reset.text
    reset_password = reset.json()["temporary_password"]
    assert len(reset_password) >= 8
    assert reset_password != temporary_password

    old_password_login = client.post(
        "/api/auth/login",
        json={"email": "new.member@example.com", "password": temporary_password},
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/api/auth/login",
        json={"email": "new.member@example.com", "password": reset_password},
    )
    assert new_password_login.status_code == 200, new_password_login.text

    updated = client.patch(
        f"/api/admin/users/{managed_user['id']}",
        headers=auth(admin_token),
        json={"name": "新管理员", "global_role": "admin"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "新管理员"
    assert updated.json()["global_role"] == "admin"

    admin_filtered = client.get(
        "/api/admin/users",
        headers=auth(admin_token),
        params={"q": "new.member", "global_role": "admin"},
    )
    assert admin_filtered.status_code == 200, admin_filtered.text
    assert [user["id"] for user in admin_filtered.json()] == [managed_user["id"]]


def test_admin_user_management_protects_administrators(tmp_path: Path) -> None:
    client = make_client(tmp_path, admin_emails=())
    settings = client.app.state.settings
    connection = connect(settings)
    try:
        create_user(
            connection,
            name="独立管理员",
            email="admin@example.com",
            password="password123",
            global_role="admin",
            admin_emails=settings.admin_emails,
        )
    finally:
        connection.close()

    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert login.status_code == 200, login.text
    admin_token = login.json()["access_token"]
    admin_user = login.json()["user"]

    self_disable = client.post(
        f"/api/admin/users/{admin_user['id']}/disable",
        headers=auth(admin_token),
        json={"reason": "误操作"},
    )
    assert self_disable.status_code == 400

    demote_last_admin = client.patch(
        f"/api/admin/users/{admin_user['id']}",
        headers=auth(admin_token),
        json={"global_role": "user"},
    )
    assert demote_last_admin.status_code == 400

    second_admin = client.post(
        "/api/admin/users",
        headers=auth(admin_token),
        json={
            "name": "第二管理员",
            "email": "second.admin@example.com",
            "global_role": "admin",
        },
    )
    assert second_admin.status_code == 200, second_admin.text

    demote_with_backup = client.patch(
        f"/api/admin/users/{admin_user['id']}",
        headers=auth(admin_token),
        json={"global_role": "user"},
    )
    assert demote_with_backup.status_code == 200, demote_with_backup.text
    assert demote_with_backup.json()["global_role"] == "user"


def test_configured_admin_user_cannot_be_downgraded(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")
    admin_user = client.get("/api/me", headers=auth(admin_token)).json()

    demote = client.patch(
        f"/api/admin/users/{admin_user['id']}",
        headers=auth(admin_token),
        json={"global_role": "user"},
    )

    assert demote.status_code == 400
    assert "Configured administrator" in demote.json()["detail"]


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


def test_project_public_proteins_are_project_bound_crud_records(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Tool proteins"},
    ).json()

    created = client.post(
        f"/api/projects/{project['id']}/public-proteins",
        headers=auth(owner_token),
        json={
            "name": "TEV protease",
            "sequence": "acdefg",
            "description": "cleavage control",
            "protein_type": "enzyme",
            "target": "purification",
        },
    )
    assert created.status_code == 200, created.text
    public_protein = created.json()
    assert public_protein["project_id"] == project["id"]
    assert public_protein["name"] == "TEV protease"
    assert public_protein["sequence"] == "ACDEFG"
    assert public_protein["description"] == "cleavage control"
    assert public_protein["protein_type"] == "enzyme"
    assert public_protein["target"] == "purification"
    assert public_protein["created_by_email"] == "owner@example.com"

    synthetic_proteins = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
    )
    assert synthetic_proteins.status_code == 200
    assert synthetic_proteins.json() == []

    outsider_list = client.get(
        f"/api/projects/{project['id']}/public-proteins",
        headers=auth(outsider_token),
    )
    assert outsider_list.status_code == 403

    added_member = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "member"},
    )
    assert added_member.status_code == 200, added_member.text

    member_list = client.get(
        f"/api/projects/{project['id']}/public-proteins",
        headers=auth(member_token),
    )
    assert member_list.status_code == 200, member_list.text
    assert [item["name"] for item in member_list.json()] == ["TEV protease"]

    updated = client.patch(
        f"/api/projects/{project['id']}/public-proteins/{public_protein['id']}",
        headers=auth(member_token),
        json={
            "name": "TEV protease v2",
            "sequence": "hiklmn",
            "description": "updated control",
            "protein_type": "tool enzyme",
            "target": "tag removal",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "TEV protease v2"
    assert updated.json()["sequence"] == "HIKLMN"
    assert updated.json()["target"] == "tag removal"

    deleted = client.delete(
        f"/api/projects/{project['id']}/public-proteins/{public_protein['id']}",
        headers=auth(member_token),
    )
    assert deleted.status_code == 204

    empty = client.get(
        f"/api/projects/{project['id']}/public-proteins",
        headers=auth(owner_token),
    )
    assert empty.status_code == 200
    assert empty.json() == []


def test_admin_sequence_search_includes_batched_and_public_sequences(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Sequence search project"},
    ).json()
    batched_protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={
            "name": "Batched binder",
            "sequence": "ACDEFGHIKL",
            "protein_type": "nanobody",
            "target": "CD19",
        },
    ).json()
    unbatched_protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "Draft binder", "sequence": "MNPQRSTVWY"},
    ).json()
    public_protein = client.post(
        f"/api/projects/{project['id']}/public-proteins",
        headers=auth(owner_token),
        json={
            "name": "Public control",
            "sequence": "GGGGACDEFGTT",
            "protein_type": "tool enzyme",
            "target": "purification",
        },
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Search batch", "protein_ids": [batched_protein["id"]]},
    )
    assert batch.status_code == 200, batch.text

    denied = client.get("/api/admin/sequences", headers=auth(owner_token))
    assert denied.status_code == 403

    listed = client.get("/api/admin/sequences", headers=auth(admin_token))
    assert listed.status_code == 200, listed.text
    results = listed.json()
    result_names = {item["name"] for item in results}
    assert "Batched binder" in result_names
    assert "Public control" in result_names
    assert "Draft binder" not in result_names

    batched_result = next(
        item for item in results if item["name"] == batched_protein["name"]
    )
    assert batched_result["source_type"] == "batch_protein"
    assert batched_result["protein_id"] == batched_protein["id"]
    assert batched_result["public_protein_id"] is None
    assert batched_result["project_name"] == "Sequence search project"
    assert batched_result["sequence_length"] == len(batched_protein["sequence"])
    assert batched_result["batch_count"] == 1
    assert batched_result["detail_path"] == f"/proteins/{batched_protein['id']}"

    public_result = next(item for item in results if item["name"] == "Public control")
    assert public_result["source_type"] == "public_protein"
    assert public_result["protein_id"] is None
    assert public_result["public_protein_id"] == public_protein["id"]
    assert public_result["detail_path"] == f"/public-proteins/{public_protein['id']}"

    searched = client.get(
        "/api/admin/sequences",
        headers=auth(admin_token),
        params={"q": " c d e f "},
    )
    assert searched.status_code == 200, searched.text
    assert {item["name"] for item in searched.json()} == {
        "Batched binder",
        "Public control",
    }

    similarity_searched = client.get(
        "/api/admin/sequences",
        headers=auth(admin_token),
        params={
            "q": "ACDEFGHIKM",
            "mode": "similarity",
            "similarity_threshold": 0.9,
        },
    )
    assert similarity_searched.status_code == 200, similarity_searched.text
    similarity_results = similarity_searched.json()
    assert [item["name"] for item in similarity_results] == ["Batched binder"]
    assert similarity_results[0]["identity"] == 0.9
    assert similarity_results[0]["alignment_length"] == 10
    assert similarity_results[0]["match_type"] == "high_similarity"

    public_detail = client.get(
        f"/api/public-proteins/{public_protein['id']}",
        headers=auth(owner_token),
    )
    assert public_detail.status_code == 200, public_detail.text
    assert public_detail.json()["public_protein"]["project_name"] == (
        "Sequence search project"
    )

    outsider_detail = client.get(
        f"/api/public-proteins/{public_protein['id']}",
        headers=auth(outsider_token),
    )
    assert outsider_detail.status_code == 403

    admin_detail = client.get(
        f"/api/public-proteins/{public_protein['id']}",
        headers=auth(admin_token),
    )
    assert admin_detail.status_code == 200, admin_detail.text

    unbatched_detail = client.get(
        f"/api/proteins/{unbatched_protein['id']}",
        headers=auth(admin_token),
    )
    assert unbatched_detail.status_code == 200


def test_project_list_includes_owner_and_member_summary(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com", "张三")
    member_token = register(client, "member@example.com", "李四")
    register(client, "assay@example.com", "王五")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Member summary"},
    ).json()
    for email in ("member@example.com", "assay@example.com"):
        added = client.post(
            f"/api/projects/{project['id']}/members",
            headers=auth(owner_token),
            json={"email": email, "role": "member"},
        )
        assert added.status_code == 200, added.text

    listed = client.get("/api/projects", headers=auth(owner_token))
    assert listed.status_code == 200, listed.text
    listed_project = next(item for item in listed.json() if item["id"] == project["id"])
    assert listed_project["owner_name"] == "张三"
    assert listed_project["owner_email"] == "owner@example.com"
    assert listed_project["member_count"] == 2
    assert {
        (member["name"], member["email"])
        for member in listed_project["members"]
    } == {
        ("王五", "assay@example.com"),
        ("李四", "member@example.com"),
    }

    member_listed = client.get("/api/projects", headers=auth(member_token))
    assert member_listed.status_code == 200, member_listed.text
    assert member_listed.json()[0]["member_count"] == 2


def test_project_status_filters_and_admin_updates(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")

    active_project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Active project"},
    ).json()
    archived_project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Archived project"},
    ).json()
    trash_project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Trash project"},
    ).json()

    assert active_project["status"] == "active"

    for project in (active_project, archived_project, trash_project):
        added = client.post(
            f"/api/projects/{project['id']}/members",
            headers=auth(owner_token),
            json={"email": "member@example.com", "role": "member"},
        )
        assert added.status_code == 200, added.text

    trash_protein = client.post(
        f"/api/projects/{trash_project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "Hidden protein", "sequence": "ACDEFG"},
    ).json()

    owner_update = client.patch(
        f"/api/projects/{archived_project['id']}/status",
        headers=auth(owner_token),
        json={"status": "archived"},
    )
    assert owner_update.status_code == 403

    invalid_update = client.patch(
        f"/api/projects/{archived_project['id']}/status",
        headers=auth(admin_token),
        json={"status": "paused"},
    )
    assert invalid_update.status_code == 400
    assert invalid_update.json()["detail"] == (
        "Project status must be active, archived, or trash"
    )

    missing_update = client.patch(
        "/api/projects/999999/status",
        headers=auth(admin_token),
        json={"status": "trash"},
    )
    assert missing_update.status_code == 404

    archived_update = client.patch(
        f"/api/projects/{archived_project['id']}/status",
        headers=auth(admin_token),
        json={"status": "archived"},
    )
    assert archived_update.status_code == 200, archived_update.text
    assert archived_update.json()["status"] == "archived"

    trash_update = client.patch(
        f"/api/projects/{trash_project['id']}/status",
        headers=auth(admin_token),
        json={"status": "trash"},
    )
    assert trash_update.status_code == 200, trash_update.text
    assert trash_update.json()["status"] == "trash"

    owner_active = client.get("/api/projects?status=active", headers=auth(owner_token))
    assert owner_active.status_code == 200, owner_active.text
    assert {project["id"] for project in owner_active.json()} == {active_project["id"]}

    owner_archived = client.get(
        "/api/projects?status=archived",
        headers=auth(owner_token),
    )
    assert owner_archived.status_code == 200, owner_archived.text
    assert {project["id"] for project in owner_archived.json()} == {
        archived_project["id"]
    }

    member_archived = client.get(
        "/api/projects?status=archived",
        headers=auth(member_token),
    )
    assert member_archived.status_code == 200, member_archived.text
    assert {project["id"] for project in member_archived.json()} == {
        archived_project["id"]
    }

    owner_trash = client.get("/api/projects?status=trash", headers=auth(owner_token))
    assert owner_trash.status_code == 403

    admin_trash = client.get("/api/projects?status=trash", headers=auth(admin_token))
    assert admin_trash.status_code == 200, admin_trash.text
    assert {project["id"] for project in admin_trash.json()} == {trash_project["id"]}

    archived_detail = client.get(
        f"/api/projects/{archived_project['id']}",
        headers=auth(member_token),
    )
    assert archived_detail.status_code == 200, archived_detail.text
    assert archived_detail.json()["project"]["status"] == "archived"

    trash_detail = client.get(
        f"/api/projects/{trash_project['id']}",
        headers=auth(owner_token),
    )
    assert trash_detail.status_code == 403

    trash_proteins = client.get(
        f"/api/projects/{trash_project['id']}/proteins",
        headers=auth(owner_token),
    )
    assert trash_proteins.status_code == 403

    admin_trash_protein = client.get(
        f"/api/proteins/{trash_protein['id']}",
        headers=auth(admin_token),
    )
    assert admin_trash_protein.status_code == 200, admin_trash_protein.text


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
    assert protein["manual_rating"] == "unrated"
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


def test_protein_sequence_check_reports_duplicates_and_high_similarity(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Sequence check"},
    ).json()
    existing = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "existing", "sequence": "ACDEFGHIKL"},
    )
    assert existing.status_code == 200, existing.text

    response = client.post(
        f"/api/projects/{project['id']}/proteins/sequence-check",
        headers=auth(owner_token),
        json={
            "items": [
                {"name": "exact", "sequence": "acdefg hikl"},
                {"name": "similar", "sequence": "ACDEFGHIKM"},
                {"name": "incoming-a", "sequence": "MNPQRSTVWY"},
                {"name": "incoming-b", "sequence": "MNPQRSTVWY"},
            ]
        },
    )

    assert response.status_code == 200, response.text
    check = response.json()
    assert check["has_blocking_duplicates"] is False
    assert check["has_warnings"] is True
    assert check["similarity_threshold"] == 0.9
    items = {item["name"]: item for item in check["items"]}
    assert items["exact"]["sequence"] == "ACDEFGHIKL"
    assert items["exact"]["has_duplicate"] is True
    assert items["exact"]["has_high_similarity"] is True
    assert {
        (match["scope"], match["match_type"], match["protein_name"])
        for match in items["exact"]["matches"]
    } >= {("existing", "duplicate", "existing")}
    assert items["similar"]["has_high_similarity"] is True
    assert any(
        match["scope"] == "existing"
        and match["match_type"] == "high_similarity"
        and match["identity"] == 0.9
        for match in items["similar"]["matches"]
    )
    assert any(
        match["scope"] == "incoming" and match["match_type"] == "duplicate"
        for match in items["incoming-b"]["matches"]
    )
    assert any(
        match["scope"] == "incoming" and match["match_type"] == "duplicate"
        for match in items["incoming-a"]["matches"]
    )

    empty = client.post(
        f"/api/projects/{project['id']}/proteins/sequence-check",
        headers=auth(owner_token),
        json={"items": []},
    )
    assert empty.status_code == 400
    assert "At least one protein sequence" in empty.json()["detail"]


def test_create_protein_allows_duplicates_and_tags_high_similarity(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Sequence guarded"},
    ).json()
    created = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "base", "sequence": "ACDEFGHIKL"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["manual_rating"] == "unrated"
    assert created.json()["sequence_similarity_status"] == ""
    assert created.json()["sequence_similarity_matches"] == []

    duplicate = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "duplicate", "sequence": "ACDEFGHIKL"},
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_payload = duplicate.json()
    assert duplicate_payload["manual_rating"] == "unrated"
    assert duplicate_payload["sequence_similarity_status"] == "high_similarity"
    assert any(
        match["scope"] == "existing"
        and match["match_type"] == "duplicate"
        and match["protein_name"] == "base"
        for match in duplicate_payload["sequence_similarity_matches"]
    )

    similar = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "similar", "sequence": "ACDEFGHIKM"},
    )
    assert similar.status_code == 200, similar.text
    similar_payload = similar.json()
    assert similar_payload["manual_rating"] == "unrated"
    assert similar_payload["sequence_similarity_status"] == "high_similarity"
    assert any(
        match["scope"] == "existing"
        and match["match_type"] == "high_similarity"
        and match["protein_name"] == "base"
        for match in similar_payload["sequence_similarity_matches"]
    )

    confirmed = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={
            "name": "confirmed-similar",
            "sequence": "ACDEFGHIKM",
            "allow_high_similarity": True,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["sequence"] == "ACDEFGHIKM"
    assert confirmed.json()["manual_rating"] == "unrated"
    assert confirmed.json()["sequence_similarity_status"] == "high_similarity"


def test_protein_manual_rating_can_be_updated(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Manual rating project"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "rated protein", "sequence": "ACDEFG"},
    ).json()
    assert protein["manual_rating"] == "unrated"

    outsider_update = client.patch(
        f"/api/proteins/{protein['id']}/manual-rating",
        headers=auth(outsider_token),
        json={"manual_rating": "rare"},
    )
    assert outsider_update.status_code == 403

    updated = client.patch(
        f"/api/proteins/{protein['id']}/manual-rating",
        headers=auth(owner_token),
        json={"manual_rating": "legendary"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["manual_rating"] == "legendary"
    assert updated.json()["sequence"] == "ACDEFG"

    project_proteins = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
    )
    assert project_proteins.status_code == 200
    assert project_proteins.json()[0]["manual_rating"] == "legendary"

    protein_detail = client.get(
        f"/api/proteins/{protein['id']}",
        headers=auth(owner_token),
    )
    assert protein_detail.status_code == 200
    assert protein_detail.json()["protein"]["manual_rating"] == "legendary"

    cleared = client.patch(
        f"/api/proteins/{protein['id']}/manual-rating",
        headers=auth(owner_token),
        json={"manual_rating": "unrated"},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["manual_rating"] == "unrated"

    invalid = client.patch(
        f"/api/proteins/{protein['id']}/manual-rating",
        headers=auth(owner_token),
        json={"manual_rating": "mythic"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == (
        "Manual rating must be unrated, normal, rare, epic, or legendary"
    )


def test_project_proteins_filter_and_sort_by_effective_date_and_rating(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Protein filters"},
    ).json()
    plain = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "plain-upload", "sequence": "ACDEFG"},
    ).json()
    pdb = b"""HEADER    TEST                            15-JAN-21   1ABC
SEQRES   1 A    3  MET GLY LYS
"""
    pdb_created = client.post(
        f"/api/projects/{project['id']}/proteins/with-structure",
        headers=auth(owner_token),
        data={
            "name": "pdb-deposit",
            "sequence": "MGK",
            "protein_type": "TCR",
        },
        files={"file": ("pdb-deposit.pdb", pdb, "chemical/x-pdb")},
    )
    assert pdb_created.status_code == 200, pdb_created.text
    assert pdb_created.json()["structure_deposit_date"] == "2021-01-15"

    mmcif = b"""data_target
_pdbx_database_status.recvd_initial_deposition_date 2020-03-04
_entity_poly.entity_id 1
_entity_poly.type 'polypeptide(L)'
_entity_poly.pdbx_strand_id A
_entity_poly.pdbx_seq_one_letter_code_can
;ACD
EFG
;
"""
    cif_created = client.post(
        f"/api/projects/{project['id']}/proteins/with-structure",
        headers=auth(owner_token),
        data={
            "name": "cif-deposit",
            "sequence": "ACDEFG",
            "protein_type": "TCR",
        },
        files={"file": ("cif-deposit.cif", mmcif, "chemical/x-mmcif")},
    )
    assert cif_created.status_code == 200, cif_created.text
    assert cif_created.json()["structure_deposit_date"] == "2020-03-04"

    with sqlite3.connect(tmp_path / "proteinhub.sqlite3") as connection:
        connection.execute(
            """
            UPDATE proteins
            SET created_at = '2026-02-01 00:00:00',
                updated_at = '2026-02-01 00:00:00'
            WHERE id = ?
            """,
            (plain["id"],),
        )
        connection.commit()

    ratings = {
        plain["id"]: "normal",
        pdb_created.json()["id"]: "legendary",
        cif_created.json()["id"]: "rare",
    }
    for protein_id, rating in ratings.items():
        response = client.patch(
            f"/api/proteins/{protein_id}/manual-rating",
            headers=auth(owner_token),
            json={"manual_rating": rating},
        )
        assert response.status_code == 200, response.text

    effective_desc = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        params={"sort": "time_desc"},
    )
    assert effective_desc.status_code == 200, effective_desc.text
    assert [protein["name"] for protein in effective_desc.json()] == [
        "plain-upload",
        "pdb-deposit",
        "cif-deposit",
    ]
    proteins_by_name = {protein["name"]: protein for protein in effective_desc.json()}
    assert proteins_by_name["plain-upload"]["effective_date"] == "2026-02-01"
    assert proteins_by_name["plain-upload"]["effective_date_source"] == "created_at"
    assert proteins_by_name["pdb-deposit"]["effective_date"] == "2021-01-15"
    assert proteins_by_name["pdb-deposit"]["effective_date_source"] == "pdb_deposit"

    rating_desc = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        params={"sort": "rating_desc"},
    )
    assert rating_desc.status_code == 200, rating_desc.text
    assert [protein["name"] for protein in rating_desc.json()] == [
        "pdb-deposit",
        "cif-deposit",
        "plain-upload",
    ]

    rating_filtered = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        params=[
            ("ratings", "rare"),
            ("ratings", "legendary"),
            ("sort", "rating_desc"),
        ],
    )
    assert rating_filtered.status_code == 200, rating_filtered.text
    assert [protein["name"] for protein in rating_filtered.json()] == [
        "pdb-deposit",
        "cif-deposit",
    ]

    date_filtered = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        params={
            "date_from": "2021-01-01",
            "date_to": "2021-12-31",
            "sort": "time_asc",
        },
    )
    assert date_filtered.status_code == 200, date_filtered.text
    assert [protein["name"] for protein in date_filtered.json()] == ["pdb-deposit"]

    invalid_range = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        params={"date_from": "2026-02-02", "date_to": "2026-02-01"},
    )
    assert invalid_range.status_code == 400
    assert invalid_range.json()["detail"] == "Start date must be on or before end date"


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
    score_csv = (
        b"pdb_name,ddg,sap_score,norm_score\n"
        b"binder-a,-1.0,37.3919,99\n"
        b"binder-b,-2.0,12.25,88\n"
        b"unrelated,-3.0,1.0,77\n"
    )

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
            ("score_file", ("scores.csv", score_csv, "text/csv")),
        ],
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    proteins = payload["proteins"]
    assert payload["score_import"] == {
        "matched_count": 2,
        "skipped_count": 1,
        "skipped_names": ["unrelated"],
    }
    assert [protein["name"] for protein in proteins] == ["binder-a", "binder-b"]
    assert [protein["sequence"] for protein in proteins] == ["MGK", "ACDEFG"]
    assert {protein["protein_type"] for protein in proteins} == {"TCR"}
    assert {protein["target"] for protein in proteins} == {"MAGE-A4"}
    assert {protein["description"] for protein in proteins} == {"folder import"}
    assert {protein["manual_rating"] for protein in proteins} == {"unrated"}
    assert [protein["score_details"] for protein in proteins] == [
        {"ddg": "-1.0", "sap_score": "37.3919", "norm_score": "99"},
        {"ddg": "-2.0", "sap_score": "12.25", "norm_score": "88"},
    ]
    assert "score" not in proteins[0]
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

    standalone_score_import = client.post(
        f"/api/projects/{project['id']}/proteins/score-table",
        headers=auth(owner_token),
        files=[("file", ("scores.csv", score_csv, "text/csv"))],
    )
    assert standalone_score_import.status_code == 404

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

    bad_score_table = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(owner_token),
        data={"protein_type": "TCR", "target": "bad score"},
        files=[
            ("files", ("folder/binder-c.pdb", pdb, "chemical/x-pdb")),
            ("score_file", ("scores.csv", b"name,ddg\nbinder-c,-1\n", "text/csv")),
        ],
    )
    assert bad_score_table.status_code == 400
    assert "pdb_name" in bad_score_table.json()["detail"]

    project_proteins = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
    )
    assert project_proteins.status_code == 200
    assert len(project_proteins.json()) == 2
    assert {
        protein["name"]: protein["score_details"]
        for protein in project_proteins.json()
    } == {
        "binder-a": {"ddg": "-1.0", "sap_score": "37.3919", "norm_score": "99"},
        "binder-b": {"ddg": "-2.0", "sap_score": "12.25", "norm_score": "88"},
    }

    protein_detail = client.get(
        f"/api/proteins/{proteins[0]['id']}",
        headers=auth(owner_token),
    )
    assert protein_detail.status_code == 200
    assert protein_detail.json()["protein"]["score_details"] == {
        "ddg": "-1.0",
        "sap_score": "37.3919",
        "norm_score": "99",
    }

    outsider_import = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(outsider_token),
        data={"protein_type": "TCR"},
        files=[("files", ("folder/outsider.pdb", pdb, "chemical/x-pdb"))],
    )
    assert outsider_import.status_code == 403


def test_import_proteins_from_structures_tags_incoming_duplicate_sequences(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Duplicate structure import"},
    ).json()
    pdb = b"HEADER    TEST\nSEQRES   1 A    3  MET GLY LYS\n"

    imported = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(owner_token),
        data={"protein_type": "TCR"},
        files=[
            ("files", ("folder/binder-a.pdb", pdb, "chemical/x-pdb")),
            ("files", ("folder/binder-b.pdb", pdb, "chemical/x-pdb")),
        ],
    )

    assert imported.status_code == 200, imported.text
    payload = imported.json()
    proteins = payload["proteins"]
    assert payload["score_import"] == {
        "matched_count": 0,
        "skipped_count": 0,
        "skipped_names": [],
    }
    assert [protein["name"] for protein in proteins] == ["binder-a", "binder-b"]
    assert {protein["manual_rating"] for protein in proteins} == {"unrated"}
    assert {
        protein["name"]: protein["sequence_similarity_status"]
        for protein in proteins
    } == {
        "binder-a": "high_similarity",
        "binder-b": "high_similarity",
    }
    assert all(
        any(
            match["scope"] == "incoming"
            and match["match_type"] == "duplicate"
            for match in protein["sequence_similarity_matches"]
        )
        for protein in proteins
    )
    project_proteins = client.get(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
    )
    assert project_proteins.status_code == 200
    assert len(project_proteins.json()) == 2


def test_batch_creation_includes_score_density_plots(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Density batch"},
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
    score_csv = (
        b"pdb_name,plddt_binder,binder_aligned_rmsd,ddg\n"
        b"binder-a,91.2,1.3,-2.1\n"
        b"binder-b,87.4,0.8,-1.8\n"
    )

    imported = client.post(
        f"/api/projects/{project['id']}/proteins/import-structures",
        headers=auth(owner_token),
        data={
            "protein_type": "TCR",
            "target": "MAGE-A4",
            "description": "density batch",
        },
        files=[
            ("files", ("folder/binder-a.pdb", pdb, "chemical/x-pdb")),
            ("files", ("folder/binder-b.cif", mmcif, "chemical/x-mmcif")),
            ("score_file", ("scores.csv", score_csv, "text/csv")),
        ],
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    proteins = payload["proteins"]
    assert payload["score_import"] == {
        "matched_count": 2,
        "skipped_count": 0,
        "skipped_names": [],
    }

    created = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Density batch",
            "protein_ids": [protein["id"] for protein in proteins],
        },
    )
    assert created.status_code == 200, created.text
    batch_payload = created.json()
    plots = batch_payload["score_density_plots"]
    assert [plot["metric"] for plot in plots] == [
        "plddt_binder",
        "binder_aligned_rmsd",
        "ddg",
    ]
    assert [plot["sample_count"] for plot in plots] == [2, 2, 2]
    assert "Distribution of pLDDT binder" in plots[0]["svg"]
    assert plots[0]["svg"].lstrip().startswith("<svg")


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


def test_project_delete_route_is_not_available(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Kept project"},
    ).json()

    delete_response = client.delete(
        f"/api/projects/{project['id']}",
        headers=auth(owner_token),
    )
    assert delete_response.status_code == 405

    kept_project = client.get(
        f"/api/projects/{project['id']}",
        headers=auth(owner_token),
    )
    assert kept_project.status_code == 200, kept_project.text
    assert kept_project.json()["project"]["name"] == "Kept project"


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
        params={"query": "合"},
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


def test_owner_can_update_project_member_role(tmp_path: Path) -> None:
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
        json={"role": "member"},
    )
    assert sole_owner_demote.status_code == 400

    added = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "member"},
    )
    assert added.status_code == 200, added.text
    assert "discipline" not in added.json()
    member_id = added.json()["id"]

    member_cannot_update = client.patch(
        f"/api/projects/{project['id']}/members/{member_id}",
        headers=auth(member_token),
        json={"role": "owner"},
    )
    assert member_cannot_update.status_code == 403

    promote_member = client.patch(
        f"/api/projects/{project['id']}/members/{member_id}",
        headers=auth(owner_token),
        json={"role": "owner"},
    )
    assert promote_member.status_code == 400
    assert promote_member.json()["detail"] == "Projects have exactly one owner"

    updated = client.patch(
        f"/api/projects/{project['id']}/members/{member_id}",
        headers=auth(owner_token),
        json={"role": "member"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "member"
    assert "discipline" not in updated.json()

    refreshed_members = client.get(
        f"/api/projects/{project['id']}",
        headers=auth(owner_token),
    ).json()["members"]
    design_member = next(
        member for member in refreshed_members if member["email"] == "member@example.com"
    )
    assert design_member["role"] == "member"
    assert "discipline" not in design_member


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
    assert set(payload) == {"protein", "artifacts", "batch_results", "access_role"}
    assert payload["access_role"] == "owner"
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
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")
    admin_user = client.get("/api/me", headers=auth(admin_token)).json()

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
    assert batch["ordered_at"] == ""

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

    owner_update = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(owner_token),
        json={"order_status": "partially_received"},
    )
    assert owner_update.status_code == 403

    member_update = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(member_token),
        json={"order_status": "ordered"},
    )
    assert member_update.status_code == 403

    ordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text
    assert ordered.json()["batch"]["order_status"] == "ordered"
    ordered_at = ordered.json()["batch"]["ordered_at"]
    assert ordered_at

    backwards = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "not_ordered"},
    )
    assert backwards.status_code == 200, backwards.text
    assert backwards.json()["batch"]["order_status"] == "not_ordered"

    reordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert reordered.status_code == 200, reordered.text

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
        headers=auth(admin_token),
        json={"order_status": "fully_received"},
    )
    assert fully_received.status_code == 200, fully_received.text
    assert fully_received.json()["batch"]["order_status"] == "fully_received"
    assert fully_received.json()["batch"]["ordered_at"] == ordered_at
    assert all(well["received_at"] for well in fully_received.json()["wells"])
    assert all(
        well["received_by"] == admin_user["id"]
        for well in fully_received.json()["wells"]
    )

    back_from_fully_received = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "partially_received"},
    )
    assert back_from_fully_received.status_code == 200, back_from_fully_received.text
    assert (
        back_from_fully_received.json()["batch"]["order_status"]
        == "partially_received"
    )


def test_batch_order_status_can_move_through_partial_receipt(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")
    admin_user = client.get("/api/me", headers=auth(admin_token)).json()

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
    added_member = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(owner_token),
        json={"email": "member@example.com", "role": "member"},
    )
    assert added_member.status_code == 200, added_member.text
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Partial receipt batch", "protein_ids": [protein["id"]]},
    ).json()["batch"]
    assert batch["receipt_note"] == ""
    assert batch["receipt_updated_by"] is None
    assert batch["receipt_updated_at"] == ""

    ordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text

    partial = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "partially_received",
            "receipt_note": "已收到 A1，剩余样品供应商预计下周补发。",
        },
    )
    assert partial.status_code == 200, partial.text
    partial_batch = partial.json()["batch"]
    assert partial_batch["order_status"] == "partially_received"
    assert partial_batch["receipt_note"] == "已收到 A1，剩余样品供应商预计下周补发。"
    assert partial_batch["receipt_updated_by"] == admin_user["id"]
    assert partial_batch["receipt_updated_by_name"] == "陈若澜"
    assert partial_batch["receipt_updated_at"]

    member_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(member_token),
    )
    assert member_detail.status_code == 200, member_detail.text
    assert (
        member_detail.json()["batch"]["receipt_note"]
        == "已收到 A1，剩余样品供应商预计下周补发。"
    )

    member_receipt_update = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(member_token),
        json={"order_status": "partially_received", "receipt_note": "member edit"},
    )
    assert member_receipt_update.status_code == 403

    fully_received = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "fully_received"},
    )
    assert fully_received.status_code == 200, fully_received.text
    assert fully_received.json()["batch"]["order_status"] == "fully_received"


def test_batch_partial_receipt_tracks_received_wells(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")
    admin_user = client.get("/api/me", headers=auth(admin_token)).json()

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Detailed receipt plate"},
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
            "name": "Detailed receipt batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    )
    assert created.status_code == 200, created.text
    batch_payload = created.json()
    batch = batch_payload["batch"]
    wells = batch_payload["wells"]
    assert all(well["received_at"] == "" for well in wells)
    assert all(well["received_by"] is None for well in wells)

    ordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text

    partial = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "ordered",
            "receipt_note": "A01 已收货，A02 待补发。",
            "received_well_ids": [wells[0]["id"]],
        },
    )
    assert partial.status_code == 200, partial.text
    partial_payload = partial.json()
    assert partial_payload["batch"]["order_status"] == "partially_received"
    assert partial_payload["batch"]["receipt_note"] == "A01 已收货，A02 待补发。"
    assert partial_payload["batch"]["receipt_updated_by"] == admin_user["id"]
    received_by_id = {
        well["id"]: well["received_by"] for well in partial_payload["wells"]
    }
    received_at_by_id = {
        well["id"]: well["received_at"] for well in partial_payload["wells"]
    }
    assert received_by_id[wells[0]["id"]] == admin_user["id"]
    assert received_at_by_id[wells[0]["id"]]
    assert received_by_id[wells[1]["id"]] is None
    assert received_at_by_id[wells[1]["id"]] == ""

    listed = client.get(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["received_well_count"] == 1

    member_receipt_update = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(member_token),
        json={
            "order_status": "partially_received",
            "received_well_ids": [wells[0]["id"], wells[1]["id"]],
        },
    )
    assert member_receipt_update.status_code == 403

    other_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Other batch", "protein_ids": [protein_a["id"]]},
    ).json()
    invalid_well = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "partially_received",
            "received_well_ids": [other_batch["wells"][0]["id"]],
        },
    )
    assert invalid_well.status_code == 400

    fully_received = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "partially_received",
            "received_well_ids": [well["id"] for well in wells],
        },
    )
    assert fully_received.status_code == 200, fully_received.text
    full_payload = fully_received.json()
    assert full_payload["batch"]["order_status"] == "fully_received"
    assert all(well["received_at"] for well in full_payload["wells"])
    assert all(well["received_by"] == admin_user["id"] for well in full_payload["wells"])


def test_admin_can_delete_batch_and_related_rows(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    member_token = register(client, "member@example.com")
    outsider_token = register(client, "outsider@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Batch delete project"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder", "sequence": "ACDEFG"},
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
        json={"name": "Deletable batch", "protein_ids": [protein["id"]]},
    )
    assert created.status_code == 200, created.text
    batch_payload = created.json()
    batch = batch_payload["batch"]
    well = batch_payload["wells"][0]

    experiment = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "FPLC", "name": "Delete cascade FPLC"},
    )
    assert experiment.status_code == 200, experiment.text
    experiment_id = experiment.json()["experiment"]["id"]
    result = client.patch(
        f"/api/experiments/{experiment_id}/wells/{well['id']}/result",
        headers=auth(member_token),
        json={"result_value": "ready", "result_note": "delete check"},
    )
    assert result.status_code == 200, result.text

    owner_delete = client.delete(
        f"/api/batches/{batch['id']}",
        headers=auth(owner_token),
    )
    assert owner_delete.status_code == 403
    member_delete = client.delete(
        f"/api/batches/{batch['id']}",
        headers=auth(member_token),
    )
    assert member_delete.status_code == 403
    outsider_delete = client.delete(
        f"/api/batches/{batch['id']}",
        headers=auth(outsider_token),
    )
    assert outsider_delete.status_code == 403

    admin_delete = client.delete(
        f"/api/batches/{batch['id']}",
        headers=auth(admin_token),
    )
    assert admin_delete.status_code == 204

    deleted_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(admin_token),
    )
    assert deleted_detail.status_code == 404
    listed = client.get(
        f"/api/projects/{project['id']}/batches",
        headers=auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert all(item["id"] != batch["id"] for item in listed.json())

    settings = client.app.state.settings
    connection = connect(settings)
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) AS count FROM batches WHERE id = ?",
                (batch["id"],),
            ).fetchone()["count"]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) AS count FROM batch_wells WHERE batch_id = ?",
                (batch["id"],),
            ).fetchone()["count"]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) AS count FROM batch_experiments WHERE batch_id = ?",
                (batch["id"],),
            ).fetchone()["count"]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) AS count FROM experiment_well_results WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()["count"]
            == 0
        )
    finally:
        connection.close()

    missing_delete = client.delete(
        f"/api/batches/{batch['id']}",
        headers=auth(admin_token),
    )
    assert missing_delete.status_code == 404


def test_order_monitor_lists_accessible_ordered_batches_by_week(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Order monitor project"},
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
    ordered_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Ordered batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    ).json()["batch"]
    not_ordered_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Draft batch", "protein_ids": [protein_a["id"]]},
    ).json()["batch"]
    partially_received_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Partially received batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    ).json()["batch"]
    fully_received_batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Fully received batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    ).json()["batch"]

    ordered = client.patch(
        f"/api/batches/{ordered_batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text

    partial_ordered = client.patch(
        f"/api/batches/{partially_received_batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert partial_ordered.status_code == 200, partial_ordered.text
    partial_received = client.patch(
        f"/api/batches/{partially_received_batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "partially_received"},
    )
    assert partial_received.status_code == 200, partial_received.text

    full_ordered = client.patch(
        f"/api/batches/{fully_received_batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert full_ordered.status_code == 200, full_ordered.text
    full_received = client.patch(
        f"/api/batches/{fully_received_batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "fully_received"},
    )
    assert full_received.status_code == 200, full_received.text

    artifact = client.post(
        f"/api/proteins/{protein_a['id']}/artifacts",
        headers=auth(owner_token),
        files={"file": ("monitor.txt", b"ORDER", "text/plain")},
    )
    assert artifact.status_code == 200, artifact.text

    owner_monitor = client.get("/api/order-monitor", headers=auth(owner_token))
    assert owner_monitor.status_code == 403

    monitor = client.get("/api/order-monitor", headers=auth(admin_token))
    assert monitor.status_code == 200, monitor.text
    payload = monitor.json()
    assert len(payload["weekly_orders"]) == 8
    assert payload["summary"]["total_ordered_batches"] == 3
    assert payload["summary"]["total_ordered_proteins"] == 6
    assert payload["summary"]["last_ordered_at"] == payload["batches"][0]["ordered_at"]
    assert payload["summary"]["cadence_target_days"] == 14
    assert {batch["id"] for batch in payload["batches"]} == {
        ordered_batch["id"],
        partially_received_batch["id"],
        fully_received_batch["id"],
    }
    assert all(
        batch["project_name"] == "Order monitor project" for batch in payload["batches"]
    )
    assert all(batch["well_count"] == 2 for batch in payload["batches"])
    assert not_ordered_batch["id"] not in [
        batch["id"] for batch in payload["batches"]
    ]
    ordered_week = next(
        week
        for week in payload["weekly_orders"]
        if ordered_batch["id"] in week["batch_ids"]
    )
    assert set(ordered_week["batch_ids"]) == {
        ordered_batch["id"],
        partially_received_batch["id"],
        fully_received_batch["id"],
    }
    assert ordered_week["order_count"] == 3
    assert ordered_week["ordered_count"] == 1
    assert ordered_week["partially_received_count"] == 1
    assert ordered_week["fully_received_count"] == 1
    assert ordered_week["protein_count"] == 6

    historical_monitor = client.get(
        "/api/order-monitor?start_date=2000-01-01&end_date=2000-01-31",
        headers=auth(admin_token),
    )
    assert historical_monitor.status_code == 200, historical_monitor.text
    historical_payload = historical_monitor.json()
    assert historical_payload["range_start"] == "1999-12-27"
    assert historical_payload["range_end"] == "2000-01-31"
    assert all(week["order_count"] == 0 for week in historical_payload["weekly_orders"])
    assert all(
        week["ordered_count"] == 0
        and week["partially_received_count"] == 0
        and week["fully_received_count"] == 0
        for week in historical_payload["weekly_orders"]
    )
    assert all(not week["batch_ids"] for week in historical_payload["weekly_orders"])

    invalid_range = client.get(
        "/api/order-monitor?start_date=2026-08-20&end_date=2026-08-01",
        headers=auth(admin_token),
    )
    assert invalid_range.status_code == 400
    assert invalid_range.json()["detail"] == "Start date must be on or before end date"

    outsider_monitor = client.get("/api/order-monitor", headers=auth(outsider_token))
    assert outsider_monitor.status_code == 403

    admin_projects = client.get("/api/projects", headers=auth(admin_token))
    assert admin_projects.status_code == 200, admin_projects.text
    assert any(
        listed_project["id"] == project["id"] and listed_project["role"] == "owner"
        for listed_project in admin_projects.json()
    )

    admin_project = client.get(
        f"/api/projects/{project['id']}",
        headers=auth(admin_token),
    )
    assert admin_project.status_code == 200, admin_project.text
    assert admin_project.json()["project"]["role"] == "owner"

    admin_batches = client.get(
        f"/api/projects/{project['id']}/batches",
        headers=auth(admin_token),
    )
    assert admin_batches.status_code == 200, admin_batches.text
    assert {batch["id"] for batch in admin_batches.json()} == {
        ordered_batch["id"],
        partially_received_batch["id"],
        fully_received_batch["id"],
        not_ordered_batch["id"],
    }

    admin_batch_detail = client.get(
        f"/api/batches/{ordered_batch['id']}",
        headers=auth(admin_token),
    )
    assert admin_batch_detail.status_code == 200, admin_batch_detail.text
    assert admin_batch_detail.json()["access_role"] == "owner"

    admin_status_update = client.patch(
        f"/api/batches/{ordered_batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "fully_received"},
    )
    assert admin_status_update.status_code == 200, admin_status_update.text
    assert admin_status_update.json()["batch"]["order_status"] == "fully_received"

    admin_add_member = client.post(
        f"/api/projects/{project['id']}/members",
        headers=auth(admin_token),
        json={"email": "outsider@example.com", "role": "member"},
    )
    assert admin_add_member.status_code == 200, admin_add_member.text
    assert admin_add_member.json()["role"] == "member"

    admin_protein_detail = client.get(
        f"/api/proteins/{protein_a['id']}",
        headers=auth(admin_token),
    )
    assert admin_protein_detail.status_code == 200, admin_protein_detail.text
    assert admin_protein_detail.json()["access_role"] == "owner"

    admin_artifact_download = client.get(
        f"/api/artifacts/{artifact.json()['id']}/download",
        headers=auth(admin_token),
    )
    assert admin_artifact_download.status_code == 200, admin_artifact_download.text
    assert admin_artifact_download.content == b"ORDER"

    admin_artifact_delete = client.delete(
        f"/api/artifacts/{artifact.json()['id']}",
        headers=auth(admin_token),
    )
    assert admin_artifact_delete.status_code == 204


def test_order_monitor_dashboard_ranks_owners_and_sorts_receipt_progress(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_a_token = register(client, "owner-a@example.com", "Alpha Owner")
    owner_b_token = register(client, "owner-b@example.com", "Beta Owner")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")

    project_a = client.post(
        "/api/projects",
        headers=auth(owner_a_token),
        json={"name": "Alpha project"},
    ).json()
    project_b = client.post(
        "/api/projects",
        headers=auth(owner_b_token),
        json={"name": "Beta project"},
    ).json()
    proteins_a = [
        client.post(
            f"/api/projects/{project_a['id']}/proteins",
            headers=auth(owner_a_token),
            json={"name": f"alpha-{index}", "sequence": unique_test_sequence(index)},
        ).json()
        for index in range(3)
    ]
    proteins_b = [
        client.post(
            f"/api/projects/{project_b['id']}/proteins",
            headers=auth(owner_b_token),
            json={"name": f"beta-{index}", "sequence": unique_test_sequence(index + 10)},
        ).json()
        for index in range(4)
    ]

    old_alpha = client.post(
        f"/api/projects/{project_a['id']}/batches",
        headers=auth(owner_a_token),
        json={
            "name": "Alpha old",
            "protein_ids": [proteins_a[0]["id"], proteins_a[1]["id"]],
        },
    ).json()
    today_alpha = client.post(
        f"/api/projects/{project_a['id']}/batches",
        headers=auth(owner_a_token),
        json={
            "name": "Alpha today",
            "protein_ids": [proteins_a[0]["id"], proteins_a[2]["id"]],
        },
    ).json()
    month_beta = client.post(
        f"/api/projects/{project_b['id']}/batches",
        headers=auth(owner_b_token),
        json={
            "name": "Beta month",
            "protein_ids": [
                proteins_b[0]["id"],
                proteins_b[1]["id"],
                proteins_b[2]["id"],
            ],
        },
    ).json()
    today_beta = client.post(
        f"/api/projects/{project_b['id']}/batches",
        headers=auth(owner_b_token),
        json={"name": "Beta today", "protein_ids": [proteins_b[3]["id"]]},
    ).json()

    for batch in (old_alpha, today_alpha, month_beta, today_beta):
        ordered = client.patch(
            f"/api/batches/{batch['batch']['id']}/status",
            headers=auth(admin_token),
            json={"order_status": "ordered"},
        )
        assert ordered.status_code == 200, ordered.text

    old_partial = client.patch(
        f"/api/batches/{old_alpha['batch']['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "ordered",
            "received_well_ids": [old_alpha["wells"][0]["id"]],
        },
    )
    assert old_partial.status_code == 200, old_partial.text
    month_partial = client.patch(
        f"/api/batches/{month_beta['batch']['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "ordered",
            "received_well_ids": [
                month_beta["wells"][0]["id"],
                month_beta["wells"][1]["id"],
            ],
        },
    )
    assert month_partial.status_code == 200, month_partial.text
    beta_full = client.patch(
        f"/api/batches/{today_beta['batch']['id']}/status",
        headers=auth(admin_token),
        json={
            "order_status": "ordered",
            "received_well_ids": [today_beta["wells"][0]["id"]],
        },
    )
    assert beta_full.status_code == 200, beta_full.text

    today = date.today()
    ordered_dates = {
        old_alpha["batch"]["id"]: today - timedelta(days=31),
        month_beta["batch"]["id"]: today - timedelta(days=20),
        today_alpha["batch"]["id"]: today,
        today_beta["batch"]["id"]: today,
    }
    settings = client.app.state.settings
    connection = connect(settings)
    try:
        for batch_id, ordered_date in ordered_dates.items():
            connection.execute(
                "UPDATE batches SET ordered_at = ? WHERE id = ?",
                (f"{ordered_date.isoformat()} 08:00:00", batch_id),
            )
        connection.commit()
    finally:
        connection.close()

    response = client.get("/api/order-monitor", headers=auth(admin_token))
    assert response.status_code == 200, response.text
    payload = response.json()

    today_rank = payload["owner_rankings"]["today"]
    assert [(rank["owner_name"], rank["protein_count"]) for rank in today_rank] == [
        ("Alpha Owner", 2),
        ("Beta Owner", 1),
    ]
    month_rank = payload["owner_rankings"]["month"]
    assert [(rank["owner_name"], rank["protein_count"]) for rank in month_rank] == [
        ("Beta Owner", 4),
        ("Alpha Owner", 2),
    ]
    assert month_rank[0]["batch_count"] == 2
    assert month_rank[1]["batch_count"] == 1

    progress_ids = [batch["id"] for batch in payload["batch_receipt_progress"]]
    assert progress_ids == [
        old_alpha["batch"]["id"],
        month_beta["batch"]["id"],
        today_alpha["batch"]["id"],
        today_beta["batch"]["id"],
    ]
    progress_by_id = {
        batch["id"]: batch for batch in payload["batch_receipt_progress"]
    }
    assert progress_by_id[old_alpha["batch"]["id"]]["received_well_count"] == 1
    assert progress_by_id[old_alpha["batch"]["id"]]["well_count"] == 2
    assert progress_by_id[today_alpha["batch"]["id"]]["received_well_count"] == 0
    assert progress_by_id[today_beta["batch"]["id"]]["receipt_progress_percent"] == 100
    assert round(
        progress_by_id[month_beta["batch"]["id"]]["receipt_progress_percent"],
        1,
    ) == 66.7


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

    ambiguous_filename = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[("files", ("run-A1-B2.zip", b"zip-a", "application/zip"))],
    )
    assert ambiguous_filename.status_code == 400
    assert "multiple well positions" in ambiguous_filename.json()["detail"]

    imported = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[
            ("files", ("akta-run-A01-export.zip", b"zip-a", "application/zip")),
            ("files", ("sample_A2_result.zip", b"zip-b", "application/zip")),
        ],
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    experiment = payload["experiment"]
    assert experiment["experiment_type"] == "AKTA"
    assert experiment["name"] == "AKTA 2026-08-01"
    assert experiment["details"]["file_count"] == 2
    assert experiment["details"]["requested_file_count"] == 2
    assert experiment["details"]["run_date"] == "2026-08-01"
    assert experiment["details"]["skipped_positions"] == []
    assert experiment["details"]["source"] == "AKTA"
    assert experiment["details"]["uploaded_positions"] == ["A01", "A02"]
    assert experiment["details"]["all_positions"] == ["A01", "A02"]
    assert experiment["details"]["total_result_count"] == 2
    assert {
        result["position"]: result["result_value"]
        for result in payload["results"]
        if result["result_value"]
    } == {
        "A01": "AKTA 2026-08-01",
        "A02": "AKTA 2026-08-01",
    }

    same_date_duplicate_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[("files", ("A01.zip", b"zip-a-again", "application/zip"))],
    )
    assert same_date_duplicate_upload.status_code == 409
    assert same_date_duplicate_upload.json()["detail"] == (
        "AKTA result already uploaded for position A01 on 2026-08-01"
    )

    same_date_partial_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[
            ("files", ("A01.zip", b"zip-a-again", "application/zip")),
            ("files", ("A03.zip", b"zip-c", "application/zip")),
        ],
    )
    assert same_date_partial_upload.status_code == 200, same_date_partial_upload.text
    assert same_date_partial_upload.json()["experiment"]["id"] == experiment["id"]
    partial_details = same_date_partial_upload.json()["experiment"]["details"]
    assert partial_details["file_count"] == 1
    assert partial_details["requested_file_count"] == 2
    assert partial_details["run_date"] == "2026-08-01"
    assert partial_details["skipped_positions"] == ["A01"]
    assert partial_details["source"] == "AKTA"
    assert partial_details["uploaded_positions"] == ["A03"]
    assert partial_details["all_positions"] == ["A01", "A02", "A03"]
    assert partial_details["total_result_count"] == 3
    assert {
        result["position"]: result["result_value"]
        for result in same_date_partial_upload.json()["results"]
        if result["result_value"]
    } == {
        "A01": "AKTA 2026-08-01",
        "A02": "AKTA 2026-08-01",
        "A03": "AKTA 2026-08-01",
    }

    different_date_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-02"},
        files=[("files", ("A01.zip", b"zip-a-new-day", "application/zip"))],
    )
    assert different_date_upload.status_code == 200, different_date_upload.text
    assert different_date_upload.json()["experiment"]["id"] != experiment["id"]
    assert different_date_upload.json()["experiment"]["details"]["uploaded_positions"] == [
        "A01"
    ]

    duplicate_batch_upload = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files=[
            ("files", ("A01.zip", b"zip-a-third", "application/zip")),
            ("files", ("A03.zip", b"zip-c-again", "application/zip")),
        ],
    )
    assert duplicate_batch_upload.status_code == 409
    assert duplicate_batch_upload.json()["detail"] == (
        "AKTA results already uploaded for positions on 2026-08-01: A01, A03"
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
    assert "AKTA_2026-08-02_A01.png" in artifact_filenames
    assert artifact_filenames["AKTA_2026-08-01_A01.png"]["artifact_type"] == "experimental_result"
    assert {
        result["result_value"]
        for result in protein_payload["batch_results"]
        if result["experiment_type"] == "AKTA"
    } == {"AKTA 2026-08-01", "AKTA 2026-08-02"}

    png_download = client.get(
        f"/api/artifacts/{artifact_filenames['AKTA_2026-08-01_A01.png']['id']}/download",
        headers=auth(owner_token),
    )
    assert png_download.status_code == 200, png_download.text
    assert png_download.content == b"PNG for A01.zip"


def test_akta_results_upload_uses_position_mapping_csv(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Mapped AKTA batch"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-a", "sequence": "ACDEFG"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Mapped AKTA plate", "protein_ids": [protein["id"]]},
    ).json()["batch"]
    mapping_csv = b"result_position,batch_position\nB1,A1\n"

    response = client.post(
        f"/api/batches/{batch['id']}/akta-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-03"},
        files=[
            ("files", ("B01.zip", b"zip-b", "application/zip")),
            ("files", ("C01.zip", b"zip-c", "application/zip")),
            ("position_mapping_file", ("mapping.csv", mapping_csv, "text/csv")),
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    details = payload["experiment"]["details"]
    assert details["uploaded_positions"] == ["A01"]
    assert details["skipped_result_positions"] == ["C01"]
    assert details["unused_mapping_positions"] == []
    assert details["mapped_positions"] == [
        {"result_position": "B01", "batch_position": "A01"}
    ]
    assert {
        result["position"]: result["result_value"]
        for result in payload["results"]
        if result["result_value"]
    } == {"A01": "AKTA 2026-08-03"}
    note = json.loads(
        next(
            result["result_note"]
            for result in payload["results"]
            if result["position"] == "A01"
        )
    )
    assert note["result_position"] == "B01"
    assert note["plate_position"] == "A01"
    raw_files = client.get(
        f"/api/experiments/{payload['experiment']['id']}/raw-files",
        headers=auth(owner_token),
    ).json()
    assert ("mapping.csv", "position_mapping_csv") in {
        (item["filename"], item["raw_file_type"]) for item in raw_files
    }


def test_batch_spr_results_upload_maps_charts_and_table_rows(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "SPR batch"},
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
            "name": "SPR plate",
            "protein_ids": [protein_a["id"], protein_b["id"], protein_c["id"]],
        },
    ).json()["batch"]
    spr_pptx = make_fake_spr_pptx(
        [("A1XXX", "1.00e-09"), ("A2XXX", "2.00e-09")]
    )
    spr_conc_csv = (
        b"protein_name,Conc1,Conc2,Conc3,Conc4\n"
        b"binder-a,800nM,200nM,50nM,12.5nM\n"
        b"binder-b,600nM,150nM,37.5nM,9.4nM\n"
        b"binder-c,400nM,100nM,25nM,6.25nM\n"
    )

    outsider_upload = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(outsider_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-results.pptx",
                spr_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert outsider_upload.status_code == 403

    wrong_extension = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={"file": ("spr-results.txt", spr_pptx, "text/plain")},
    )
    assert wrong_extension.status_code == 400

    imported = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-results.pptx",
                spr_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    experiment = payload["experiment"]
    assert experiment["experiment_type"] == "SPR"
    assert experiment["name"] == "SPR 2026-08-01"
    assert experiment["details"]["source"] == "SPR"
    assert experiment["details"]["run_date"] == "2026-08-01"
    assert experiment["details"]["sample_count"] == 2
    assert experiment["details"]["uploaded_positions"] == ["A01", "A02"]
    assert experiment["details"]["skipped_positions"] == []
    assert experiment["details"]["sample_ids"] == ["A1XXX", "A2XXX"]
    assert experiment["details"]["all_positions"] == ["A01", "A02"]
    assert experiment["details"]["all_sample_ids"] == ["A1XXX", "A2XXX"]
    assert {
        result["position"]: result["result_value"]
        for result in payload["results"]
        if result["result_value"]
    } == {"A01": "SPR A1XXX", "A02": "SPR A2XXX"}

    raw_files_response = client.get(
        f"/api/experiments/{experiment['id']}/raw-files",
        headers=auth(owner_token),
    )
    assert raw_files_response.status_code == 200, raw_files_response.text
    raw_files = raw_files_response.json()
    assert [(item["filename"], item["raw_file_type"]) for item in raw_files] == [
        ("spr-results.pptx", "spr_results_pptx")
    ]
    raw_download = client.get(
        f"/api/experiment-raw-files/{raw_files[0]['id']}/download",
        headers=auth(owner_token),
    )
    assert raw_download.status_code == 200, raw_download.text
    assert raw_download.content == spr_pptx

    outsider_raw_files = client.get(
        f"/api/experiments/{experiment['id']}/raw-files",
        headers=auth(outsider_token),
    )
    assert outsider_raw_files.status_code == 403

    result_note = json.loads(
        next(
            result["result_note"]
            for result in payload["results"]
            if result["position"] == "A01"
        )
    )
    assert result_note["source"] == "SPR"
    assert result_note["run_date"] == "2026-08-01"
    assert result_note["sample_id"] == "A1XXX"
    assert result_note["slide_number"] == 9
    assert result_note["table_row"]["Single cycle kinetics 1 Solution"] == "A1XXX"
    assert result_note["table_row"]["KD (M)"] == "1.00e-09"
    assert result_note["concentrations"] == {}

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
    assert "SPR_2026-08-01_A1XXX_A01.svg" in artifact_filenames
    spr_artifact = artifact_filenames["SPR_2026-08-01_A1XXX_A01.svg"]
    assert spr_artifact["artifact_type"] == "experimental_result"
    assert spr_artifact["mime_type"] == "image/svg+xml"
    assert result_note["chart_artifact_id"] == spr_artifact["id"]

    svg_download = client.get(
        f"/api/artifacts/{spr_artifact['id']}/download",
        headers=auth(owner_token),
    )
    assert svg_download.status_code == 200, svg_download.text
    assert svg_download.content.startswith(b"<svg")
    assert b"A1XXX SPR result" in svg_download.content
    assert b"Conc1: 800nM" not in svg_download.content

    concentration_uploaded = client.post(
        f"/api/batches/{batch['id']}/spr-concentrations",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "SPR_conc.csv",
                spr_conc_csv,
                "text/csv",
            )
        },
    )
    assert concentration_uploaded.status_code == 200, concentration_uploaded.text
    concentration_payload = concentration_uploaded.json()
    assert concentration_payload["experiment"]["id"] == experiment["id"]
    assert concentration_payload["experiment"]["details"]["concentration_filename"] == "SPR_conc.csv"
    assert concentration_payload["experiment"]["details"]["concentration_count"] == 3
    raw_files_after_concentrations = client.get(
        f"/api/experiments/{experiment['id']}/raw-files",
        headers=auth(owner_token),
    ).json()
    assert {
        (item["filename"], item["raw_file_type"])
        for item in raw_files_after_concentrations
    } == {
        ("spr-results.pptx", "spr_results_pptx"),
        ("SPR_conc.csv", "spr_concentrations_csv"),
    }
    updated_result_note = json.loads(
        next(
            result["result_note"]
            for result in concentration_payload["results"]
            if result["position"] == "A01"
        )
    )
    assert updated_result_note["concentrations"] == {
        "Conc1": "800nM",
        "Conc2": "200nM",
        "Conc3": "50nM",
        "Conc4": "12.5nM",
    }

    updated_svg_download = client.get(
        f"/api/artifacts/{spr_artifact['id']}/download",
        headers=auth(owner_token),
    )
    assert updated_svg_download.status_code == 200, updated_svg_download.text
    assert b"Conc1: 800nM" in updated_svg_download.content

    same_date_partial_pptx = make_fake_spr_pptx(
        [("A1XXX", "1.00e-09"), ("A3XXX", "3.00e-09")]
    )
    same_date_partial = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-partial-results.pptx",
                same_date_partial_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert same_date_partial.status_code == 200, same_date_partial.text
    assert same_date_partial.json()["experiment"]["id"] == experiment["id"]
    partial_details = same_date_partial.json()["experiment"]["details"]
    assert partial_details["sample_count"] == 1
    assert partial_details["requested_sample_count"] == 2
    assert partial_details["uploaded_positions"] == ["A03"]
    assert partial_details["skipped_positions"] == ["A01"]
    assert partial_details["all_positions"] == ["A01", "A02", "A03"]
    assert partial_details["total_result_count"] == 3
    assert {
        result["position"]: result["result_value"]
        for result in same_date_partial.json()["results"]
        if result["result_value"]
    } == {
        "A01": "SPR A1XXX",
        "A02": "SPR A2XXX",
        "A03": "SPR A3XXX",
    }

    same_date_duplicate = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-duplicate-results.pptx",
                same_date_partial_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert same_date_duplicate.status_code == 409
    assert same_date_duplicate.json()["detail"] == (
        "SPR results already uploaded for positions on 2026-08-01: A01, A03"
    )

    different_date = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-02"},
        files={
            "file": (
                "spr-next-day-results.pptx",
                make_fake_spr_pptx([("A1XXX", "1.10e-09")]),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert different_date.status_code == 200, different_date.text
    assert different_date.json()["experiment"]["id"] != experiment["id"]
    assert different_date.json()["experiment"]["details"]["run_date"] == "2026-08-02"
    assert different_date.json()["experiment"]["details"]["uploaded_positions"] == [
        "A01"
    ]


def test_spr_results_upload_uses_position_mapping_csv(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Mapped SPR batch"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-a", "sequence": "ACDEFG"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Mapped SPR plate", "protein_ids": [protein["id"]]},
    ).json()["batch"]
    mapping_csv = b"result_position,batch_position\nB1,A1\n"

    response = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-03"},
        files=[
            (
                "file",
                (
                    "spr-mapped-results.pptx",
                    make_fake_spr_pptx(
                        [("B1XXX", "1.00e-09"), ("C1XXX", "2.00e-09")]
                    ),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            ),
            ("position_mapping_file", ("mapping.csv", mapping_csv, "text/csv")),
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    details = payload["experiment"]["details"]
    assert details["uploaded_positions"] == ["A01"]
    assert details["skipped_result_positions"] == ["C01"]
    assert details["unused_mapping_positions"] == []
    assert details["mapped_positions"] == [
        {"result_position": "B01", "batch_position": "A01"}
    ]
    assert details["requested_sample_count"] == 2
    assert details["sample_count"] == 1
    assert {
        result["position"]: result["result_value"]
        for result in payload["results"]
        if result["result_value"]
    } == {"A01": "SPR B1XXX"}
    note = json.loads(
        next(
            result["result_note"]
            for result in payload["results"]
            if result["position"] == "A01"
        )
    )
    assert note["result_position"] == "B01"
    assert note["plate_position"] == "A01"
    raw_files = client.get(
        f"/api/experiments/{payload['experiment']['id']}/raw-files",
        headers=auth(owner_token),
    ).json()
    assert ("mapping.csv", "position_mapping_csv") in {
        (item["filename"], item["raw_file_type"]) for item in raw_files
    }


def test_spr_chart_legend_renames_numeric_series_labels() -> None:
    svg = _chart_svg(
        sample_id="A1XXX",
        slide_number=9,
        series=[
            {
                "label": "1",
                "color": "#2563eb",
                "points": [(0.0, 0.0), (1.0, 1.0)],
            },
            {
                "label": "2",
                "color": "#0f766e",
                "points": [(0.0, 0.2), (1.0, 0.8)],
            },
        ],
        x_axis="Time (s)",
        y_axis="Relative response (RU)",
    )
    assert b"raw data" in svg
    assert b"fitted data" in svg


def test_batch_spr_results_upload_extracts_positions_from_sample_ids(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "SPR embedded positions"},
    ).json()
    proteins = [
        client.post(
            f"/api/projects/{project['id']}/proteins",
            headers=auth(owner_token),
            json={"name": f"binder-{index}", "sequence": unique_test_sequence(index)},
        ).json()
        for index in range(2)
    ]
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "SPR plate",
            "protein_ids": [protein["id"] for protein in proteins],
        },
    ).json()["batch"]

    imported = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-embedded-results.pptx",
                make_fake_spr_pptx(
                    [
                        ("sample-A1XXX", "1.00e-09"),
                        ("screen_A2_result", "2.00e-09"),
                    ]
                ),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["experiment"]["details"]["uploaded_positions"] == [
        "A01",
        "A02",
    ]

    ambiguous = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-02"},
        files={
            "file": (
                "spr-ambiguous-results.pptx",
                make_fake_spr_pptx([("sample-A1-B2", "1.00e-09")]),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert ambiguous.status_code == 400
    assert "multiple well positions" in ambiguous.json()["detail"]


def test_batch_spr_results_upload_detects_dynamic_slides_and_ignores_thumbnails(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "SPR dynamic slides"},
    ).json()
    proteins = [
        client.post(
            f"/api/projects/{project['id']}/proteins",
            headers=auth(owner_token),
            json={"name": f"binder-{index}", "sequence": unique_test_sequence(index)},
        ).json()
        for index in range(2)
    ]
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "SPR nonstandard deck",
            "protein_ids": [protein["id"] for protein in proteins],
        },
    ).json()["batch"]
    spr_pptx = make_fake_spr_pptx(
        [("A1XXX", "1.00e-09"), ("A2XXX", "2.00e-09")],
        chart_slide_numbers=[3, 7],
        table_slide_number=18,
        include_thumbnail_decoys=True,
        use_relative_chart_targets=True,
    )

    imported = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-dynamic-results.pptx",
                spr_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    assert payload["experiment"]["details"]["sample_ids"] == ["A1XXX", "A2XXX"]
    assert payload["experiment"]["details"]["uploaded_positions"] == ["A01", "A02"]
    assert "A98XXX" not in payload["experiment"]["details"]["sample_ids"]
    assert "A99XXX" not in payload["experiment"]["details"]["sample_ids"]

    result_note = json.loads(
        next(
            result["result_note"]
            for result in payload["results"]
            if result["position"] == "A01"
        )
    )
    assert result_note["slide_number"] == 3
    assert result_note["table_row"]["Single cycle kinetics 1 Solution"] == "A1XXX"


def test_batch_spr_results_upload_maps_a13_test_labels_to_next_row(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "SPR sequential labels"},
    ).json()
    proteins = [
        client.post(
            f"/api/projects/{project['id']}/proteins",
            headers=auth(owner_token),
            json={"name": f"binder-{index}", "sequence": unique_test_sequence(index)},
        ).json()
        for index in range(14)
    ]
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "SPR plate",
            "protein_ids": [protein["id"] for protein in proteins],
        },
    ).json()["batch"]
    spr_pptx = make_fake_spr_pptx(
        [("A13XXX", "1.30e-09"), ("A14XXX", "1.40e-09")]
    )

    imported = client.post(
        f"/api/batches/{batch['id']}/spr-results",
        headers=auth(owner_token),
        data={"run_date": "2026-08-01"},
        files={
            "file": (
                "spr-sequential-results.pptx",
                spr_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    assert {
        result["position"]: result["result_value"]
        for result in imported.json()["results"]
        if result["result_value"]
    } == {"B01": "SPR A13XXX", "B02": "SPR A14XXX"}


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


def test_batch_translation_csv_import_replaces_selected_dna(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Manual translation batch"},
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
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Manual translation plate",
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
            "backbone": "5",
            "resistance": "Kan",
        },
    )
    assert translated.status_code == 200, translated.text

    short_manual_dna = "ATGGGTAAA"
    imported = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={
            "file": (
                "manual-translations.csv",
                f"蛋白名称,DNA序列\nshort,{short_manual_dna}\n".encode(),
                "text/csv",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    assert payload["padding"] is True
    assert payload["add_additional_w"] is True
    assert payload["backbone"] == "5"
    assert payload["resistance"] == "Kan"

    sequences_by_name = {
        sequence["protein_name"]: sequence for sequence in payload["sequences"]
    }
    assert sequences_by_name["short"]["dna_sequence"] == short_manual_dna
    assert sequences_by_name["short"]["translated_aa_sequence"] == "MGK"
    assert translate_dna(sequences_by_name["short"]["dna_sequence"]) == "MGK"
    assert translate_dna(sequences_by_name["long"]["dna_sequence"]) == "ACDEFGW"

    long_manual_dna = "GCTTGTGATGAATTTGGT"
    headerless_import = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={
            "file": (
                "manual-translations.csv",
                f"long,{long_manual_dna}\n".encode(),
                "text/csv",
            )
        },
    )
    assert headerless_import.status_code == 200, headerless_import.text
    sequences_by_name = {
        sequence["protein_name"]: sequence
        for sequence in headerless_import.json()["sequences"]
    }
    assert sequences_by_name["short"]["dna_sequence"] == short_manual_dna
    assert sequences_by_name["long"]["dna_sequence"] == long_manual_dna
    assert sequences_by_name["long"]["translated_aa_sequence"] == "ACDEFG"
    assert ">A01 short\n" in headerless_import.json()["dna_fasta"]
    assert ">A02 long\n" in headerless_import.json()["dna_fasta"]

    batch_detail = client.get(
        f"/api/batches/{batch['id']}",
        headers=auth(owner_token),
    )
    assert batch_detail.status_code == 200, batch_detail.text
    wells_by_name = {
        well["protein_name"]: well for well in batch_detail.json()["wells"]
    }
    assert wells_by_name["short"]["dna_sequence"] == short_manual_dna
    assert wells_by_name["short"]["translated_aa_sequence"] == "MGK"
    assert wells_by_name["long"]["dna_sequence"] == long_manual_dna
    assert wells_by_name["long"]["translated_aa_sequence"] == "ACDEFG"

    summary_export = client.get(
        f"/api/batches/{batch['id']}/summary/export",
        headers=auth(owner_token),
    )
    assert summary_export.status_code == 200, summary_export.text
    summary_values = xlsx_sheet_values(summary_export.content)
    assert summary_values["B7"] == 6
    assert summary_values["B8"] == 3


def test_batch_translation_csv_import_validates_input_and_access(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")
    outsider_token = register(client, "outsider@example.com")
    admin_token = register(client, "ruolan.chen@northstar-bio.local", "陈若澜")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Manual translation validation"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder", "sequence": "MGK"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Validation plate", "protein_ids": [protein["id"]]},
    ).json()["batch"]
    valid_dna = "ATGGGTAAA"

    unmatched = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={
            "file": (
                "manual.csv",
                f" binder,{valid_dna}\n".encode(),
                "text/csv",
            )
        },
    )
    assert unmatched.status_code == 400
    assert "not in this batch" in unmatched.json()["detail"]

    duplicate_csv = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={
            "file": (
                "manual.csv",
                f"binder,{valid_dna}\nbinder,{valid_dna}\n".encode(),
                "text/csv",
            )
        },
    )
    assert duplicate_csv.status_code == 400
    assert "duplicate protein name" in duplicate_csv.json()["detail"]

    invalid_dna = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={"file": ("manual.csv", b"binder,ATGN\n", "text/csv")},
    )
    assert invalid_dna.status_code == 400
    assert "not divisible by 3" in invalid_dna.json()["detail"]

    mismatch = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={"file": ("manual.csv", b"binder,GCT\n", "text/csv")},
    )
    assert mismatch.status_code == 400
    assert "DNA verification failed" in mismatch.json()["detail"]

    outsider_import = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(outsider_token),
        files={"file": ("manual.csv", f"binder,{valid_dna}\n".encode(), "text/csv")},
    )
    assert outsider_import.status_code == 403

    duplicate_name_project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Duplicate protein names"},
    ).json()
    first_duplicate = client.post(
        f"/api/projects/{duplicate_name_project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "dup", "sequence": "MGK"},
    ).json()
    second_duplicate = client.post(
        f"/api/projects/{duplicate_name_project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "dup", "sequence": "ACDEFG"},
    ).json()
    duplicate_name_batch = client.post(
        f"/api/projects/{duplicate_name_project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "Duplicate names plate",
            "protein_ids": [first_duplicate["id"], second_duplicate["id"]],
        },
    ).json()["batch"]
    ambiguous = client.post(
        f"/api/batches/{duplicate_name_batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={"file": ("manual.csv", f"dup,{valid_dna}\n".encode(), "text/csv")},
    )
    assert ambiguous.status_code == 400
    assert "match multiple batch wells" in ambiguous.json()["detail"]

    ordered = client.patch(
        f"/api/batches/{batch['id']}/status",
        headers=auth(admin_token),
        json={"order_status": "ordered"},
    )
    assert ordered.status_code == 200, ordered.text
    locked_import = client.post(
        f"/api/batches/{batch['id']}/translations/import-csv",
        headers=auth(owner_token),
        files={"file": ("manual.csv", f"binder,{valid_dna}\n".encode(), "text/csv")},
    )
    assert locked_import.status_code == 400
    assert "cannot be changed" in locked_import.json()["detail"]


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
    akta = client.post(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(owner_token),
        json={"experiment_type": "AKTA", "name": "AKTA import"},
    )
    assert spr.status_code == 200, spr.text
    assert hplc.status_code == 200, hplc.text
    assert akta.status_code == 200, akta.text

    experiments = client.get(
        f"/api/batches/{batch['id']}/experiments",
        headers=auth(member_token),
    )
    assert experiments.status_code == 200, experiments.text
    assert {experiment["experiment_type"] for experiment in experiments.json()} == {
        "FPLC",
        "SPR",
        "HPLC",
        "AKTA",
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
    assert listed_after_result.json()[0]["experiment_count"] == 4
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


def test_hplc_results_upload_maps_files_and_vial_blocks(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "HPLC project"},
    ).json()

    protein_a = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={
            "name": "binder-a",
            "sequence": "ACDEFG",
            "protein_type": "TCR",
        },
    ).json()
    protein_b = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={
            "name": "binder-b",
            "sequence": "HIKLMN",
            "protein_type": "TCR",
        },
    ).json()

    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={
            "name": "HPLC batch",
            "protein_ids": [protein_a["id"], protein_b["id"]],
        },
    ).json()["batch"]

    chromatogram_a = b"0.00,-2.9\n0.50,-2.7\n1.00,-2.5\n1.50,-2.4\n2.00,-2.6\n"
    chromatogram_b = b"0.00,-3.1\n0.50,-2.8\n1.00,-2.3\n1.50,-2.1\n2.00,-2.2\n"
    vial_fc_csv = (
        "样品 名称,20260711 183616D1F-A1-result\n"
        "编号,位置,开始时间 (min),结束时间 (min),体积 (mL)\n"
        "1,P1-I22,1.500,1.776,0.18\n"
        "2,P1-I23,1.779,1.808,0.03\n"
        "\"参比检测器 = DAD1 (起始延迟时间: 0.096 min, 结束延迟时间: 0.096 min)\"\n\n"
        "样品 名称,20260711 184745D1F-A2-result\n"
        "编号,位置,开始时间 (min),结束时间 (min),体积 (mL)\n"
        "1,P1-J1,0.500,1.250,0.20\n"
        "\"参比检测器 = DAD1 (起始延迟时间: 0.096 min, 结束延迟时间: 0.096 min)\"\n"
    ).encode("utf-8")

    response = client.post(
        f"/api/batches/{batch['id']}/hplc-results",
        headers=auth(owner_token),
        data={"source_name": "20260710-TGFR1-48SAMPLES"},
        files=[
            (
                "files",
                (
                    "20260711 183616D1F-A1-result.dx_DAD1A.CSV",
                    chromatogram_a,
                    "text/csv",
                ),
            ),
            (
                "files",
                (
                    "20260711 184745D1F-A2-result.dx_DAD1A.CSV",
                    chromatogram_b,
                    "text/csv",
                ),
            ),
            ("files", ("vial_fc.csv", vial_fc_csv, "text/csv")),
        ],
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    experiment = payload["experiment"]
    assert experiment["experiment_type"] == "HPLC"
    assert experiment["details"]["source_name"] == "20260710-TGFR1-48SAMPLES"
    assert experiment["details"]["sample_count"] == 2
    assert [result["position"] for result in payload["results"]] == ["A01", "A02"]

    raw_files_response = client.get(
        f"/api/experiments/{experiment['id']}/raw-files",
        headers=auth(owner_token),
    )
    assert raw_files_response.status_code == 200, raw_files_response.text
    raw_files = raw_files_response.json()
    assert {
        (item["filename"], item["raw_file_type"])
        for item in raw_files
    } == {
        ("vial_fc.csv", "hplc_vial_fc_csv"),
        ("20260711 183616D1F-A1-result.dx_DAD1A.CSV", "hplc_chromatogram_csv"),
        ("20260711 184745D1F-A2-result.dx_DAD1A.CSV", "hplc_chromatogram_csv"),
    }
    chromatogram_raw_file = next(
        item
        for item in raw_files
        if item["filename"] == "20260711 183616D1F-A1-result.dx_DAD1A.CSV"
    )
    assert chromatogram_raw_file["position"] == "A01"
    assert chromatogram_raw_file["protein_id"] == protein_a["id"]
    assert chromatogram_raw_file["protein_name"] == "binder-a"
    vial_raw_file = next(item for item in raw_files if item["filename"] == "vial_fc.csv")
    vial_download = client.get(
        f"/api/experiment-raw-files/{vial_raw_file['id']}/download",
        headers=auth(owner_token),
    )
    assert vial_download.status_code == 200, vial_download.text
    assert vial_download.content == vial_fc_csv

    first_result = payload["results"][0]
    note = json.loads(first_result["result_note"])
    assert note["source"] == "HPLC"
    assert note["plate_position"] == "A01"
    assert note["block_count"] == 2
    assert note["blocks"][0]["position"] == "P1-I22"
    artifact_id = note["chart_artifact_id"]

    protein_detail = client.get(
        f"/api/proteins/{protein_a['id']}",
        headers=auth(owner_token),
    )
    assert protein_detail.status_code == 200, protein_detail.text
    artifact = next(
        item
        for item in protein_detail.json()["artifacts"]
        if item["filename"].startswith("HPLC_A01_")
    )
    assert artifact["artifact_type"] == "experimental_result"
    assert artifact["mime_type"] == "image/svg+xml"

    download = client.get(
        f"/api/artifacts/{artifact['id']}/download",
        headers=auth(owner_token),
    )
    assert download.status_code == 200, download.text
    svg = download.text
    assert "HPLC A01" in svg
    assert "P1-I22" in svg
    assert svg.count("<rect") >= 2
    assert artifact["id"] == artifact_id


def test_hplc_results_upload_uses_position_mapping_csv(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    owner_token = register(client, "owner@example.com")

    project = client.post(
        "/api/projects",
        headers=auth(owner_token),
        json={"name": "Mapped HPLC project"},
    ).json()
    protein = client.post(
        f"/api/projects/{project['id']}/proteins",
        headers=auth(owner_token),
        json={"name": "binder-a", "sequence": "ACDEFG"},
    ).json()
    batch = client.post(
        f"/api/projects/{project['id']}/batches",
        headers=auth(owner_token),
        json={"name": "Mapped HPLC batch", "protein_ids": [protein["id"]]},
    ).json()["batch"]
    chromatogram_b = b"0.00,-2.9\n0.50,-2.7\n1.00,-2.5\n"
    chromatogram_c = b"0.00,-3.1\n0.50,-2.8\n1.00,-2.3\n"
    vial_fc_csv = (
        "样品 名称,run-B1-result\n"
        "编号,位置,开始时间 (min),结束时间 (min),体积 (mL)\n"
        "1,P1-I22,0.100,0.500,0.18\n\n"
        "样品 名称,run-C1-result\n"
        "编号,位置,开始时间 (min),结束时间 (min),体积 (mL)\n"
        "1,P1-J1,0.500,1.000,0.20\n"
    ).encode("utf-8")
    mapping_csv = b"result_position,batch_position\nB1,A1\n"

    response = client.post(
        f"/api/batches/{batch['id']}/hplc-results",
        headers=auth(owner_token),
        data={"source_name": "mapped-run"},
        files=[
            (
                "files",
                ("run-B1-result.dx_DAD1A.CSV", chromatogram_b, "text/csv"),
            ),
            (
                "files",
                ("run-C1-result.dx_DAD1A.CSV", chromatogram_c, "text/csv"),
            ),
            ("files", ("vial_fc.csv", vial_fc_csv, "text/csv")),
            ("position_mapping_file", ("mapping.csv", mapping_csv, "text/csv")),
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    details = payload["experiment"]["details"]
    assert details["plate_positions"] == ["A01"]
    assert details["skipped_result_positions"] == ["C01"]
    assert details["unused_mapping_positions"] == []
    assert details["mapped_positions"] == [
        {"result_position": "B01", "batch_position": "A01"}
    ]
    assert [result["position"] for result in payload["results"]] == ["A01"]
    note = json.loads(payload["results"][0]["result_note"])
    assert note["result_position"] == "B01"
    assert note["plate_position"] == "A01"
    raw_files = client.get(
        f"/api/experiments/{payload['experiment']['id']}/raw-files",
        headers=auth(owner_token),
    ).json()
    assert ("mapping.csv", "position_mapping_csv") in {
        (item["filename"], item["raw_file_type"]) for item in raw_files
    }
