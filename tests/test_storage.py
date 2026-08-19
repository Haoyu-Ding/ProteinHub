import hashlib
from io import BytesIO
from pathlib import Path

from proteinhub.storage import (
    artifact_relative_path,
    protein_structure_relative_path,
    resolve_storage_path,
    safe_filename,
)
from proteinhub.infrastructure.database.connection import connect, init_db
from proteinhub.infrastructure.postgres.connection import _prepare_statement
from proteinhub.infrastructure.sqlite.repositories import (
    ArtifactRepository,
    ProteinRepository,
)
from proteinhub.infrastructure.storage.database_file_store import DatabaseFileStore


def test_safe_filename_removes_path_and_unsafe_characters() -> None:
    assert safe_filename("../bad name!.pdb") == "bad_name_.pdb"


def test_safe_filename_preserves_unicode_names() -> None:
    assert safe_filename("../设计打分摘要.md") == "设计打分摘要.md"


def test_artifact_relative_path_stays_under_project_protein_artifact() -> None:
    path = artifact_relative_path(
        project_id=1,
        protein_id=2,
        artifact_id=3,
        filename="../model.pdb",
    )

    assert path == Path("projects/1/proteins/2/artifacts/3/model.pdb")
    assert not path.is_absolute()


def test_protein_structure_relative_path_stays_under_project_protein() -> None:
    path = protein_structure_relative_path(
        project_id=1,
        protein_id=2,
        filename="../model.pdb",
    )

    assert path == Path("projects/1/proteins/2/structure/model.pdb")
    assert not path.is_absolute()


def test_resolve_storage_path_rejects_escape(tmp_path: Path) -> None:
    try:
        resolve_storage_path(tmp_path, "../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("storage escape was accepted")


def test_database_file_store_persists_artifact_bytes_without_repository_leak(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"
    init_db(database_path)
    with connect(database_path) as connection:
        user_id = _insert_user(connection)
        project_id = _insert_project(connection, user_id)
        protein_id = ProteinRepository(connection).insert(
            project_id=project_id,
            name="TCR-1",
            sequence="ACDE",
            dna_sequence="",
            description="",
            protein_type="TCR",
            target="",
        )
        artifacts = ArtifactRepository(connection)
        artifact_id = artifacts.insert_pending(
            protein_id=protein_id,
            uploaded_by=user_id,
            filename="raw.csv",
            artifact_type="experimental_result",
            mime_type="text/csv",
            storage_backend="database",
        )
        store = DatabaseFileStore(connection)

        stored = store.save_artifact(
            project_id=project_id,
            protein_id=protein_id,
            artifact_id=artifact_id,
            filename="raw.csv",
            source=BytesIO(b"time,value\n0,1\n"),
        )
        artifacts.mark_stored(
            artifact_id=artifact_id,
            size_bytes=stored.size_bytes,
            storage_path=stored.relative_path,
            storage_backend=store.backend,
        )

        artifact = artifacts.get(artifact_id)
        assert artifact is not None
        assert "content" not in artifact
        assert artifact["storage_backend"] == "database"
        assert artifact["content_sha256"] == hashlib.sha256(b"time,value\n0,1\n").hexdigest()
        assert store.read_artifact(artifact_id) == b"time,value\n0,1\n"


def test_database_file_store_persists_protein_structure_without_repository_leak(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "proteinhub.sqlite3"
    init_db(database_path)
    with connect(database_path) as connection:
        user_id = _insert_user(connection)
        project_id = _insert_project(connection, user_id)
        proteins = ProteinRepository(connection)
        protein_id = proteins.insert(
            project_id=project_id,
            name="TCR-1",
            sequence="ACDE",
            dna_sequence="",
            description="",
            protein_type="TCR",
            target="",
        )
        store = DatabaseFileStore(connection)

        stored = store.save_protein_structure(
            project_id=project_id,
            protein_id=protein_id,
            filename="source.pdb",
            source=BytesIO(b"HEADER    TEST\n"),
        )
        proteins.update_structure_file(
            protein_id=protein_id,
            filename="source.pdb",
            mime_type="chemical/x-pdb",
            size_bytes=stored.size_bytes,
            storage_path=stored.relative_path,
            storage_backend=store.backend,
        )

        protein = proteins.get(protein_id)
        assert protein is not None
        assert "structure_content" not in protein
        assert protein["structure_storage_backend"] == "database"
        assert protein["structure_content_sha256"] == hashlib.sha256(
            b"HEADER    TEST\n"
        ).hexdigest()
        assert store.read_protein_structure(protein_id) == b"HEADER    TEST\n"


def test_postgres_statement_adapter_handles_qmark_and_timestamp() -> None:
    statement = _prepare_statement(
        "UPDATE artifacts SET deleted_at = CURRENT_TIMESTAMP WHERE filename = ? "
        "AND mime_type = '?'"
    )

    assert statement == (
        "UPDATE artifacts SET deleted_at = (CURRENT_TIMESTAMP::text) "
        "WHERE filename = %s AND mime_type = '?'"
    )


def test_postgres_statement_adapter_does_not_double_cast_timestamp() -> None:
    statement = _prepare_statement(
        "CREATE TABLE example (created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text))"
    )

    assert statement == (
        "CREATE TABLE example (created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text))"
    )


def _insert_user(connection) -> int:
    cursor = connection.execute(
        """
        INSERT INTO users (name, email, password_hash)
        VALUES (?, ?, ?)
        """,
        ("User", "user@example.test", "hash"),
    )
    return int(cursor.lastrowid)


def _insert_project(connection, user_id: int) -> int:
    cursor = connection.execute(
        """
        INSERT INTO projects (name, owner_id)
        VALUES (?, ?)
        """,
        ("Project", user_id),
    )
    return int(cursor.lastrowid)
