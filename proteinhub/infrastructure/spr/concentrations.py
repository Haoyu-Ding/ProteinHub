from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

from proteinhub.domain.errors import DomainError


def read_spr_concentration_csv(file: tuple[str, str, bytes]) -> dict[str, dict[str, str]]:
    filename, _content_type, content = file
    file_name = Path(filename.replace("\\", "/")).name
    if not file_name:
        raise DomainError("SPR concentration filename is required")
    if not file_name.lower().endswith(".csv"):
        raise DomainError("SPR concentration table must be a CSV file")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainError("SPR concentration table must be UTF-8 CSV") from exc

    reader = csv.reader(StringIO(text))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise DomainError("SPR concentration table must include a header row") from exc

    if not headers or not headers[0].strip():
        raise DomainError("SPR concentration table must include a protein name column")

    concentration_headers = [
        (index, header.strip())
        for index, header in enumerate(headers[1:], start=1)
        if header.strip()
    ]
    if not concentration_headers:
        raise DomainError("SPR concentration table must include concentration columns")

    concentrations_by_protein: dict[str, dict[str, str]] = {}
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        protein_name = row[0] if row else ""
        protein_key = _protein_key(protein_name)
        if not protein_key:
            continue
        if protein_key in concentrations_by_protein:
            raise DomainError(f"Duplicate SPR concentration row for {protein_name.strip()}")
        concentrations_by_protein[protein_key] = {
            header: row[index].strip() if index < len(row) else ""
            for index, header in concentration_headers
        }
    return concentrations_by_protein


def format_spr_concentration_text(concentrations: Mapping[str, str]) -> str:
    return " · ".join(
        f"{label}: {value}"
        for label, value in concentrations.items()
        if str(value).strip()
    )


def _protein_key(value: str) -> str:
    name = Path(value.strip().replace("\\", "/")).name
    return Path(name).stem.casefold()
