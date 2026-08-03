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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
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
    structure_filename TEXT NOT NULL DEFAULT '',
    structure_mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    structure_size_bytes INTEGER NOT NULL DEFAULT 0,
    structure_storage_path TEXT NOT NULL DEFAULT '',
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
    translation_padding INTEGER NOT NULL DEFAULT 0,
    translation_additional_w INTEGER NOT NULL DEFAULT 0,
    translation_organism TEXT NOT NULL DEFAULT '',
    translation_backbone TEXT NOT NULL DEFAULT '',
    translation_resistance TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_wells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    position TEXT NOT NULL,
    source_aa_sequence TEXT NOT NULL DEFAULT '',
    translated_aa_sequence TEXT NOT NULL DEFAULT '',
    dna_sequence TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    artifact_type TEXT NOT NULL DEFAULT 'file',
    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
);
"""

BASELINE_MIGRATION = "0001_current_schema"


MIGRATIONS = [
    (
        "users",
        "name",
        "ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''",
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
        "artifacts",
        "protein_id",
        "ALTER TABLE artifacts ADD COLUMN protein_id INTEGER REFERENCES proteins(id)",
    ),
]
