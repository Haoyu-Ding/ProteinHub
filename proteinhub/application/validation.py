from __future__ import annotations

from proteinhub.domain.errors import DomainError


def required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise DomainError(f"{field_name} is required")
    return cleaned

