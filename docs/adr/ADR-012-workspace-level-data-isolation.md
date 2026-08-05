# ADR-012: Use Workspace-Level Data Isolation

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1
- **Supersedes:** Household tenant, ownership, and isolation terminology in ADR-002

## Context

F2S now supports household, farm, microbusiness, small-business, combined, and custom
workspaces. Treating Household as the universal tenant name would mix product type with the
security boundary and would make future modules inconsistent.

## Decision

Workspace is the canonical tenant and authorization boundary. Every protected business row
has a direct, non-null `workspace_id`. Same-workspace relationships use composite foreign
keys or an equally strong database constraint. Repositories, services, APIs, jobs, files,
reports, caches, audit queries, and AI preparation require an explicit workspace context.

The authenticated user is not sufficient authorization: an Active account must have an
Active membership with the required capability in the requested workspace. Resource lookup
conceals cross-workspace existence. Automated tests use at least two workspaces and attempt
read, write, list, search, aggregate, export, file, job, and identifier-substitution attacks.

## Consequences

Workspace terminology replaces Household terminology at security and persistence
boundaries. Household remains a workspace type and a finance domain. Queries and indexes
carry `workspace_id`, increasing schema verbosity in exchange for explicit isolation and
database-enforced relationship safety.

## Rejected alternatives

- Inferring tenant identity through parent joins: too easy to omit and difficult to index.
- Separate databases per workspace in the MVP: operationally disproportionate.
- Frontend filtering: not an authorization control.
