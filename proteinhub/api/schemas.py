from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
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


class ProteinCreateRequest(BaseModel):
    name: str
    description: str = ""


class SequenceCreateRequest(BaseModel):
    name: str
    sequence: str
    description: str = ""
    version_tag: str = ""

