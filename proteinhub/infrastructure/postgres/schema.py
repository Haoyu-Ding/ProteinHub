from __future__ import annotations


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    global_role TEXT NOT NULL DEFAULT 'user' CHECK (global_role IN ('admin', 'user')),
    is_active INTEGER NOT NULL DEFAULT 1,
    disabled_at TEXT NOT NULL DEFAULT '',
    disabled_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    disabled_reason TEXT NOT NULL DEFAULT '',
    last_login_at TEXT NOT NULL DEFAULT '',
    password_updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS projects (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'trash')),
    owner_id BIGINT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
    discipline TEXT NOT NULL DEFAULT 'other' CHECK (discipline IN ('design', 'synthesis', 'assay', 'other')),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS proteins (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sequence TEXT NOT NULL,
    dna_sequence TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    protein_type TEXT NOT NULL DEFAULT 'TCR',
    target TEXT NOT NULL DEFAULT '',
    manual_rating TEXT NOT NULL DEFAULT 'unrated' CHECK (manual_rating IN ('unrated', 'normal', 'rare', 'epic', 'legendary')),
    score_details_json TEXT NOT NULL DEFAULT '{}',
    sequence_similarity_status TEXT NOT NULL DEFAULT '',
    sequence_similarity_matches_json TEXT NOT NULL DEFAULT '[]',
    structure_filename TEXT NOT NULL DEFAULT '',
    structure_mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    structure_size_bytes BIGINT NOT NULL DEFAULT 0,
    structure_storage_path TEXT NOT NULL DEFAULT '',
    structure_storage_backend TEXT NOT NULL DEFAULT 'database' CHECK (structure_storage_backend IN ('filesystem', 'database')),
    structure_content BYTEA,
    structure_content_sha256 TEXT NOT NULL DEFAULT '',
    structure_deposit_date TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS public_proteins (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sequence TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    protein_type TEXT NOT NULL DEFAULT '',
    target TEXT NOT NULL DEFAULT '',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS batches (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    plate_format TEXT NOT NULL DEFAULT '96' CHECK (plate_format IN ('96')),
    order_status TEXT NOT NULL DEFAULT 'not_ordered' CHECK (order_status IN ('not_ordered', 'ordered', 'partially_received', 'fully_received')),
    ordered_at TEXT NOT NULL DEFAULT '',
    receipt_note TEXT NOT NULL DEFAULT '',
    receipt_updated_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    receipt_updated_at TEXT NOT NULL DEFAULT '',
    translation_padding INTEGER NOT NULL DEFAULT 0,
    translation_additional_w INTEGER NOT NULL DEFAULT 0,
    translation_organism TEXT NOT NULL DEFAULT '',
    translation_backbone TEXT NOT NULL DEFAULT '',
    translation_resistance TEXT NOT NULL DEFAULT '',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS batch_wells (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    protein_id BIGINT NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    position TEXT NOT NULL,
    source_aa_sequence TEXT NOT NULL DEFAULT '',
    translated_aa_sequence TEXT NOT NULL DEFAULT '',
    dna_sequence TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    received_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    UNIQUE (batch_id, position)
);

CREATE TABLE IF NOT EXISTS batch_experiments (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    experiment_type TEXT NOT NULL CHECK (experiment_type IN ('FPLC', 'SPR', 'HPLC', 'AKTA')),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS fplc_experiments (
    experiment_id BIGINT PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS spr_experiments (
    experiment_id BIGINT PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS hplc_experiments (
    experiment_id BIGINT PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS akta_experiments (
    experiment_id BIGINT PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS experiment_well_results (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES batch_experiments(id) ON DELETE CASCADE,
    well_id BIGINT NOT NULL REFERENCES batch_wells(id) ON DELETE CASCADE,
    result_value TEXT NOT NULL DEFAULT '',
    result_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    UNIQUE (experiment_id, well_id)
);

CREATE TABLE IF NOT EXISTS experiment_raw_files (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES batch_experiments(id) ON DELETE CASCADE,
    uploaded_by BIGINT NOT NULL REFERENCES users(id),
    well_id BIGINT REFERENCES batch_wells(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    raw_file_type TEXT NOT NULL DEFAULT 'source',
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes BIGINT NOT NULL,
    content BYTEA NOT NULL,
    content_sha256 TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id BIGSERIAL PRIMARY KEY,
    protein_id BIGINT NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    uploaded_by BIGINT NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    artifact_type TEXT NOT NULL DEFAULT 'file',
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'database' CHECK (storage_backend IN ('filesystem', 'database')),
    content BYTEA,
    content_sha256 TEXT NOT NULL DEFAULT '',
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_proteins_project_created
    ON proteins(project_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_public_proteins_project_created
    ON public_proteins(project_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_artifacts_protein_deleted
    ON artifacts(protein_id, is_deleted);
CREATE INDEX IF NOT EXISTS idx_batches_project_created
    ON batches(project_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_batch_experiments_batch
    ON batch_experiments(batch_id);
CREATE INDEX IF NOT EXISTS idx_experiment_well_results_experiment
    ON experiment_well_results(experiment_id);
"""


BASELINE_MIGRATION = "0001_postgres_schema"


POSTGRES_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS disabled_at TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS disabled_by BIGINT REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS disabled_reason TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_updated_at TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'trash'))",
    "ALTER TABLE proteins ADD COLUMN IF NOT EXISTS structure_storage_backend TEXT NOT NULL DEFAULT 'database' CHECK (structure_storage_backend IN ('filesystem', 'database'))",
    "ALTER TABLE proteins ADD COLUMN IF NOT EXISTS structure_content BYTEA",
    "ALTER TABLE proteins ADD COLUMN IF NOT EXISTS structure_content_sha256 TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS storage_backend TEXT NOT NULL DEFAULT 'database' CHECK (storage_backend IN ('filesystem', 'database'))",
    "ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS content BYTEA",
    "ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS content_sha256 TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE experiment_raw_files ADD COLUMN IF NOT EXISTS well_id BIGINT REFERENCES batch_wells(id) ON DELETE SET NULL",
    "ALTER TABLE batches ADD COLUMN IF NOT EXISTS receipt_note TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE batches ADD COLUMN IF NOT EXISTS receipt_updated_by BIGINT REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE batches ADD COLUMN IF NOT EXISTS receipt_updated_at TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE batch_wells ADD COLUMN IF NOT EXISTS received_at TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE batch_wells ADD COLUMN IF NOT EXISTS received_by BIGINT REFERENCES users(id) ON DELETE SET NULL",
    """
    UPDATE batch_wells
    SET
        received_at = COALESCE(
            NULLIF(batches.receipt_updated_at, ''),
            NULLIF(batches.ordered_at, ''),
            (CURRENT_TIMESTAMP::text)
        ),
        received_by = batches.receipt_updated_by,
        updated_at = (CURRENT_TIMESTAMP::text)
    FROM batches
    WHERE batch_wells.batch_id = batches.id
      AND batches.order_status = 'fully_received'
      AND batch_wells.received_at = ''
    """,
]
