# Bootstrap Operator Procedure

## Purpose and authority

This procedure covers the one-time first-Admin and first-workspace bootstrap implemented in
Phase 1. It follows ADR-013, ADR-015, ADR-016, the Workspace and Identity Foundation, and the
API Design. It is not public self-registration or disaster-reset tooling.

## Before bootstrap

1. Apply all reviewed database migrations to the intended empty installation.
2. Confirm the API uses the intended PostgreSQL database and production-safe configuration.
3. Use a trusted same-origin client and confirm TLS before entering credentials in production.
4. Check `GET /api/v1/setup/bootstrap`; continue only when `data.available` is `true`.
5. Prepare the Admin's own normalized email and password plus the workspace name, type,
   three-letter uppercase currency, IANA timezone, and supported language code.

F2S provides no default account, password, bootstrap token, or example production credential.
Passwords are accepted only in the POST body, represented as redacted secret values in the
application, and persisted only as an Argon2id verifier.

## Completion

Send one `POST /api/v1/setup/bootstrap` request. The operation creates the Active account,
workspace, Active Admin membership, sole ownership reference, explicit module flags, and
`WORKSPACE_CREATED` plus `BOOTSTRAP_COMPLETED` evidence atomically. A successful response is
`201 Created`; preserve the safe correlation ID for diagnostics, not the request body.

Workspace-type recommendations are initialized as explicit configuration:

| Workspace type | Household finance | Farming investments |
| --- | --- | --- |
| `HOUSEHOLD` | Enabled | Disabled |
| `FARM` | Enabled | Enabled |
| `MICROBUSINESS` | Enabled | Disabled |
| `SMALL_BUSINESS` | Enabled | Disabled |
| `COMBINED` | Enabled | Enabled |
| `CUSTOM` | Disabled | Disabled |

These flags are configuration metadata only; they do not implement later financial modules.

## Verification and failure

After success, `GET /api/v1/setup/bootstrap` returns `data.available: false`, and every later
POST returns the same safe `409 CONFLICT` without account or workspace disclosure. Concurrent
first requests have exactly one winner.

If completion fails, do not manually create or edit owner rows. Confirm no completion response
was received, inspect safe logs by correlation ID, and retry only after resolving the cause.
The transaction rolls back its guard, account, workspace, membership, modules, and audit rows
together. Ordinary bootstrap cannot be reset after success; any future disaster-reset procedure
requires a separate approved, authenticated, and audited design.
