# F2S Backend

This directory contains the FastAPI modular-monolith foundation and the first two PostgreSQL persistence slices. It defines identity/workspace foundations, digest-only security and audit records, the Workspace Access authorization/repository boundary, and shared identity cryptography and abuse-control primitives. Authentication workflows and endpoints, delivery, session rotation behavior, transfer behavior, finance, farming, and background jobs remain out of scope.

## Boundaries

```text
app/
|-- api/       # HTTP and operational transport boundary
|-- core/      # Small application-wide technical configuration
|-- infrastructure/database/ # SQLAlchemy mappings, repositories, and transactions
|-- modules/   # Framework-free business policy and public contracts
`-- main.py    # Application factory and ASGI entry point
```

`migrations/` contains reviewed Alembic revisions. Domain module code remains independent of SQLAlchemy; persistence mappings stay in the outer infrastructure layer.

Workspace Access owns the immutable `AuthorizationContext` and the Admin, Contributor, and Advisor capability matrix. The SQLAlchemy adapter derives context from current database state, revalidates it for every protected operation, and includes `workspace_id` in each protected read and mutation. Public protected repository methods cannot be called without context. Restricted administration projections require their named capability, and missing or foreign resource identifiers share the safe `RESOURCE_NOT_FOUND` outcome.

Identity Security uses locked `argon2-cffi` with the provisional Argon2id candidate from the security design: 65,536 KiB memory, three iterations, parallelism one, 32-byte output, and a random 16-byte salt. New passwords require 15 through 1,024 Unicode characters; the upper safety bound still permits the required 64-character minimum support. A compromised-password screen is injected through a port. Successful verification reports whether the encoded parameters need rehashing.

Opaque credentials use at least 32 random bytes. Persistence receives only an HMAC-SHA-256 digest whose input includes a fixed versioned domain and bounded purpose. The HMAC key is injected as redacted runtime key material and must contain at least 32 bytes; no example or fallback key exists in source. Activation/recovery callers use the provisional 24-hour lifetime constant. Verification always derives and compares the digest with `hmac.compare_digest` before returning bounded invalid, expired, consumed, or revoked results. Consumption verifies the presented value and purpose in the same helper; a later persistence service remains responsible for making database verification and consumption atomic.

Rate-limit storage remains an injected adapter. The shared contracts accept only keyed subject digests and bounded scopes—never raw identifiers or account-existence flags. Fixed-window threshold and progressive login-delay policies are deterministic, while production distributed counters and final measured limits remain later work.

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

The migration chain supports both a clean database and an incremental upgrade from revision `20260809_0001`. Downgrade is intended for development/review while the new security tables are empty; production rollback requires the reviewed backup and migration procedure.

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

CI provisions a clean PostgreSQL 18 service and always runs clean/incremental migration, downgrade, transaction rollback, identity cryptography/redaction, digest/expiry/lifecycle, authorization decision-table, two-workspace repository, same-workspace, index, and relational-constraint tests.
