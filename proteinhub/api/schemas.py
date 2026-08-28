from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    database_backend: str
    storage: str
    artifact_storage_backend: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    global_role: str = "user"
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class ProjectStatusUpdateRequest(BaseModel):
    status: str


class MemberCreateRequest(BaseModel):
    email: str
    role: str = "member"


class MemberUpdateRequest(BaseModel):
    role: str = "member"


class ProteinCreateRequest(BaseModel):
    name: str
    sequence: str
    description: str = ""
    protein_type: str = "TCR"
    target: str = ""
    allow_high_similarity: bool = False


class PublicProteinCreateRequest(BaseModel):
    name: str
    sequence: str
    description: str = ""
    protein_type: str = ""
    target: str = ""


class PublicProteinUpdateRequest(PublicProteinCreateRequest):
    pass


class ProteinManualRatingUpdateRequest(BaseModel):
    manual_rating: str = "unrated"


class ProteinSequenceCheckItemRequest(BaseModel):
    name: str
    sequence: str


class ProteinSequenceCheckRequest(BaseModel):
    items: list[ProteinSequenceCheckItemRequest]
    similarity_threshold: float = 0.9


class ProteinSequenceMatchResponse(BaseModel):
    protein_id: int | None
    protein_name: str
    scope: str
    match_type: str
    identity: float
    alignment_length: int


class ProteinSequenceCheckItemResponse(BaseModel):
    name: str
    sequence: str
    sequence_length: int
    matches: list[ProteinSequenceMatchResponse]
    has_duplicate: bool
    has_high_similarity: bool


class ProteinSequenceCheckResponse(BaseModel):
    items: list[ProteinSequenceCheckItemResponse]
    has_blocking_duplicates: bool
    has_warnings: bool
    similarity_threshold: float


class ProjectProteinScoreImportResponse(BaseModel):
    matched_count: int
    skipped_count: int
    skipped_names: list[str] = Field(default_factory=list)


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
    receipt_note: str | None = None
    received_well_ids: list[int] | None = None


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


class ExperimentRawFileResponse(BaseModel):
    id: int
    experiment_id: int
    uploaded_by: int
    well_id: int | None
    filename: str
    raw_file_type: str
    mime_type: str
    size_bytes: int
    content_sha256: str
    created_at: str
    position: str | None = None
    protein_id: int | None = None
    protein_name: str | None = None
    uploaded_by_name: str
    uploaded_by_email: str


class ProjectMemberSummaryResponse(BaseModel):
    id: int
    name: str
    email: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    status: str
    owner_id: int
    owner_name: str = ""
    owner_email: str = ""
    members: list[ProjectMemberSummaryResponse] = Field(default_factory=list)
    member_count: int = 0
    created_at: str
    role: str


class ProjectMemberResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
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
    manual_rating: str = "unrated"
    score_details: dict[str, Any] = Field(default_factory=dict)
    sequence_similarity_status: str = ""
    sequence_similarity_matches: list[ProteinSequenceMatchResponse] = Field(default_factory=list)
    structure_filename: str
    structure_mime_type: str
    structure_size_bytes: int
    structure_storage_path: str
    structure_deposit_date: str = ""
    effective_date: str = ""
    effective_date_source: str = ""
    created_at: str
    updated_at: str


class ProjectProteinResponse(ProteinResponse):
    artifact_count: int


class ProteinStructureImportResponse(BaseModel):
    proteins: list[ProteinResponse]
    score_import: ProjectProteinScoreImportResponse


class PublicProteinResponse(BaseModel):
    id: int
    project_id: int
    project_name: str = ""
    project_status: str = "active"
    name: str
    sequence: str
    description: str
    protein_type: str
    target: str
    created_by: int
    created_by_name: str
    created_by_email: str
    created_at: str
    updated_at: str


class PublicProteinDetailResponse(BaseModel):
    public_protein: PublicProteinResponse
    access_role: str = ""


class AdminSequenceSearchResultResponse(BaseModel):
    source_type: str
    protein_id: int | None = None
    public_protein_id: int | None = None
    project_id: int
    project_name: str
    project_status: str
    name: str
    sequence: str
    sequence_length: int
    protein_type: str
    target: str
    updated_at: str
    batch_count: int = 0
    detail_path: str


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
    ordered_at: str = ""
    receipt_note: str = ""
    receipt_updated_by: int | None = None
    receipt_updated_at: str = ""
    receipt_updated_by_name: str = ""
    receipt_updated_by_email: str = ""
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
    received_well_count: int = 0
    experiment_count: int
    result_count: int


class OrderMonitorSummaryResponse(BaseModel):
    total_ordered_batches: int
    total_ordered_proteins: int
    last_ordered_at: str
    days_since_last_order: int | None
    cadence_target_days: int
    cadence_status: str
    cadence_text: str


class WeeklyOrderResponse(BaseModel):
    week_start: str
    week_label: str
    order_count: int
    ordered_count: int
    partially_received_count: int
    fully_received_count: int
    protein_count: int
    batch_ids: list[int]


class OrderMonitorOwnerRankResponse(BaseModel):
    owner_id: int
    owner_name: str
    owner_email: str
    batch_count: int
    protein_count: int


class OrderMonitorBatchResponse(BaseModel):
    id: int
    project_id: int
    project_name: str
    owner_id: int
    owner_name: str
    owner_email: str
    name: str
    description: str
    plate_format: str
    order_status: str
    ordered_at: str
    ordered_week: str
    days_since_order: int | None
    well_count: int
    received_well_count: int = 0
    receipt_progress_percent: float = 0
    created_at: str
    updated_at: str
    created_by_name: str
    created_by_email: str


class OrderMonitorResponse(BaseModel):
    summary: OrderMonitorSummaryResponse
    weekly_orders: list[WeeklyOrderResponse]
    range_start: str
    range_end: str
    batches: list[OrderMonitorBatchResponse]
    owner_rankings: dict[str, list[OrderMonitorOwnerRankResponse]] = Field(
        default_factory=dict
    )
    batch_receipt_progress: list[OrderMonitorBatchResponse] = Field(
        default_factory=list
    )


class BatchScoreDensityPlotResponse(BaseModel):
    metric: str
    label: str
    sample_count: int
    svg: str


class BatchWellResponse(BaseModel):
    id: int
    batch_id: int
    protein_id: int
    position: str
    source_aa_sequence: str
    translated_aa_sequence: str
    dna_sequence: str
    received_at: str = ""
    received_by: int | None = None
    created_at: str
    updated_at: str
    received_by_name: str = ""
    received_by_email: str = ""
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
    score_density_plots: list[BatchScoreDensityPlotResponse] = Field(default_factory=list)
    access_role: str = ""


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
    access_role: str = ""


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
    access_role: str = ""
