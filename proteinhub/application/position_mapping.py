from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from proteinhub.application.validation import required
from proteinhub.domain.errors import DomainError
from proteinhub.domain.plate_positions import (
    PLATE_96_POSITIONS,
    extract_unique_plate_position,
)


@dataclass(frozen=True)
class PositionMapping:
    filename: str
    content_type: str
    content: bytes
    result_to_batch: dict[str, str]

    def batch_position_for(self, result_position: str) -> str | None:
        return self.result_to_batch.get(result_position)

    def entries(self) -> list[dict[str, str]]:
        return [
            {"result_position": result_position, "batch_position": batch_position}
            for result_position, batch_position in self.result_to_batch.items()
        ]

    def details_for(
        self,
        *,
        used_result_positions: set[str],
        skipped_result_positions: set[str],
        observed_result_positions: set[str] | None = None,
    ) -> dict:
        observed_positions = observed_result_positions or used_result_positions
        return {
            "position_mapping_filename": self.filename,
            "position_mapping": self.entries(),
            "mapped_positions": [
                {
                    "result_position": result_position,
                    "batch_position": self.result_to_batch[result_position],
                }
                for result_position in sorted(used_result_positions)
                if result_position in self.result_to_batch
            ],
            "skipped_result_positions": sorted(skipped_result_positions),
            "unused_mapping_positions": [
                result_position
                for result_position in self.result_to_batch
                if result_position not in observed_positions
            ],
        }


def parse_position_mapping_file(
    mapping_file: tuple[str, str, bytes] | None,
) -> PositionMapping | None:
    if mapping_file is None:
        return None

    filename, content_type, content = mapping_file
    file_name = required(
        Path(filename.replace("\\", "/")).name,
        "Position mapping filename",
    )
    if not file_name.lower().endswith(".csv"):
        raise DomainError("Position mapping must be a CSV file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainError("Position mapping must be UTF-8 CSV") from exc

    reader = csv.reader(StringIO(text))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise DomainError("Position mapping must include a header row") from exc

    result_column = _required_column(headers, "result_position")
    batch_column = _required_column(headers, "batch_position")
    result_to_batch: dict[str, str] = {}
    seen_batch_positions: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        result_position = _cell_position(
            row,
            result_column,
            label=f"Position mapping row {row_number} result_position",
        )
        batch_position = _cell_position(
            row,
            batch_column,
            label=f"Position mapping row {row_number} batch_position",
        )
        if result_position in result_to_batch:
            raise DomainError(
                f"Duplicate position mapping result_position {result_position}"
            )
        if batch_position in seen_batch_positions:
            raise DomainError(
                f"Duplicate position mapping batch_position {batch_position}"
            )
        result_to_batch[result_position] = batch_position
        seen_batch_positions.add(batch_position)

    if not result_to_batch:
        raise DomainError("Position mapping must include at least one mapping row")

    return PositionMapping(
        filename=file_name,
        content_type=content_type,
        content=content,
        result_to_batch=result_to_batch,
    )


def require_mapping_batch_positions(
    mapping: PositionMapping | None,
    wells_by_position: dict[str, dict],
) -> None:
    if mapping is None:
        return
    missing_positions = [
        position
        for position in mapping.result_to_batch.values()
        if position not in wells_by_position
    ]
    if missing_positions:
        raise DomainError(
            "Position mapping batch_position does not exist in this batch: "
            f"{', '.join(sorted(missing_positions))}"
        )


def _required_column(headers: list[str], name: str) -> int:
    normalized_headers = [header.strip().lower() for header in headers]
    try:
        return normalized_headers.index(name)
    except ValueError as exc:
        raise DomainError(f"Position mapping must include a {name} column") from exc


def _cell_position(row: list[str], index: int, *, label: str) -> str:
    value = row[index] if index < len(row) else ""
    return _normalize_plate_position(value, label=label)


def _normalize_plate_position(value: str, *, label: str) -> str:
    position = extract_unique_plate_position(str(value), label=label)
    if position not in PLATE_96_POSITIONS:
        raise DomainError(f"{label} must be between A1 and H12")
    return position
