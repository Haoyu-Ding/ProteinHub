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

