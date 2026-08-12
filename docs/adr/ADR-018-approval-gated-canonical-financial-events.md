# ADR-018: Use Approval-Gated Canonical Financial Events and Append-Only Corrections

- **Status:** Accepted
- **Date:** 2026-08-13
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 2 - Household Finance

## Context

F2S receives cash activity from manual household finance and, in later phases, farming
costs, sales, remittances, debts, and receivables. Representing the same cash movement in
more than one module would make balances irreconcilable. Rewriting or deleting an approved
event would also remove the evidence needed to explain historical totals.

Contributors may submit records but cannot affect official totals before Admin review.
Advisors may review permitted Approved information but cannot change financial facts. The
design therefore needs to distinguish review status from whether a posting is currently
effective.

## Decision

Household Finance owns one canonical financial event for each real cash inflow or outflow.
Other modules use its public command/reference contract and a unique same-workspace source
link; they do not write Household Finance tables or create a second cash representation.

### Approval and posting

Approval and posting are separate state dimensions:

| Approval status | Posting status | Meaning |
| --- | --- | --- |
| `PENDING` | `NOT_EFFECTIVE` | Committed submission awaiting Admin decision |
| `REJECTED` | `NOT_EFFECTIVE` | Preserved rejected submission |
| `APPROVED` | `EFFECTIVE` | Approved posting included in official datasets |
| `APPROVED` | `REVERSED` | Approved original neutralised by one effective reversal |

Other combinations are invalid. A client-side draft is not a committed financial event.
Contributor creation always produces `PENDING/NOT_EFFECTIVE`. An authorised Admin creation
produces `APPROVED/EFFECTIVE` atomically. Only an Admin may decide a Pending submission.
Approved status never transitions back to Pending or Rejected.

The central official-dataset predicate includes only Approved effective postings in the
selected workspace and permitted filter scope. Pending and Rejected records never affect
balances, summaries, dashboards, reports, exports, forecasts, or AI datasets.

### Exact values and immutability

An ordinary event stores a positive magnitude and an explicit `INFLOW` or `OUTFLOW`
direction. [ADR-008](ADR-008-safe-financial-numeric-storage.md) governs exact decimal input,
storage, currency scale, serialization, and rounding.

After approval, amount, currency, direction, occurred date, event kind, activity
classification, category, and canonical source link are immutable. Pending submissions are
versioned and may change only the allowlisted source fields defined by the focused design.

### Correction, reversal, replacement, and archive

A reversal is a new Approved effective event with the same workspace, currency, magnitude,
and occurred date supplied for the reversal action, and the opposite direction. It links to
one Approved effective original. The operation atomically makes the original `REVERSED`.
There is at most one effective reversal for an original. A reversal cannot reverse itself or
another reversal in Phase 2.

Correction of an Approved event is one atomic command that creates its reversal and an
optional Approved effective replacement linked directly to the original. A later correction
targets the replacement as a new original. The original chain remains attributable.

Archive changes ordinary discoverability only. It never changes the cash effect of an
Approved posting. Reversal is the only Phase 2 action that neutralises an Approved posting.
Ordinary hard deletion of a financial event is prohibited.

### Roles and review artifacts

- Admin creates Approved events, manages categories, decides Pending submissions, and runs
  correction, reversal, and archive commands.
- Contributor creates Pending submissions and may edit only their own eligible Pending
  source fields. Contributor representations contain no restricted totals or indirect
  aggregates.
- Advisor reads permitted Approved records and creates attributed comment or flag sidecars.
  Advisor cannot mutate, approve, reject, correct, reverse, archive, or delete an event.

Review comments and flags are workspace-owned Household Finance records. They do not alter
approval, posting, or official totals and are not stored as audit free text.

### Atomicity, idempotency, and module boundaries

Creation, decision, reversal, correction, required audit evidence, and terminal idempotency
outcome commit once in one PostgreSQL transaction or roll back together. Current account,
membership, selected workspace, module, and capability are revalidated on replay.

Idempotency evidence is scoped by workspace and operation. Matching key and fingerprint
replays the original safe result; a changed fingerprint conflicts. The terminal outcome is
retained for 14 days. Request bodies, credentials, and Restricted values are not stored as
idempotency evidence.

Every protected finance, review, file-link, and idempotency row carries direct
`workspace_id`. Composite keys prevent cross-workspace references. FastAPI and SQLAlchemy
remain boundary/adaptor concerns under ADR-003; domain contracts do not depend on them.

## Consequences

### Positive

- One cash movement contributes once across every current and future consumer.
- Approval cannot be confused with accounting effect.
- Corrections preserve history and reconcile exactly.
- Workspace and role boundaries remain enforceable in queries and response schemas.
- Later modules can integrate without taking ownership of finance persistence.

### Negative

- Corrections require additional rows and more explicit state handling.
- Official queries must apply one shared effectiveness predicate.
- Review artifacts, idempotency evidence, and source links add schema and test surface.
- Archive cannot be used as a shortcut to remove a mistaken amount from totals.

## Alternatives considered

### Mutable transaction rows

Rejected because changes to approved facts would erase the explanation for prior totals and
make audit evidence insufficient.

### One status field for approval and posting

Rejected because review state and accounting effect have different transition rules.

### Duplicate module-specific cash rows

Rejected because uniqueness and reconciliation could not reliably prove that one real event
was counted once.

### Archive removes an event from totals

Rejected because a presentation action would silently change financial truth.

## Fitness criteria

This decision remains fit when tests prove:

1. only Approved effective postings enter official datasets;
2. a source action has exactly one canonical event;
3. original plus reversal reconciles to zero at the currency accounting scale;
4. concurrent decisions, reversals, and retries have one winner;
5. failure leaves no partial finance, audit, or idempotency outcome;
6. two-workspace and role tests reveal no value or existence detail; and
7. approved history survives supported migrations and recovery.

Changing canonical ownership, approval/effectiveness meaning, or correction semantics
requires a superseding ADR.
