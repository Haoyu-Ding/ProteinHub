from pathlib import Path

from proteinhub.storage import artifact_relative_path, resolve_storage_path, safe_filename


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


def test_resolve_storage_path_rejects_escape(tmp_path: Path) -> None:
    try:
        resolve_storage_path(tmp_path, "../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("storage escape was accepted")
