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


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


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
    protein_type: str = "TCR"
    target: str = ""


class BatchCreateRequest(BaseModel):
    name: str
    protein_ids: list[int]
    description: str = ""
    plate_format: str = "96"
    start_position: str = "A01"


class BatchWellPositionUpdateRequest(BaseModel):
    position: str
    mode: str = "move"


class BatchOrderStatusUpdateRequest(BaseModel):
    order_status: str


class BatchTranslationRequest(BaseModel):
    padding: bool = False
    add_additional_w: bool = False
    organism: str = "E. coli"
    backbone: str = "5"
    resistance: str = "Amp"


class ExperimentCreateRequest(BaseModel):
    experiment_type: str
    name: str
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ExperimentWellResultUpdateRequest(BaseModel):
    result_value: str = ""
    result_note: str = ""


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    created_at: str
    role: str


class ProjectMemberResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    discipline: str
    created_at: str


class ProjectDetailResponse(BaseModel):
    project: ProjectResponse
    members: list[ProjectMemberResponse]


class ProteinResponse(BaseModel):
    id: int
    project_id: int
    name: str
    protein_name: str
    sequence: str
    description: str
    protein_type: str
    target: str
    structure_filename: str
    structure_mime_type: str
    structure_size_bytes: int
    structure_storage_path: str
    created_at: str
    updated_at: str


class ProjectProteinResponse(ProteinResponse):
    artifact_count: int


class StructureSequenceResponse(BaseModel):
    filename: str
    sequence: str
    length: int
    source: str
    chain_id: str
    entity_id: str
    sequence_count: int


class ArtifactResponse(BaseModel):
    id: int
    protein_id: int
    uploaded_by: int
    filename: str
    artifact_type: str
    mime_type: str
    size_bytes: int
    storage_path: str
    is_deleted: int
    created_at: str
    deleted_at: str | None
    uploaded_by_name: str
    uploaded_by_email: str


class BatchResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    plate_format: str
    order_status: str
    translation_padding: bool = False
    translation_additional_w: bool = False
    translation_organism: str = ""
    translation_backbone: str = ""
    translation_resistance: str = ""
    created_by: int
    created_at: str
    updated_at: str
    created_by_name: str
    created_by_email: str


class BatchSummaryResponse(BatchResponse):
    well_count: int
    experiment_count: int
    result_count: int


class BatchWellResponse(BaseModel):
    id: int
    batch_id: int
    protein_id: int
    position: str
    source_aa_sequence: str
    translated_aa_sequence: str
    dna_sequence: str
    created_at: str
    updated_at: str
    protein_name: str
    protein_sequence: str
    protein_type: str


class ExperimentResponse(BaseModel):
    id: int
    batch_id: int
    experiment_type: str
    name: str
    description: str
    created_by: int
    created_at: str
    updated_at: str
    created_by_name: str
    created_by_email: str
    details: dict[str, Any]


class ExperimentSummaryResponse(ExperimentResponse):
    result_count: int


class ExperimentWellResultResponse(BaseModel):
    well_id: int
    position: str
    protein_id: int
    protein_name: str
    protein_sequence: str
    protein_type: str
    result_id: int | None
    result_value: str
    result_note: str
    result_updated_at: str | None


class BatchDetailResponse(BaseModel):
    batch: BatchResponse
    wells: list[BatchWellResponse]
    experiments: list[ExperimentSummaryResponse]


class BatchTranslationSequenceResponse(BaseModel):
    well_id: int
    position: str
    protein_id: int
    protein_name: str
    source_aa_sequence: str
    translated_aa_sequence: str
    dna_sequence: str


class BatchTranslationResponse(BaseModel):
    padding: bool
    add_additional_w: bool
    organism: str
    backbone: str
    resistance: str
    sequences: list[BatchTranslationSequenceResponse]
    dna_fasta: str


class ExperimentDetailResponse(BaseModel):
    experiment: ExperimentResponse
    results: list[ExperimentWellResultResponse]


class ProteinBatchResultResponse(BaseModel):
    id: int
    experiment_id: int
    well_id: int
    result_value: str
    result_note: str
    created_at: str
    updated_at: str
    position: str
    protein_id: int
    batch_id: int
    batch_name: str
    plate_format: str
    project_id: int
    experiment_name: str
    experiment_type: str


class ProteinDetailResponse(BaseModel):
    protein: ProteinResponse
    artifacts: list[ArtifactResponse]
    batch_results: list[ProteinBatchResultResponse]
