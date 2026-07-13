from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class MemberCreateRequest(BaseModel):
    email: str
    role: str = "member"
    discipline: str = "other"


class MemberUpdateRequest(BaseModel):
    role: str = "member"
    discipline: str = "other"


class ProteinCreateRequest(BaseModel):
    name: str
    sequence: str
    description: str = ""
    version_tag: str = ""


class BatchCreateRequest(BaseModel):
    name: str
    protein_ids: list[int]
    description: str = ""
    plate_format: str = "96"


class ExperimentCreateRequest(BaseModel):
    experiment_type: str
    name: str
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ExperimentWellResultUpdateRequest(BaseModel):
    result_value: str = ""
    result_note: str = ""
