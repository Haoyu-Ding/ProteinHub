# ProteinHub

ProteinHub is a local MVP for protein-centered design work.

The fixed data hierarchy is:

```text
Project -> Protein -> Artifact
Project -> Batch -> Experiment -> BatchWell -> Protein
```

Each protein owns exactly one amino-acid sequence. Batches group project proteins into 96-well plate positions. Each batch can have multiple experiments, currently FPLC, SPR, HPLC, and AKTA imports, and each experiment maps results back through wells to proteins. Artifacts manage protein-attached files. Experiment raw files keep shared or per-well source uploads such as SPR PPTX, SPR concentration CSV, HPLC chromatogram CSV, and HPLC `vial_fc.csv`. SQLite remains the local development database. Server deployments can use PostgreSQL, where uploaded artifact bytes and protein structure files are stored directly in database rows by default. Permissions are enforced at the Project level with JWT authentication.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python main.py
```

Then open the NiceGUI URL printed in the terminal, usually `http://127.0.0.1:8080`.

For PostgreSQL deployments, configure a database URL before startup:

```bash
export PROTEINHUB_DATABASE_URL=postgresql://proteinhub:password@localhost:5432/proteinhub
export PROTEINHUB_ARTIFACT_STORAGE_BACKEND=database
```

When `PROTEINHUB_DATABASE_URL` is set, `PROTEINHUB_ARTIFACT_STORAGE_BACKEND`
defaults to `database`. Leave it unset for local SQLite development.

Batch labels generate a 50 x 30 mm SVG with a QR code to the batch detail page.
Configure the externally reachable base URL before printing labels:

```bash
export PROTEINHUB_PUBLIC_BASE_URL=http://10.6.108.62
```

Batch DNA translation shells out to the legacy xiaopang/domesticator workflow.
ProteinHub auto-discovers `~/Downloads/domesticator.py`,
`~/Documents/SMARTS_intern/database`, and common `envs/trans/bin/python` paths.
If the legacy Python environment is elsewhere, configure it before using the
translation button:

```bash
export PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON=/home/yuguo/software/miniconda3/envs/trans/bin/python
```

AKTA result imports shell out to `akta_hap.py` and expect zip filenames
that are well positions such as `A01.zip`. ProteinHub auto-discovers
`~/Documents/SMARTS_intern/LJW-AKTAResults/akta_hap.py`. If its Python
environment is elsewhere, configure it before importing AKTA results:

```bash
export PROTEINHUB_AKTA_HAP_PYTHON=/path/to/akta/python
```

## Code layout

ProteinHub keeps framework, business, and infrastructure concerns separate:

- `proteinhub/api/` defines FastAPI routes, request schemas, and request-scoped dependencies.
- `proteinhub/application/` coordinates business rules such as authentication, permissions, projects, proteins, batches, and artifacts.
- `proteinhub/domain/` contains domain-level errors and shared domain concepts.
- `proteinhub/infrastructure/database/` chooses the configured database backend.
- `proteinhub/infrastructure/sqlite/` owns SQLite schema and repository queries.
- `proteinhub/infrastructure/postgres/` owns PostgreSQL connection and schema setup.
- `proteinhub/infrastructure/storage/` owns file storage adapters and safe artifact paths.
- `proteinhub/ui/` defines NiceGUI pages and browser helpers that talk to the backend only through `/api/...`.

The legacy modules `proteinhub.db`, `proteinhub.storage`, and `proteinhub.services` remain as compatibility exports for existing imports and tests.

Detailed project standards live in:

- `docs/architecture.md`
- `docs/development.md`
- `docs/deploy.md`
- `AGENTS.md`

## API

- `GET /api/health`
- `POST /api/auth/login`
- `GET /api/me`
- `GET /api/admin/sequences`
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PATCH /api/admin/users/{target_user_id}`
- `POST /api/admin/users/{target_user_id}/disable`
- `POST /api/admin/users/{target_user_id}/enable`
- `POST /api/admin/users/{target_user_id}/reset-password`
- `GET /api/projects`
- `POST /api/projects`
- `PATCH /api/projects/{project_id}/status`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/member-candidates`
- `POST /api/projects/{project_id}/members`
- `PATCH /api/projects/{project_id}/members/{member_user_id}`
- `GET /api/projects/{project_id}/proteins`
- `POST /api/projects/{project_id}/proteins`
- `POST /api/projects/{project_id}/proteins/sequence-check`
- `POST /api/projects/{project_id}/proteins/with-structure`
- `POST /api/projects/{project_id}/proteins/import-structures`
- `POST /api/projects/{project_id}/proteins/parse-structure`
- `GET /api/projects/{project_id}/public-proteins`
- `POST /api/projects/{project_id}/public-proteins`
- `PATCH /api/projects/{project_id}/public-proteins/{public_protein_id}`
- `DELETE /api/projects/{project_id}/public-proteins/{public_protein_id}`
- `GET /api/projects/{project_id}/batches`
- `POST /api/projects/{project_id}/batches`
- `GET /api/public-proteins/{public_protein_id}`
- `GET /api/proteins/{protein_id}`
- `PATCH /api/proteins/{protein_id}/manual-rating`
- `POST /api/proteins/{protein_id}/parse-structure`
- `GET /api/proteins/{protein_id}/structure/download`
- `GET /api/proteins/{protein_id}/artifacts`
- `POST /api/proteins/{protein_id}/artifacts`
- `GET /api/batches/{batch_id}`
- `PATCH /api/batches/{batch_id}/status`
- `PATCH /api/batches/{batch_id}/wells/{well_id}/position`
- `GET /api/batches/{batch_id}/plate/export`
- `GET /api/batches/{batch_id}/summary/export`
- `GET /api/batches/{batch_id}/label.svg`
- `POST /api/batches/{batch_id}/translations`
- `POST /api/batches/{batch_id}/translations/import-csv`
- `POST /api/batches/{batch_id}/akta-results`
- `POST /api/batches/{batch_id}/spr-results`
- `POST /api/batches/{batch_id}/spr-concentrations`
- `POST /api/batches/{batch_id}/hplc-results`
- `GET /api/order-monitor`
- `GET /api/batches/{batch_id}/experiments`
- `POST /api/batches/{batch_id}/experiments`
- `GET /api/experiments/{experiment_id}`
- `GET /api/experiments/{experiment_id}/raw-files`
- `GET /api/experiment-raw-files/{raw_file_id}/download`
- `PATCH /api/experiments/{experiment_id}/wells/{well_id}/result`
- `GET /api/artifacts/{artifact_id}/download`
- `DELETE /api/artifacts/{artifact_id}`
