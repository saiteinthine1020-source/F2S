# F2S Backend

This directory contains the FastAPI modular-monolith foundation and the first PostgreSQL
identity/workspace slices. It includes one-time bootstrap, Admin-controlled Contributor and
Advisor provisioning, single-use account activation, digest-only security and audit records,
and workspace-scoped authorization. It also implements concealed normalized-email login,
short-lived opaque bearer authentication, rotating server-side refresh sessions, reuse-family
revocation, and logout. Production activation delivery, distributed authentication counters,
ownership transfer, finance, farming, and background jobs remain out of scope.

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

Audit exposes a framework-free append-only writer contract and bounded Phase 1 action, result,
resource, reason, source, and context enums. Its SQLAlchemy adapter uses the caller-supplied
session, flushes required evidence, and never commits independently, so a consequential state
change and its audit event succeed or roll back together. Global identity evidence is supported
before workspace creation; workspace evidence validates workspace and membership references.
Concealed cross-workspace denial evidence stores no probed workspace/resource ID. Correlation
input is either a canonical UUID or a generated UUIDv4; invalid input receives a fresh safe
correlation and is never echoed. See the
[Audit Event Catalogue](../docs/22_Audit_Event_Catalogue.md).

The one-time installation bootstrap is available at `GET/POST /api/v1/setup/bootstrap`.
PostgreSQL serializes callers through the singleton installation guard; the account, Argon2id
password verifier, workspace, Active Admin owner membership, explicit module defaults, audit
events, and completion marker share one transaction. Exactly one concurrent request can win,
and later attempts receive a concealed conflict. Bootstrap does not create a login session;
the new Admin signs in through the ordinary authentication route.
Operators must follow the
[Bootstrap Operator Procedure](../docs/23_Bootstrap_Operator_Procedure.md); there are no default
credentials or ordinary reset path.

Opaque credentials use at least 32 random bytes. Persistence receives only an HMAC-SHA-256
digest whose input includes a fixed versioned domain and bounded purpose. The HMAC key is
injected as redacted runtime key material and must contain at least 32 bytes; no example or
fallback key exists in source. Activation challenges expire after 24 hours. PostgreSQL locks
the matched challenge, membership, and account while it verifies and consumes the challenge,
so only one activation can succeed. Restart revokes every earlier Issued challenge and keeps
the rows as historical evidence. Invalid, expired, replayed, and revoked values return the
same concealed activation failure and write bounded denial evidence.

Member provisioning is available only to an authenticated Active Admin at
`POST /api/v1/workspaces/{workspace_id}/members`; the only accepted roles are Contributor and
Advisor. It creates a Pending membership and either a new Pending Activation account or a
membership for an existing eligible account without revealing which occurred. Activation
restart is available at
`POST /api/v1/workspaces/{workspace_id}/members/{membership_id}/activation/restart`.
`POST /api/v1/auth/activate` accepts the one-time activation value and, for a new account, its
first password. There is no public registration endpoint and member responses contain no
global account identifier.

Local and test environments use a process-local development activation outbox. It captures
the clear activation value once for a developer/test delivery boundary; `drain()` removes the
captured values. It is neither durable nor an email service and must never be enabled in
production. Production deliberately rejects provisioning/restart until a durable delivery
adapter is configured, causing the database transaction to roll back instead of creating an
undeliverable membership. Logs, API responses, database fields, and examples must use
placeholders, never a captured value.

Authentication is available at `POST /api/v1/auth/login`, refresh at
`POST /api/v1/auth/refresh`, and logout at `POST /api/v1/auth/logout`. Login and activation
require the exact configured browser Origin. Refresh and logout additionally require the
`__Host-f2s_refresh` cookie and the current session-bound `X-CSRF-Token`. Login/refresh return
the opaque access credential and CSRF value in a `no-store` JSON response; the refresh value
appears only in a Secure, HttpOnly, SameSite=Strict, Path=/ cookie without a Domain attribute.
The access value is sent only as `Authorization: Bearer <value>` and every protected request
rechecks the current session and account state in PostgreSQL.

Access credentials expire after 15 minutes. Refresh idle expiry is seven days and resets only
after a successful atomic rotation; absolute session expiry is 30 days and never extends.
Rotation has zero grace. Reusing a rotated refresh value marks historical rotated generations
as Reuse Detected and revokes the current generation in that family. Logout scope `CURRENT`
revokes the current family; `ALL` revokes every Active session for the account. Logout is
idempotent and always expires the browser cookie.

Local/test login abuse control stores only keyed subject digests, applies the provisional
five-failure progressive delay, and limits one network subject to 30 attempts per 15 minutes
before Argon2 verification. It is process-local developer/test support. Production rejects
login until a reviewed distributed counter adapter is configured; it must not silently fall
back to per-process counters.

Rate-limit storage remains an injected adapter. The shared contracts accept only keyed
subject digests and bounded scopes—never raw identifiers or account-existence flags.
Fixed-window threshold and progressive login-delay policies are deterministic, while
production distributed counters and final measured limits remain later work.

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
| `F2S_IDENTITY_DIGEST_KEY` | none | Required secret with at least 32 UTF-8 bytes; use random environment-specific material |
| `F2S_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | Exact browser origin; production requires explicit HTTPS |

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

The operational liveness endpoint is:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

It returns only `{"status":"ok"}`. It does not claim database or external-provider readiness and exposes no configuration, version, hostname, dependency or workspace data.

Safe placeholder requests:

```text
POST /api/v1/workspaces/00000000-0000-4000-8000-000000000101/members
{"email":"member@example.invalid","display_name":"Example Member","role":"CONTRIBUTOR","preferred_language":"en","timezone":"UTC"}

POST /api/v1/auth/activate
{"value":"<activation-value-from-development-delivery>","password":"<new-password>"}

POST /api/v1/auth/login
Origin: http://127.0.0.1:5173
{"email":"member@example.invalid","password":"<password>"}

POST /api/v1/auth/refresh
Origin: http://127.0.0.1:5173
Cookie: __Host-f2s_refresh=<refresh-value>
X-CSRF-Token: <csrf-value>
{}
```

Do not paste a real activation value, password, database credential, or digest key into source,
shell history, issue text, screenshots, logs, or documentation.

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

CI provisions a clean PostgreSQL 18 service and always runs clean/incremental migration,
downgrade, transaction rollback, identity cryptography/redaction, activation
restart/expiry/replay/concurrency, authorization decision-table, two-workspace repository,
same-workspace, login concealment, session rotation/concurrency/reuse, expiry, logout,
cookie/Origin/CSRF, abuse-control, index, and relational-constraint tests.
