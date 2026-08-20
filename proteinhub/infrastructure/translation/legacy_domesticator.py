from __future__ import annotations

import logging
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from Bio.Seq import Seq

from proteinhub.config import Settings
from proteinhub.domain.errors import ConfigurationError, ExternalToolError


XIAOPANG_RESTRICTION_SITES = ("XhoI", "NdeI")
XIAOPANG_AVOID_PATTERNS = (
    "AGGAGG",
    "TAAGGAG",
    "GCTGGTGG",
    "TTTTTT",
    "AAAAAAA",
    "ATCTGTT",
    "GGRGGT",
    "MAGGTRAG",
    "YYYYNTAGG",
    "GGTCTC",
    "GAGACC",
)
XIAOPANG_SPECIES = "e_coli"
XIAOPANG_AVOID_KMERS = "8"
XIAOPANG_AVOID_KMERS_BOOST = "25"
XIAOPANG_OUTPUT_FILENAME = "xiaopang_translated.DNA.fasta"
logger = logging.getLogger(__name__)


def optimize_with_legacy_domesticator(
    records: dict[str, str],
    *,
    settings: Settings,
) -> dict[str, str]:
    if not records:
        return {}

    python_path, script_path, database_path = _configured_paths(settings)
    with tempfile.TemporaryDirectory(prefix="proteinhub-domesticator-") as temp_dir:
        work_dir = Path(temp_dir)
        input_path = work_dir / "xiaopang_input.pad.fasta"
        output_path = work_dir / XIAOPANG_OUTPUT_FILENAME
        _write_fasta(input_path, records)

        command = _xiaopang_command(
            python_path=python_path,
            script_path=script_path,
            input_path=input_path,
            output_path=output_path,
        )
        started_at = time.monotonic()
        logger.info(
            "Starting legacy domesticator for %s records with timeout %s seconds",
            len(records),
            settings.legacy_domesticator_timeout_seconds,
        )
        try:
            completed = _run_command(
                command,
                cwd=work_dir,
                env=_domesticator_env(database_path),
                timeout=settings.legacy_domesticator_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            detail = _process_output_detail(exc.stdout, exc.stderr)
            message = (
                "Legacy domesticator timed out after "
                f"{settings.legacy_domesticator_timeout_seconds} seconds"
            )
            if detail:
                message = f"{message}: {detail}"
            raise ExternalToolError(message) from exc
        except OSError as exc:
            raise ExternalToolError("Legacy domesticator could not be started") from exc

        elapsed_seconds = time.monotonic() - started_at
        logger.info(
            "Legacy domesticator finished in %.1f seconds for %s records",
            elapsed_seconds,
            len(records),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            message = "Legacy domesticator failed"
            if detail:
                message = f"{message}: {detail[-500:]}"
            raise ExternalToolError(message)
        if not output_path.exists():
            raise ExternalToolError("Legacy domesticator did not write DNA FASTA")

        optimized = _read_fasta(output_path)
        _validate_output_records(input_ids=set(records), output_ids=set(optimized))
        _validate_dna_translations(input_records=records, optimized_records=optimized)
        return optimized


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=(os.name == "posix"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout = exc.stdout
            stderr = exc.stderr
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=timeout,
            output=stdout,
            stderr=stderr,
        ) from exc
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )


def _kill_process_tree(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
    process.kill()


def _process_output_detail(
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> str:
    parts = []
    for label, value in (("stderr", stderr), ("stdout", stdout)):
        if value is None:
            continue
        if isinstance(value, bytes):
            text = value.decode(errors="replace")
        else:
            text = value
        text = text.strip()
        if text:
            parts.append(f"{label}: {text[-500:]}")
    return "; ".join(parts)


def _configured_paths(settings: Settings) -> tuple[Path, Path, Path]:
    python_path = settings.legacy_domesticator_python
    script_path = settings.legacy_domesticator_script
    database_path = settings.legacy_domesticator_database
    if python_path is None:
        raise ConfigurationError("Legacy domesticator Python is not configured")
    if script_path is None:
        raise ConfigurationError("Legacy domesticator script is not configured")
    if database_path is None:
        raise ConfigurationError("Legacy domesticator database is not configured")
    if not python_path.exists():
        raise ConfigurationError("Legacy domesticator Python does not exist")
    if not script_path.exists():
        raise ConfigurationError("Legacy domesticator script does not exist")
    if not database_path.is_dir():
        raise ConfigurationError("Legacy domesticator database does not exist")
    return python_path, script_path, database_path


def _xiaopang_command(
    *,
    python_path: Path,
    script_path: Path,
    input_path: Path,
    output_path: Path,
) -> list[str]:
    return [
        str(python_path),
        str(script_path),
        str(input_path),
        "--avoid_restriction_sites",
        *XIAOPANG_RESTRICTION_SITES,
        "--avoid_patterns",
        *XIAOPANG_AVOID_PATTERNS,
        "--species",
        XIAOPANG_SPECIES,
        "--avoid_kmers",
        XIAOPANG_AVOID_KMERS,
        "--avoid_kmers_boost",
        XIAOPANG_AVOID_KMERS_BOOST,
        "--output_mode",
        "fasta",
        "--output_filename",
        str(output_path),
    ]


def _domesticator_env(database_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_parts = [str(database_path)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["DOMESTICATOR_DATABASE"] = str(database_path)
    return env


def _write_fasta(path: Path, records: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record_id, sequence in records.items():
            if not record_id or any(character.isspace() for character in record_id):
                raise ExternalToolError("Legacy domesticator record ids must not contain spaces")
            handle.write(f">{record_id}\n")
            handle.write(f"{sequence}\n")


def _read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    current_id = ""
    sequence_lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id:
                records[current_id] = "".join(sequence_lines).upper()
            current_id = line[1:].split()[0]
            sequence_lines = []
            continue
        sequence_lines.append(line)
    if current_id:
        records[current_id] = "".join(sequence_lines).upper()
    return records


def _validate_output_records(*, input_ids: set[str], output_ids: set[str]) -> None:
    missing = input_ids - output_ids
    extra = output_ids - input_ids
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing: {', '.join(sorted(missing)[:5])}")
        if extra:
            details.append(f"extra: {', '.join(sorted(extra)[:5])}")
        raise ExternalToolError(
            "Legacy domesticator output records do not match input records"
            + (f" ({'; '.join(details)})" if details else "")
        )


def _validate_dna_translations(
    *,
    input_records: dict[str, str],
    optimized_records: dict[str, str],
) -> None:
    failures = []
    for record_id, expected_sequence in input_records.items():
        expected_protein = _normalize_protein_sequence(expected_sequence)
        dna_sequence = optimized_records[record_id]
        try:
            observed_protein = _translate_dna_sequence(dna_sequence)
        except ValueError as exc:
            failures.append(f"{record_id}: {exc}")
            continue
        if observed_protein != expected_protein:
            failures.append(
                f"{record_id}: expected {_short_sequence(expected_protein)}, "
                f"got {_short_sequence(observed_protein)}"
            )

    if failures:
        shown = "; ".join(failures[:5])
        suffix = f"; and {len(failures) - 5} more" if len(failures) > 5 else ""
        raise ExternalToolError(
            f"Legacy domesticator DNA verification failed: {shown}{suffix}"
        )


def _translate_dna_sequence(sequence: str) -> str:
    normalized = _normalize_dna_sequence(sequence)
    if len(normalized) % 3 != 0:
        raise ValueError("DNA length is not divisible by 3")
    invalid_characters = sorted(set(normalized) - {"A", "C", "G", "T"})
    if invalid_characters:
        raise ValueError(f"DNA contains invalid bases: {''.join(invalid_characters)}")
    return str(Seq(normalized).translate())


def _normalize_protein_sequence(sequence: str) -> str:
    return "".join(sequence.upper().split())


def _normalize_dna_sequence(sequence: str) -> str:
    return "".join(sequence.upper().replace("U", "T").split())


def _short_sequence(sequence: str) -> str:
    if len(sequence) <= 24:
        return sequence
    return f"{sequence[:12]}...{sequence[-6:]}"
