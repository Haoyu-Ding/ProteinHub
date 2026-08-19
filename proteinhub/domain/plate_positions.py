from __future__ import annotations

import re

from proteinhub.domain.errors import DomainError


PLATE_96_POSITIONS = tuple(
    f"{row}{column:02d}" for row in "ABCDEFGH" for column in range(1, 13)
)
_PLATE_POSITION_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-H])(0?[1-9]|1[0-2])(?=$|[^A-Za-z0-9])",
    re.IGNORECASE,
)
_LETTER_SUFFIX_POSITION_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-H])(0?[1-9]|[1-9][0-9]?)(?=$|[^0-9])",
    re.IGNORECASE,
)


def extract_unique_plate_position(
    value: str,
    *,
    label: str,
    allow_linear_a_labels: bool = False,
    allow_letter_suffix: bool = False,
) -> str:
    text = value.strip()
    pattern = (
        _LETTER_SUFFIX_POSITION_TOKEN_RE
        if allow_letter_suffix or allow_linear_a_labels
        else _PLATE_POSITION_TOKEN_RE
    )
    positions = {
        position
        for match in pattern.finditer(text)
        if (position := _position_from_match(match, allow_linear_a_labels))
    }
    if not positions:
        raise DomainError(f"{label} must include a well position like A1 or A01")
    if len(positions) > 1:
        raise DomainError(
            f"{label} includes multiple well positions: {', '.join(sorted(positions))}"
        )
    return positions.pop()


def _position_from_match(
    match: re.Match[str],
    allow_linear_a_labels: bool,
) -> str | None:
    row = match.group(1).upper()
    column_number = int(match.group(2))
    if 1 <= column_number <= 12:
        return f"{row}{column_number:02d}"
    if (
        allow_linear_a_labels
        and row == "A"
        and column_number <= len(PLATE_96_POSITIONS)
    ):
        return PLATE_96_POSITIONS[column_number - 1]
    return None
