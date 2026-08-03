from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
HOME_DIR = Path.home()
LEGACY_DOMESTICATOR_PYTHON_CANDIDATES = (
    BASE_DIR / ".legacy/trans/bin/python",
    Path("/home/yuguo/software/miniconda3/envs/trans/bin/python"),
    HOME_DIR / "miniconda3/envs/trans/bin/python",
    HOME_DIR / "anaconda3/envs/trans/bin/python",
    HOME_DIR / "mambaforge/envs/trans/bin/python",
    HOME_DIR / "micromamba/envs/trans/bin/python",
    HOME_DIR / ".conda/envs/trans/bin/python",
    Path("/opt/miniconda3/envs/trans/bin/python"),
    Path("/opt/anaconda3/envs/trans/bin/python"),
)
LEGACY_DOMESTICATOR_SCRIPT_CANDIDATES = (
    HOME_DIR / "Downloads/domesticator.py",
)
LEGACY_DOMESTICATOR_DATABASE_CANDIDATES = (
    HOME_DIR / "Documents/SMARTS_intern/database",
)
AKTA_HAP_PYTHON_CANDIDATES = (
    BASE_DIR / ".legacy/akta/bin/python",
    HOME_DIR / "Documents/SMARTS_intern/LJW-AKTAResults/.venv/bin/python",
    Path(sys.executable),
)
AKTA_HAP_SCRIPT_CANDIDATES = (
    HOME_DIR / "Documents/SMARTS_intern/LJW-AKTAResults/akta_hap.py",
)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    storage_root: Path
    jwt_secret: str
    nicegui_storage_secret: str
    jwt_issuer: str = "proteinhub"
    token_ttl_seconds: int = 60 * 60 * 24
    legacy_domesticator_python: Path | None = None
    legacy_domesticator_script: Path | None = None
    legacy_domesticator_database: Path | None = None
    legacy_domesticator_timeout_seconds: int = 300
    akta_hap_python: Path | None = None
    akta_hap_script: Path | None = None
    akta_hap_timeout_seconds: int = 120


def get_settings() -> Settings:
    data_dir = Path(os.getenv("PROTEINHUB_DATA_DIR", BASE_DIR / "data"))
    storage_root = Path(os.getenv("PROTEINHUB_STORAGE_DIR", BASE_DIR / "storage"))
    database_path = Path(os.getenv("PROTEINHUB_DATABASE", data_dir / "proteinhub.sqlite3"))
    jwt_secret = os.getenv("PROTEINHUB_JWT_SECRET", "dev-only-change-me")
    nicegui_storage_secret = os.getenv(
        "PROTEINHUB_NICEGUI_STORAGE_SECRET",
        "dev-storage-secret",
    )
    legacy_domesticator_python = _path_from_env_or_candidates(
        "PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON",
        LEGACY_DOMESTICATOR_PYTHON_CANDIDATES,
        executable=True,
    )
    legacy_domesticator_script = _path_from_env_or_candidates(
        "PROTEINHUB_LEGACY_DOMESTICATOR_SCRIPT",
        LEGACY_DOMESTICATOR_SCRIPT_CANDIDATES,
    )
    legacy_domesticator_database = _path_from_env_or_candidates(
        "PROTEINHUB_LEGACY_DOMESTICATOR_DATABASE",
        LEGACY_DOMESTICATOR_DATABASE_CANDIDATES,
        directory=True,
    )
    legacy_domesticator_timeout_seconds = int(
        os.getenv("PROTEINHUB_LEGACY_DOMESTICATOR_TIMEOUT_SECONDS", "300")
    )
    akta_hap_python = _path_from_env_or_candidates(
        "PROTEINHUB_AKTA_HAP_PYTHON",
        AKTA_HAP_PYTHON_CANDIDATES,
        executable=True,
    )
    akta_hap_script = _path_from_env_or_candidates(
        "PROTEINHUB_AKTA_HAP_SCRIPT",
        AKTA_HAP_SCRIPT_CANDIDATES,
    )
    akta_hap_timeout_seconds = int(
        os.getenv("PROTEINHUB_AKTA_HAP_TIMEOUT_SECONDS", "120")
    )
    return Settings(
        database_path=database_path,
        storage_root=storage_root,
        jwt_secret=jwt_secret,
        nicegui_storage_secret=nicegui_storage_secret,
        legacy_domesticator_python=legacy_domesticator_python,
        legacy_domesticator_script=legacy_domesticator_script,
        legacy_domesticator_database=legacy_domesticator_database,
        legacy_domesticator_timeout_seconds=legacy_domesticator_timeout_seconds,
        akta_hap_python=akta_hap_python,
        akta_hap_script=akta_hap_script,
        akta_hap_timeout_seconds=akta_hap_timeout_seconds,
    )


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def _path_from_env_or_candidates(
    env_name: str,
    candidates: tuple[Path, ...],
    *,
    directory: bool = False,
    executable: bool = False,
) -> Path | None:
    configured = _optional_path(os.getenv(env_name))
    if configured is not None:
        return configured
    for candidate in candidates:
        if directory and candidate.is_dir():
            return candidate
        if executable and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
        if not directory and not executable and candidate.is_file():
            return candidate
    return None
