from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from proteinhub.config import Settings
from proteinhub.domain.errors import ConfigurationError, ExternalToolError
from proteinhub.infrastructure.storage.paths import safe_filename


def render_akta_pngs(zip_files: dict[str, bytes], *, settings: Settings) -> dict[str, bytes]:
    if not zip_files:
        return {}

    python_path, script_path = _configured_paths(settings)
    with tempfile.TemporaryDirectory(prefix="proteinhub-akta-") as temp_dir:
        work_dir = Path(temp_dir)
        input_paths = _write_zip_files(work_dir, zip_files)
        command = [
            str(python_path),
            str(script_path),
            *(str(path) for path in input_paths),
            "--output",
            "png",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=settings.akta_hap_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExternalToolError("AKTA renderer timed out") from exc
        except OSError as exc:
            raise ExternalToolError("AKTA renderer could not be started") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            message = "AKTA renderer failed"
            if detail:
                message = f"{message}: {detail[-500:]}"
            raise ExternalToolError(message)

        rendered: dict[str, bytes] = {}
        for input_path in input_paths:
            output_path = input_path.with_suffix(".png")
            if not output_path.exists():
                raise ExternalToolError(
                    f"AKTA renderer did not write PNG for {input_path.name}"
                )
            rendered[input_path.name] = output_path.read_bytes()
        return rendered


def _configured_paths(settings: Settings) -> tuple[Path, Path]:
    python_path = settings.akta_hap_python
    script_path = settings.akta_hap_script
    if python_path is None:
        raise ConfigurationError("AKTA renderer Python is not configured")
    if script_path is None:
        raise ConfigurationError("AKTA renderer script is not configured")
    if not python_path.exists():
        raise ConfigurationError("AKTA renderer Python does not exist")
    if not script_path.exists():
        raise ConfigurationError("AKTA renderer script does not exist")
    return python_path, script_path


def _write_zip_files(work_dir: Path, zip_files: dict[str, bytes]) -> list[Path]:
    input_paths = []
    for filename, content in zip_files.items():
        safe_name = safe_filename(filename)
        if not safe_name.lower().endswith(".zip"):
            raise ExternalToolError("AKTA renderer input files must be zip files")
        path = work_dir / safe_name
        path.write_bytes(content)
        input_paths.append(path)
    return input_paths
