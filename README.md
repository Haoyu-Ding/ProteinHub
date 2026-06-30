# ProteinHub

ProteinHub is a local MVP for sequence-centered protein design work.

The fixed data hierarchy is:

```text
Project -> Protein -> Sequence -> Artifact
```

Artifacts manage all file types. Files are stored under `storage/`, while SQLite stores only metadata and relative file paths. Permissions are enforced at the Project level with JWT authentication.

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
- `proteinhub/application/` coordinates business rules such as authentication, permissions, projects, sequences, and artifacts.
- `proteinhub/domain/` contains domain-level errors and shared domain concepts.
- `proteinhub/infrastructure/sqlite/` owns SQLite connection, schema, and repository queries.
- `proteinhub/infrastructure/storage/` owns local file storage and safe artifact paths.
- `proteinhub/ui.py` defines NiceGUI pages and talks to the backend only through `/api/...`.

The legacy modules `proteinhub.db`, `proteinhub.storage`, and `proteinhub.services` remain as compatibility exports for existing imports and tests.

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
- `GET /api/proteins/{protein_id}/sequences`
- `POST /api/proteins/{protein_id}/sequences`
- `GET /api/sequences/{sequence_id}`
- `GET /api/sequences/{sequence_id}/artifacts`
- `POST /api/sequences/{sequence_id}/artifacts`
- `GET /api/artifacts/{artifact_id}/download`
- `DELETE /api/artifacts/{artifact_id}`
