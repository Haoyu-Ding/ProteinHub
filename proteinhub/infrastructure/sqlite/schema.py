from __future__ import annotations


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_id INTEGER NOT NULL REFERENCES proteins(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sequence TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version_tag TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'designed', 'ready_for_synthesis', 'synthesizing', 'testing', 'validated', 'failed')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
    assigned_to INTEGER REFERENCES users(id),
    discipline_owner TEXT NOT NULL DEFAULT '' CHECK (discipline_owner IN ('', 'design', 'synthesis', 'assay', 'other')),
    design_rationale TEXT NOT NULL DEFAULT '',
    handoff_note TEXT NOT NULL DEFAULT '',
    risk_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS sequence_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


MIGRATIONS = [
    (
        "project_members",
        "discipline",
        "ALTER TABLE project_members ADD COLUMN discipline TEXT NOT NULL DEFAULT 'other' CHECK (discipline IN ('design', 'synthesis', 'assay', 'other'))",
    ),
    (
        "sequences",
        "status",
        "ALTER TABLE sequences ADD COLUMN status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'designed', 'ready_for_synthesis', 'synthesizing', 'testing', 'validated', 'failed'))",
    ),
    (
        "sequences",
        "priority",
        "ALTER TABLE sequences ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high'))",
    ),
    (
        "sequences",
        "assigned_to",
        "ALTER TABLE sequences ADD COLUMN assigned_to INTEGER REFERENCES users(id)",
    ),
    (
        "sequences",
        "discipline_owner",
        "ALTER TABLE sequences ADD COLUMN discipline_owner TEXT NOT NULL DEFAULT '' CHECK (discipline_owner IN ('', 'design', 'synthesis', 'assay', 'other'))",
    ),
    (
        "sequences",
        "design_rationale",
        "ALTER TABLE sequences ADD COLUMN design_rationale TEXT NOT NULL DEFAULT ''",
    ),
    (
        "sequences",
        "handoff_note",
        "ALTER TABLE sequences ADD COLUMN handoff_note TEXT NOT NULL DEFAULT ''",
    ),
    (
        "sequences",
        "risk_note",
        "ALTER TABLE sequences ADD COLUMN risk_note TEXT NOT NULL DEFAULT ''",
    ),
    (
        "sequences",
        "updated_at",
        "ALTER TABLE sequences ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
    ),
]
