from __future__ import annotations

from fastapi import FastAPI
from nicegui import ui

from proteinhub.api import create_api_router
from proteinhub.config import get_settings
from proteinhub.db import init_db
from proteinhub.ui import install_ui


def create_app() -> FastAPI:
    settings = get_settings()
    init_db(settings.database_path)
    settings.storage_root.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="ProteinHub MVP")
    app.include_router(
        create_api_router(
            database_path=settings.database_path,
            storage_root=settings.storage_root,
            settings=settings,
        )
    )
    install_ui(
        database_path=settings.database_path,
        storage_root=settings.storage_root,
        settings=settings,
    )
    ui.run_with(app, title="ProteinHub", storage_secret="dev-storage-secret")
    return app
