# F2S Backend

This directory contains the FastAPI modular-monolith foundation and the first PostgreSQL persistence slice from Issue #43. It defines only installation bootstrap state, user accounts, workspaces, memberships, and workspace module configuration. Login/session workflows, credentials, recovery, finance, farming, and background jobs remain out of scope.

## Boundaries

```text
app/
|-- api/       # HTTP and operational transport boundary
|-- core/      # Small application-wide technical configuration
|-- infrastructure/database/ # SQLAlchemy mappings and transaction adapters
|-- modules/   # Future business modules and their public contracts
`-- main.py    # Application factory and ASGI entry point
```

`migrations/` contains reviewed Alembic revisions. Domain module code remains independent of SQLAlchemy; persistence mappings stay in the outer infrastructure layer.

Future module domain code must not import FastAPI, SQLAlchemy or `app.api`. Cross-module access must use documented public contracts; direct imports from another module's internals and circular dependencies remain prohibited by [ADR-001](../docs/adr/ADR-001-modular-monolith.md). FastAPI is limited to the HTTP and application boundary by [ADR-003](../docs/adr/ADR-003-use-fastapi.md).

## Prerequisites and setup

- uv 0.12.1
- Python 3.13.14, installed automatically by uv when unavailable

From `backend/`:

```powershell
uv sync --frozen --all-groups
```

No `.env` file is loaded automatically by the application. Settings use explicit `F2S_` environment variables:

| Variable | Default | Rule |
| --- | --- | --- |
| `F2S_ENVIRONMENT` | `local` | One of `local`, `test`, or `production` |
| `F2S_DEBUG` | `false` | Must remain false in production |
| `F2S_DOCS_ENABLED` | `false` | Must remain false in production; explicit local opt-in only |
| `F2S_DATABASE_HOST` | none | Required; database network host |
| `F2S_DATABASE_PORT` | `5432` | TCP port from 1 through 65535 |
| `F2S_DATABASE_NAME` | none | Required PostgreSQL identifier |
| `F2S_DATABASE_USER` | none | Required PostgreSQL identifier |
| `F2S_DATABASE_PASSWORD` | none | Required secret; redacted by settings and URL representations |
| `F2S_DATABASE_SSLMODE` | `disable` | Production requires `verify-full`; disable is local/test only |

Unknown settings passed to the settings model and unsupported values fail validation. A raw database URL is deliberately unsupported so reserved characters are encoded safely and the password is not copied into logs.

## Run locally

```powershell
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Apply the reviewed schema before running persistence-backed behavior:

```powershell
uv run --frozen alembic upgrade head
```

The only implemented behavior is the operational liveness endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

It returns only `{"status":"ok"}`. It does not claim database or external-provider readiness and exposes no configuration, version, hostname, dependency or workspace data.

## Validate

```powershell
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy app tests
uv run --frozen pytest
```

All four commands are merge gates. The ordinary local test command skips tests marked `postgres`. Run the complete suite only against a disposable database configured through the variables above:

```powershell
$env:F2S_RUN_POSTGRES_TESTS = "1"
uv run --frozen pytest
```

CI provisions a clean PostgreSQL 18 service and always runs migration, downgrade, transaction rollback, and relational-constraint tests.
