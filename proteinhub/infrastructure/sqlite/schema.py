from __future__ import annotations


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    global_role TEXT NOT NULL DEFAULT 'user' CHECK (global_role IN ('admin', 'user')),
    is_active INTEGER NOT NULL DEFAULT 1,
    disabled_at TEXT NOT NULL DEFAULT '',
    disabled_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    disabled_reason TEXT NOT NULL DEFAULT '',
    last_login_at TEXT NOT NULL DEFAULT '',
    password_updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'trash')),
    owner_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
    discipline TEXT NOT NULL DEFAULT 'other' CHECK (discipline IN ('design', 'synthesis', 'assay', 'other')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS proteins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
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
    structure_size_bytes INTEGER NOT NULL DEFAULT 0,
    structure_storage_path TEXT NOT NULL DEFAULT '',
    structure_storage_backend TEXT NOT NULL DEFAULT 'filesystem' CHECK (structure_storage_backend IN ('filesystem', 'database')),
    structure_content BLOB,
    structure_content_sha256 TEXT NOT NULL DEFAULT '',
    structure_deposit_date TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public_proteins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sequence TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    protein_type TEXT NOT NULL DEFAULT '',
    target TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    plate_format TEXT NOT NULL DEFAULT '96' CHECK (plate_format IN ('96')),
    order_status TEXT NOT NULL DEFAULT 'not_ordered' CHECK (order_status IN ('not_ordered', 'ordered', 'partially_received', 'fully_received')),
    ordered_at TEXT NOT NULL DEFAULT '',
    receipt_note TEXT NOT NULL DEFAULT '',
    receipt_updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    receipt_updated_at TEXT NOT NULL DEFAULT '',
    translation_padding INTEGER NOT NULL DEFAULT 0,
    translation_additional_w INTEGER NOT NULL DEFAULT 0,
    translation_organism TEXT NOT NULL DEFAULT '',
    translation_backbone TEXT NOT NULL DEFAULT '',
    translation_resistance TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_member_batch_access (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id, batch_id),
    FOREIGN KEY (project_id, user_id)
        REFERENCES project_members(project_id, user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS batch_wells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    position TEXT NOT NULL,
    source_aa_sequence TEXT NOT NULL DEFAULT '',
    translated_aa_sequence TEXT NOT NULL DEFAULT '',
    dna_sequence TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    received_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (batch_id, position)
);

CREATE TABLE IF NOT EXISTS batch_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    experiment_type TEXT NOT NULL CHECK (experiment_type IN ('FPLC', 'SPR', 'HPLC', 'AKTA')),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fplc_experiments (
    experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS spr_experiments (
    experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS hplc_experiments (
    experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS akta_experiments (
    experiment_id INTEGER PRIMARY KEY REFERENCES batch_experiments(id) ON DELETE CASCADE,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS experiment_well_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL REFERENCES batch_experiments(id) ON DELETE CASCADE,
    well_id INTEGER NOT NULL REFERENCES batch_wells(id) ON DELETE CASCADE,
    result_value TEXT NOT NULL DEFAULT '',
    result_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (experiment_id, well_id)
);

CREATE TABLE IF NOT EXISTS experiment_raw_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL REFERENCES batch_experiments(id) ON DELETE CASCADE,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    well_id INTEGER REFERENCES batch_wells(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    raw_file_type TEXT NOT NULL DEFAULT 'source',
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL,
    content BLOB NOT NULL,
    content_sha256 TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    artifact_type TEXT NOT NULL DEFAULT 'file',
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'filesystem' CHECK (storage_backend IN ('filesystem', 'database')),
    content BLOB,
    content_sha256 TEXT NOT NULL DEFAULT '',
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
CREATE INDEX IF NOT EXISTS idx_project_member_batch_access_user
    ON project_member_batch_access(project_id, user_id);
CREATE INDEX IF NOT EXISTS idx_project_member_batch_access_batch
    ON project_member_batch_access(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_experiments_batch
    ON batch_experiments(batch_id);
CREATE INDEX IF NOT EXISTS idx_experiment_well_results_experiment
    ON experiment_well_results(experiment_id);
"""

BASELINE_MIGRATION = "0001_current_schema"


MIGRATIONS = [
    (
        "users",
        "name",
        "ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''",
    ),
    (
        "users",
        "global_role",
        "ALTER TABLE users ADD COLUMN global_role TEXT NOT NULL DEFAULT 'user' CHECK (global_role IN ('admin', 'user'))",
    ),
    (
        "users",
        "is_active",
        "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
    ),
    (
        "users",
        "disabled_at",
        "ALTER TABLE users ADD COLUMN disabled_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "users",
        "disabled_by",
        "ALTER TABLE users ADD COLUMN disabled_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
    ),
    (
        "users",
        "disabled_reason",
        "ALTER TABLE users ADD COLUMN disabled_reason TEXT NOT NULL DEFAULT ''",
    ),
    (
        "users",
        "last_login_at",
        "ALTER TABLE users ADD COLUMN last_login_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "users",
        "password_updated_at",
        "ALTER TABLE users ADD COLUMN password_updated_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "projects",
        "status",
        "ALTER TABLE projects ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'trash'))",
    ),
    (
        "project_members",
        "discipline",
        "ALTER TABLE project_members ADD COLUMN discipline TEXT NOT NULL DEFAULT 'other' CHECK (discipline IN ('design', 'synthesis', 'assay', 'other'))",
    ),
    (
        "proteins",
        "sequence",
        "ALTER TABLE proteins ADD COLUMN sequence TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "dna_sequence",
        "ALTER TABLE proteins ADD COLUMN dna_sequence TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "protein_type",
        "ALTER TABLE proteins ADD COLUMN protein_type TEXT NOT NULL DEFAULT 'TCR'",
    ),
    (
        "proteins",
        "target",
        "ALTER TABLE proteins ADD COLUMN target TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "manual_rating",
        "ALTER TABLE proteins ADD COLUMN manual_rating TEXT NOT NULL DEFAULT 'unrated' CHECK (manual_rating IN ('unrated', 'normal', 'rare', 'epic', 'legendary'))",
    ),
    (
        "proteins",
        "score_details_json",
        "ALTER TABLE proteins ADD COLUMN score_details_json TEXT NOT NULL DEFAULT '{}'",
    ),
    (
        "proteins",
        "sequence_similarity_status",
        "ALTER TABLE proteins ADD COLUMN sequence_similarity_status TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "sequence_similarity_matches_json",
        "ALTER TABLE proteins ADD COLUMN sequence_similarity_matches_json TEXT NOT NULL DEFAULT '[]'",
    ),
    (
        "proteins",
        "structure_filename",
        "ALTER TABLE proteins ADD COLUMN structure_filename TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "structure_mime_type",
        "ALTER TABLE proteins ADD COLUMN structure_mime_type TEXT NOT NULL DEFAULT 'application/octet-stream'",
    ),
    (
        "proteins",
        "structure_size_bytes",
        "ALTER TABLE proteins ADD COLUMN structure_size_bytes INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "proteins",
        "structure_storage_path",
        "ALTER TABLE proteins ADD COLUMN structure_storage_path TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "structure_storage_backend",
        "ALTER TABLE proteins ADD COLUMN structure_storage_backend TEXT NOT NULL DEFAULT 'filesystem' CHECK (structure_storage_backend IN ('filesystem', 'database'))",
    ),
    (
        "proteins",
        "structure_content",
        "ALTER TABLE proteins ADD COLUMN structure_content BLOB",
    ),
    (
        "proteins",
        "structure_content_sha256",
        "ALTER TABLE proteins ADD COLUMN structure_content_sha256 TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "structure_deposit_date",
        "ALTER TABLE proteins ADD COLUMN structure_deposit_date TEXT NOT NULL DEFAULT ''",
    ),
    (
        "proteins",
        "updated_at",
        "ALTER TABLE proteins ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batches",
        "order_status",
        "ALTER TABLE batches ADD COLUMN order_status TEXT NOT NULL DEFAULT 'not_ordered' CHECK (order_status IN ('not_ordered', 'ordered', 'partially_received', 'fully_received'))",
    ),
    (
        "batches",
        "ordered_at",
        "ALTER TABLE batches ADD COLUMN ordered_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batches",
        "receipt_note",
        "ALTER TABLE batches ADD COLUMN receipt_note TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batches",
        "receipt_updated_by",
        "ALTER TABLE batches ADD COLUMN receipt_updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
    ),
    (
        "batches",
        "receipt_updated_at",
        "ALTER TABLE batches ADD COLUMN receipt_updated_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batches",
        "translation_padding",
        "ALTER TABLE batches ADD COLUMN translation_padding INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "batches",
        "translation_additional_w",
        "ALTER TABLE batches ADD COLUMN translation_additional_w INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "batches",
        "translation_organism",
        "ALTER TABLE batches ADD COLUMN translation_organism TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batches",
        "translation_backbone",
        "ALTER TABLE batches ADD COLUMN translation_backbone TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batches",
        "translation_resistance",
        "ALTER TABLE batches ADD COLUMN translation_resistance TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batch_wells",
        "source_aa_sequence",
        "ALTER TABLE batch_wells ADD COLUMN source_aa_sequence TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batch_wells",
        "translated_aa_sequence",
        "ALTER TABLE batch_wells ADD COLUMN translated_aa_sequence TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batch_wells",
        "dna_sequence",
        "ALTER TABLE batch_wells ADD COLUMN dna_sequence TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batch_wells",
        "received_at",
        "ALTER TABLE batch_wells ADD COLUMN received_at TEXT NOT NULL DEFAULT ''",
    ),
    (
        "batch_wells",
        "received_by",
        "ALTER TABLE batch_wells ADD COLUMN received_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
    ),
    (
        "artifacts",
        "protein_id",
        "ALTER TABLE artifacts ADD COLUMN protein_id INTEGER REFERENCES proteins(id)",
    ),
    (
        "artifacts",
        "storage_backend",
        "ALTER TABLE artifacts ADD COLUMN storage_backend TEXT NOT NULL DEFAULT 'filesystem' CHECK (storage_backend IN ('filesystem', 'database'))",
    ),
    (
        "artifacts",
        "content",
        "ALTER TABLE artifacts ADD COLUMN content BLOB",
    ),
    (
        "artifacts",
        "content_sha256",
        "ALTER TABLE artifacts ADD COLUMN content_sha256 TEXT NOT NULL DEFAULT ''",
    ),
    (
        "experiment_raw_files",
        "well_id",
        "ALTER TABLE experiment_raw_files ADD COLUMN well_id INTEGER REFERENCES batch_wells(id) ON DELETE SET NULL",
    ),
]
