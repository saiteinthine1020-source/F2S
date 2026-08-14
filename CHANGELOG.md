# Changelog

All notable changes to F2S will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioned application releases will follow [Semantic Versioning](https://semver.org/) when the project reaches a releasable implementation. F2S currently has no application release or version tag.

## [Unreleased]

### Added

- Phase 0 product, functional, architecture, database, API, UI/UX, farming, security, reporting, testing, AI, deployment, operations and recovery documentation.
- Repository milestones, issue plan, governance and initialisation guidance.
- Repository security, contribution, conduct and changelog policies.
- Least-privilege Phase 0 repository validation for Markdown, links, Compose configuration, secret hygiene and prohibited generated files.
- ADR-003 and an initial typed FastAPI modular-monolith skeleton with safe settings, liveness behavior, locked tooling, tests, CI and a non-root local container.
- Phase 1 workspace and identity authority, repository instructions, and ADR-012 through
  ADR-016 covering isolation, ownership, sessions, onboarding, recovery, and module types.
- SQLAlchemy 2 async PostgreSQL infrastructure, reviewed Alembic migration, and the five-table Identity and Workspace Access schema foundation.
- PostgreSQL CI coverage for clean migration lifecycle, transaction rollback, and foundational workspace constraints.
- Digest-only session, activation, recovery, ownership-transfer, and append-only audit persistence with a second reviewed Alembic migration.
- PostgreSQL inspection and negative tests for incremental migration, unique digests, expiry/lifecycle rules, same-workspace transfers, audit references, and security query indexes.
- Immutable server-derived authorization context, backend role-capability policy, and context-required workspace-scoped SQLAlchemy repository foundations.
- Capability decision-table and two-workspace tests for inactive, foreign, fabricated, restricted-field, and no-side-effect mutation denials.
- Locked Argon2id password hashing, purpose-separated opaque credential, HMAC-SHA-256 digest, timezone-aware single-use lifecycle, and injectable abuse-control primitives.
- Focused security tests for password hashing/rehash, entropy, purpose separation, constant-time comparison, expiry/replay/revocation, throttling, and redaction.
- Bounded Phase 1 audit and correlation contracts, an append-only transaction-bound SQLAlchemy writer, safe concealed-denial evidence, and an authoritative event catalogue.
- Audit validation and PostgreSQL evidence for UTC identity/workspace events, metadata redaction, append-only boundaries, correlation consistency, and atomic state-plus-audit commit/rollback.
- One-time serialized first-Admin/workspace bootstrap with normalized input, Argon2id-only password persistence, explicit module defaults, atomic owner/audit creation, safe API envelopes, and permanent post-success closure.
- Bootstrap concurrency, rollback, validation, owner, audit, API, and operator-procedure evidence.
- Workspace-scoped finance-category list, create, rename, and archive APIs with Admin-only
  mutations, optimistic concurrency, normalized duplicate protection, historical visibility,
  module gating, safe denials, and bounded audit evidence.

### Security

- Private vulnerability-reporting instructions that prohibit public disclosure of vulnerability details, secrets and workspace data.
- Purpose-separated bearer and challenge digests replace raw credential persistence; audit metadata is bounded relational data without free-form payload storage.
- Protected repository operations revalidate active account, workspace, membership, role, and capability while foreign and fabricated authority receives one concealed not-found outcome.
- Identity secret values, password verifiers, keyed digests, and abuse subjects use redacted representations; validation and lifecycle failures expose only bounded safe codes.
- Audit accepts only reviewed codes and stable references; malformed correlation values and denied foreign-resource probes are never reflected into evidence or safe errors.

### Changed

- Aligned the roadmap, root guidance, secondary designs, and operational documentation with Workspace as the canonical tenant boundary and Admin, Contributor, and Advisor as the Phase 1 roles.
- Required typed database connection settings with secret redaction and verified TLS in production.

### Licensing

- Confirmed the existing MIT License remains the repository's explicit license pending repository-owner review of any future change.

Unreleased entries describe repository changes only. They must not imply that planned application features, security controls, deployments, backups or tests are implemented.
