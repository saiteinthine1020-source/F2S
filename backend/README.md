# F2S Backend

This directory contains the smallest executable FastAPI skeleton approved by Issue #20. It proves configuration, application-factory, liveness, architecture-test, container and CI behavior. It contains no user, login, household, finance, farming, persistence, schema, migration or background-job implementation.

## Boundaries

```text
app/
|-- api/       # HTTP and operational transport boundary
|-- core/      # Small application-wide technical configuration
|-- modules/   # Future business modules and their public contracts
`-- main.py    # Application factory and ASGI entry point
```

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

Unknown settings passed to the settings model and unsupported values fail validation. No secret setting exists in this skeleton.

## Run locally

```powershell
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The only implemented behavior is the operational liveness endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

It returns only `{"status":"ok"}`. It does not claim database or external-provider readiness and exposes no configuration, version, hostname, dependency or household data.

## Validate

```powershell
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy app tests
uv run --frozen pytest
```

All four commands are merge gates. PostgreSQL tests are not present because this skeleton has no persistence behavior.
