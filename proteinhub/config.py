from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_path: Path
    storage_root: Path
    jwt_secret: str
    jwt_issuer: str = "proteinhub"
    token_ttl_seconds: int = 60 * 60 * 24


def get_settings() -> Settings:
    data_dir = Path(os.getenv("PROTEINHUB_DATA_DIR", BASE_DIR / "data"))
    storage_root = Path(os.getenv("PROTEINHUB_STORAGE_DIR", BASE_DIR / "storage"))
    database_path = Path(os.getenv("PROTEINHUB_DATABASE", data_dir / "proteinhub.sqlite3"))
    jwt_secret = os.getenv("PROTEINHUB_JWT_SECRET", "dev-only-change-me")
    return Settings(
        database_path=database_path,
        storage_root=storage_root,
        jwt_secret=jwt_secret,
    )

