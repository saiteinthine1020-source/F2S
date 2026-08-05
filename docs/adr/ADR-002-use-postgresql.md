# ADR-002: Use PostgreSQL as the Primary Relational Database

- **Status:** Accepted
- **Date:** 2026-08-04
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1 - Authentication and Workspace
- **Superseded in part by:** ADR-012 replaces Household with Workspace as the tenant,
  ownership, and isolation boundary; historical Household wording below is read in that
  workspace-scoped sense.

## Context

F2S must preserve household isolation and exact financial relationships across household finance, farming investments, shared costs, harvests, crop sales, remittances, debts, receivables, audit evidence, and generated datasets. Several use cases require atomic changes across logically separate modules inside the modular monolith.

The initial product is operated by a small team for one farming household, but its records are long-lived and financially sensitive. The database therefore needs:

- ACID transactions across related module-owned records;
- exact decimal numeric types;
- foreign keys, unique/check constraints, and indexes;
- timezone-aware timestamps;
- predictable migration and backup tooling;
- transactional concurrency control and idempotency support;
- a mature Python/SQLAlchemy ecosystem; and
- an operational path that remains manageable on one initial production server.

[ADR-001](ADR-001-modular-monolith.md) establishes one backend deployable unit and one initial relational database while preserving logical module ownership. The [System Architecture](../07_System_Architecture.md) prohibits modules from bypassing public contracts or writing one another's tables directly.

## Decision

F2S will use **PostgreSQL** as its primary relational database.

The initial backend will connect to one PostgreSQL database cluster and one application database. Tables and migrations remain logically owned by the modules defined in the system architecture even when they share a physical database and transaction.

PostgreSQL-specific features may be used when they provide a clear correctness, security, operability, or performance benefit and are hidden behind owning persistence adapters. Domain code must not depend directly on PostgreSQL or SQLAlchemy objects.

### Version policy

- Local, test, CI, staging, backup/restore, and production environments must use the same approved PostgreSQL major version unless a compatibility test explicitly covers a transition.
- The exact major/minor version is selected and pinned by the deployment design in Issue #15 from a PostgreSQL-supported release at implementation time.
- Production must not run an end-of-life major version.
- A major-version upgrade requires a tested migration/backup/restore plan and documented compatibility evidence before production use.

This ADR chooses PostgreSQL; it intentionally does not freeze a version years before deployment evidence exists.

## Relational ownership and access rules

1. Each table, sequence, constraint, index, and migration has one owning backend module.
2. Only the owning module's repository or approved adapter writes its tables.
3. Cross-module business operations call public module contracts under an application-owned unit of work; coordinators do not issue direct writes to another module's tables.
4. Cross-module identifiers are explicit relational references where the database design approves them. Exact keys and delete behavior are deferred to Issue #8.
5. Reporting, dashboards, and AI preparation use authorised query/dataset contracts, not unrestricted ad hoc joins over internal tables.
6. Database constraints defend critical invariants but do not replace domain validation or backend household authorisation.
7. Ordinary business operations use correction, reversal, cancellation, or archive behavior; they do not cascade-delete linked financial or farming history silently.

## Transaction and concurrency rules

- One application use-case coordinator owns one database transaction for required core state and policy-required audit evidence.
- A cross-module financial operation commits all required records exactly once or rolls them all back.
- External calls, email delivery, Gemini requests, and report rendering do not run inside core financial transactions.
- Mutable aggregates use an approved optimistic version or equivalent concurrency mechanism. A stale write returns an explicit conflict.
- Replayable commands use household- and operation-scoped idempotency evidence. Current authorisation is revalidated even when an idempotency key was seen previously.
- Transaction isolation and locking are selected per use case by the detailed database design and tests; code must not rely on an undocumented database default to prevent lost updates.
- Long-running transactions and user interaction inside a transaction are prohibited.

## Data type baseline

| Concern | PostgreSQL baseline |
| --- | --- |
| Primary identifiers | Application-generated opaque identifiers or another explicit relational identifier selected by Issue #8; never business meaning alone |
| Money, rates, percentages, quantities | Exact `NUMERIC` definitions governed by [ADR-008](ADR-008-safe-financial-numeric-storage.md); `REAL`, `DOUBLE PRECISION`, and floating-point expressions are prohibited in verified paths |
| Timestamps | `TIMESTAMPTZ`, stored/compared as UTC instants; household timezone is presentation/business-period context |
| Dates | `DATE` for calendar facts that are not instants, such as a planting date when no time is intended |
| Boolean/state | Explicit boolean or constrained state value; lifecycle meaning remains in domain rules |
| Free text | Length-limited text with purpose, sensitivity, and safe handling defined by the data dictionary |
| Structured extension data | Relational columns by default; `JSONB` only for a documented bounded purpose, ownership, validation, indexing, and migration strategy |
| Binary files | Protected file/object storage reference and metadata, not unrestricted large file bytes in business tables unless a later ADR approves it |

Detailed column choices belong to Issue #8 and may be stricter than this baseline.

## Household isolation

PostgreSQL is a defence layer, not the sole authorisation mechanism.

- Every household-owned table identified by Issue #8 must carry or derive an enforceable household ownership path.
- Owning repository queries must include the authorised household scope for lists, reads, writes, aggregates, archives, and deletes/corrections.
- Loading a record globally and filtering it in Python afterward is prohibited.
- Uniqueness that is household-specific must include the household scope.
- Foreign-key paths must not permit a child record to reference a parent from another household.
- Isolation tests must use at least two households and substitute direct identifiers, parent identifiers, filters, cursors, aggregates, reports, jobs, files, and AI-preparation targets.
- PostgreSQL row-level security may be added as defence in depth only after Issue #8 and Issue #11 define connection/session semantics and operational bypass policy. It cannot replace application authorisation or scoped repositories.

## Least-privilege database access

Production credentials and roles must be separated by purpose:

| Principal | Minimum intent |
| --- | --- |
| Migration principal | Apply approved schema migrations; not used by ordinary runtime requests |
| Runtime application principal | Required DML and sequence/function access on approved application objects; no role creation, database creation, extension installation, ownership, or unrestricted DDL |
| Backup principal or mechanism | Read only what is required for a complete protected backup; no ordinary application mutation |
| Restore/administrative principal | Break-glass or controlled operational use; not embedded in application configuration |
| Monitoring principal | Minimum metadata/health visibility; no household business-data browsing unless a separately approved diagnostic procedure requires it |

Credentials are unique by environment, stored outside source control, rotated according to the security design, and never shared with the browser. Production network exposure is restricted to approved application and operator paths. TLS requirements are finalized in Issues #11 and #15.

## Backup, recovery, and sensitive data

- Backups are treated as sensitive production data and receive access control and encryption protection equivalent to the live database.
- Backup credentials, encryption keys, and storage credentials are separated according to the operations design and never stored in the repository or backup archive itself.
- At least one approved backup copy must be outside the failure boundary of the primary server before production acceptance; exact count and retention are owned by Issue #16.
- Restore testing must recreate schema, constraints, module ownership expectations, household isolation, audit references, and representative financial reconciliations.
- A backup is not considered usable until an executed restore drill meets the approved RPO/RTO and integrity checklist.
- Production data must not be copied into development, documentation, support, or analytics environments without an explicit protected-data procedure.

## Schema change policy

- Alembic is the planned migration mechanism, but no migration is created by this ADR.
- Every schema change is versioned, reviewed, repeatable from a clean database, and tested from the supported prior state.
- Application and migration compatibility is documented for rolling or staged deployment where relevant.
- Destructive or table-rewriting changes require backup, capacity, lock-duration, rollback/restore, and data-reconciliation evidence.
- Migrations never rely on manually edited production state that is absent from version control and operations records.
- Direct production schema changes outside the approved migration/emergency process are prohibited.

## Fitness criteria

PostgreSQL remains fit for F2S when the implementation can demonstrate:

1. **Atomicity:** injected failures in representative finance/farming, sale/payment, debt/payment, and receivable/payment operations leave all required records committed once or none committed.
2. **Exactness:** the ADR-008 decimal examples and boundary matrices pass without binary floating-point artifacts.
3. **Isolation:** two-household repository, service, API, aggregate, report, file, job, audit, and AI-preparation tests reveal no cross-household value or existence detail.
4. **Integrity:** foreign keys, uniqueness, checks, and domain tests reject orphaned or contradictory records defined by Issue #8.
5. **Concurrency:** duplicate, concurrent, stale-version, and timeout-after-commit tests produce one intended mutation or an explicit conflict.
6. **Migration safety:** a clean database and a representative prior snapshot migrate successfully and reconcile expected row counts, constraints, and verified totals.
7. **Recoverability:** a protected backup restores into a documented replacement environment and passes integrity, isolation, authentication, and financial reconciliation checks.
8. **Capacity:** the production-like profile meets approved latency and resource targets with the reference dataset and concurrent workload.
9. **Privilege separation:** automated/manual review proves the runtime principal cannot perform prohibited ownership, role, database, extension, or unrestricted DDL operations.

Failure to meet a criterion requires remediation, a narrower supported profile, or a superseding ADR; it must not be hidden by changing expected results.

## Consequences

### Positive

- Core modular-monolith operations can use ordinary ACID transactions rather than distributed coordination.
- Exact `NUMERIC`, constraints, relational integrity, indexes, and concurrency features support trustworthy financial records.
- PostgreSQL, SQLAlchemy, Alembic, backup tools, and monitoring have mature ecosystems.
- One initial database keeps deployment, backup, restore, and incident handling manageable for a small team.
- Logical module ownership preserves a future path to extraction if measured evidence justifies it.

### Negative

- PostgreSQL must be installed, secured, upgraded, monitored, backed up, and restored; it is more operationally demanding than an embedded database.
- Modules share database capacity and failure impact.
- Database-specific features can increase portability cost.
- Weak repository discipline could still create cross-module coupling or unsafe household queries despite relational ownership rules.
- Schema evolution for long-lived financial history requires careful compatibility and reconciliation work.

### Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Runtime credential has excessive privilege | Separate migration/runtime/backup/operator roles and test denied capabilities |
| Cross-household query omits scope | Repository contract, composite ownership constraints where designed, two-household isolation tests, optional later RLS defence |
| Shared database becomes a coupling shortcut | Module-owned migrations/tables, public contracts, import/architecture checks, review rule against internal SQL access |
| Backup exposes sensitive data | Encryption, access control, separate key custody, off-host storage, retention, restore evidence |
| Migration corrupts history or blocks service | Representative snapshot testing, reconciliation, lock/capacity review, backup and rollback/restore plan |
| Unsupported version creates security/upgrade risk | Pin a supported major version, monitor lifecycle, rehearse major upgrades |

## Alternatives considered

### SQLite

Rejected as the production database. It is valuable for isolated tooling but would not provide the approved production concurrency, role separation, server operation, and parity profile. Using SQLite as a default test substitute is also prohibited where PostgreSQL behavior, constraints, transactions, or numeric semantics are under test.

### MySQL or MariaDB

Viable relational alternatives, but rejected because PostgreSQL is the planned stack and provides the desired exact numeric, constraint, transactional, JSON, indexing, and Python ecosystem without a demonstrated F2S benefit from choosing a different server.

### Document database

Rejected as the primary store because F2S relies on relational ownership, exact financial relationships, constraints, canonical events, and multi-record transactions. Purpose-specific document storage would require a later ADR.

### Separate database per module

Rejected initially because it would introduce distributed transactions, duplicated operations, and cross-database reporting complexity before independent scale or team ownership justifies it.

## Revisit conditions

Review this decision if measured evidence shows that PostgreSQL cannot meet required correctness, availability, capacity, recovery, regulatory, or operational needs, or if a module requires independently governed data/deployment boundaries. Any replacement or extraction requires a new ADR and a verified migration/reconciliation plan.

## Scope note

This ADR selects the database technology and operational rules only. It creates no database, role, table, model, migration, query, endpoint, container, or deployment resource.
