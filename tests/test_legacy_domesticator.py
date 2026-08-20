from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from proteinhub.config import Settings
from proteinhub.domain.errors import ExternalToolError
from proteinhub.infrastructure.translation.legacy_domesticator import (
    optimize_with_legacy_domesticator,
)


def test_legacy_domesticator_timeout_kills_child_processes(tmp_path: Path) -> None:
    database = tmp_path / "database"
    database.mkdir()
    script = tmp_path / "slow_domesticator.py"
    script.write_text(
        """
import subprocess
import sys
import time

subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
time.sleep(30)
""".lstrip(),
        encoding="utf-8",
    )
    settings = Settings(
        database_path=tmp_path / "proteinhub.sqlite3",
        storage_root=tmp_path / "storage",
        jwt_secret="test-secret",
        nicegui_storage_secret="test-storage-secret",
        legacy_domesticator_python=Path(sys.executable),
        legacy_domesticator_script=script,
        legacy_domesticator_database=database,
        legacy_domesticator_timeout_seconds=1,
    )

    started_at = time.monotonic()

    with pytest.raises(ExternalToolError, match="timed out after 1 seconds"):
        optimize_with_legacy_domesticator({"A01_test": "MGK"}, settings=settings)

    assert time.monotonic() - started_at < 5
