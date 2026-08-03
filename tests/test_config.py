from __future__ import annotations

from pathlib import Path

from proteinhub import config


def test_get_settings_discovers_legacy_domesticator_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "envs" / "trans" / "bin" / "python"
    script_path = tmp_path / "domesticator.py"
    database_path = tmp_path / "database"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("#!/bin/sh\n", encoding="utf-8")
    python_path.chmod(0o755)
    script_path.write_text("# domesticator\n", encoding="utf-8")
    database_path.mkdir()

    monkeypatch.delenv("PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON", raising=False)
    monkeypatch.delenv("PROTEINHUB_LEGACY_DOMESTICATOR_SCRIPT", raising=False)
    monkeypatch.delenv("PROTEINHUB_LEGACY_DOMESTICATOR_DATABASE", raising=False)
    monkeypatch.setattr(
        config,
        "LEGACY_DOMESTICATOR_PYTHON_CANDIDATES",
        (python_path,),
    )
    monkeypatch.setattr(
        config,
        "LEGACY_DOMESTICATOR_SCRIPT_CANDIDATES",
        (script_path,),
    )
    monkeypatch.setattr(
        config,
        "LEGACY_DOMESTICATOR_DATABASE_CANDIDATES",
        (database_path,),
    )

    settings = config.get_settings()

    assert settings.legacy_domesticator_python == python_path
    assert settings.legacy_domesticator_script == script_path
    assert settings.legacy_domesticator_database == database_path


def test_get_settings_prefers_explicit_legacy_domesticator_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "python"
    script_path = tmp_path / "domesticator.py"
    database_path = tmp_path / "database"
    monkeypatch.setenv("PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON", str(python_path))
    monkeypatch.setenv("PROTEINHUB_LEGACY_DOMESTICATOR_SCRIPT", str(script_path))
    monkeypatch.setenv("PROTEINHUB_LEGACY_DOMESTICATOR_DATABASE", str(database_path))

    settings = config.get_settings()

    assert settings.legacy_domesticator_python == python_path
    assert settings.legacy_domesticator_script == script_path
    assert settings.legacy_domesticator_database == database_path


def test_get_settings_discovers_akta_hap_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "akta" / "bin" / "python"
    script_path = tmp_path / "akta_hap.py"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("#!/bin/sh\n", encoding="utf-8")
    python_path.chmod(0o755)
    script_path.write_text("# akta\n", encoding="utf-8")

    monkeypatch.delenv("PROTEINHUB_AKTA_HAP_PYTHON", raising=False)
    monkeypatch.delenv("PROTEINHUB_AKTA_HAP_SCRIPT", raising=False)
    monkeypatch.setattr(config, "AKTA_HAP_PYTHON_CANDIDATES", (python_path,))
    monkeypatch.setattr(config, "AKTA_HAP_SCRIPT_CANDIDATES", (script_path,))

    settings = config.get_settings()

    assert settings.akta_hap_python == python_path
    assert settings.akta_hap_script == script_path


def test_get_settings_prefers_explicit_akta_hap_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    python_path = tmp_path / "python"
    script_path = tmp_path / "akta_hap.py"
    monkeypatch.setenv("PROTEINHUB_AKTA_HAP_PYTHON", str(python_path))
    monkeypatch.setenv("PROTEINHUB_AKTA_HAP_SCRIPT", str(script_path))

    settings = config.get_settings()

    assert settings.akta_hap_python == python_path
    assert settings.akta_hap_script == script_path
