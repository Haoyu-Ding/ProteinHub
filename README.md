# ProteinHub

ProteinHub is a local MVP for protein-centered design work.

The fixed data hierarchy is:

```text
Project -> Protein -> Artifact
Project -> Batch -> Experiment -> BatchWell -> Protein
```

Each protein owns exactly one amino-acid sequence. Batches group project proteins into 96-well plate positions. Each batch can have multiple experiments, currently FPLC, SPR, and HPLC, and each experiment maps results back through wells to proteins. Artifacts manage all file types. Files are stored under `storage/`, while SQLite stores only metadata and relative file paths. Permissions are enforced at the Project level with JWT authentication.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python main.py
```

Then open the NiceGUI URL printed in the terminal, usually `http://127.0.0.1:8080`.

## Code layout

ProteinHub keeps framework, business, and infrastructure concerns separate:

- `proteinhub/api/` defines FastAPI routes, request schemas, and request-scoped dependencies.
- `proteinhub/application/` coordinates business rules such as authentication, permissions, projects, proteins, batches, and artifacts.
- `proteinhub/domain/` contains domain-level errors and shared domain concepts.
- `proteinhub/infrastructure/sqlite/` owns SQLite connection, schema, and repository queries.
- `proteinhub/infrastructure/storage/` owns local file storage and safe artifact paths.
- `proteinhub/ui.py` defines NiceGUI pages and talks to the backend only through `/api/...`.

The legacy modules `proteinhub.db`, `proteinhub.storage`, and `proteinhub.services` remain as compatibility exports for existing imports and tests.

Detailed project standards live in:

- `docs/architecture.md`
- `docs/development.md`
- `AGENTS.md`

## API

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/me`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/members`
- `GET /api/projects/{project_id}/proteins`
- `POST /api/projects/{project_id}/proteins`
- `POST /api/projects/{project_id}/proteins/parse-structure`
- `GET /api/projects/{project_id}/batches`
- `POST /api/projects/{project_id}/batches`
- `GET /api/proteins/{protein_id}`
- `GET /api/batches/{batch_id}`
- `GET /api/batches/{batch_id}/experiments`
- `POST /api/batches/{batch_id}/experiments`
- `GET /api/experiments/{experiment_id}`
- `PATCH /api/experiments/{experiment_id}/wells/{well_id}/result`
- `GET /api/proteins/{protein_id}/artifacts`
- `POST /api/proteins/{protein_id}/artifacts`
- `GET /api/artifacts/{artifact_id}/download`
- `DELETE /api/artifacts/{artifact_id}`
