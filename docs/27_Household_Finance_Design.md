# Household Finance Design

## 1. Purpose, authority, and implementation gate

This document is the focused Phase 2 contract for categories, canonical financial events,
approval, posting, corrections, Advisor reviews, receipts, filters, and monthly summaries.
It implements [ADR-018](adr/ADR-018-approval-gated-canonical-financial-events.md) and inherits
the exact numeric rules from [ADR-008](adr/ADR-008-safe-financial-numeric-storage.md), the
workspace boundary from [ADR-012](adr/ADR-012-workspace-level-data-isolation.md), the role
model from [ADR-013](adr/ADR-013-workspace-ownership-and-membership.md), and the module model
from [ADR-016](adr/ADR-016-workspace-types-and-modules.md).

Issues #78 through #96 must implement this contract. A conflicting implementation is blocked
until the design and, for a durable decision, a superseding ADR are accepted together. This
issue adds no application code, migration, route, or UI component.

## 2. Invariants

1. One real cash inflow or outflow has one canonical financial event.
2. Every protected row has direct immutable `workspace_id` and same-workspace relationships.
3. Amount is a positive exact magnitude; direction carries the sign.
4. Approval status and posting status are separate and only their valid combinations persist.
5. Only Approved effective postings enter an official dataset.
6. Approved financial facts are append-only; reversal changes effect and archive changes
   discoverability.
7. Contributor queries never receive restricted totals or equivalent indirect aggregates.
8. Advisor review artifacts never mutate financial truth.
9. Multi-currency values remain separate unless a later accepted dated FX policy applies.
10. Required finance state, audit evidence, and idempotency outcome commit once or not at all.

## 3. Vocabulary and registries

Machine codes are stable, uppercase, translation-backed values. Unknown codes fail; free text
cannot extend a registry.

| Registry | Phase 2 values | Rule |
| --- | --- | --- |
| `cash_direction` | `INFLOW`, `OUTFLOW` | Ordinary negative amount is invalid |
| `event_kind` | `MANUAL_INCOME`, `MANUAL_EXPENSE` | Later modules add reviewed typed codes; manual kind fixes direction |
| `activity_classification` | `HOUSEHOLD`, `FARM`, `BUSINESS` | Classification is not a tenant boundary |
| `payment_method_code` | `CASH`, `BANK_TRANSFER`, `MOBILE_MONEY`, `CARD`, `CHEQUE`, `OTHER` | No credential or complete account/card data |
| `category_applicability` | `INCOME`, `EXPENSE`, `BOTH` | Must be compatible with manual event kind |
| `approval_status` | `PENDING`, `APPROVED`, `REJECTED` | Review lifecycle |
| `posting_status` | `NOT_EFFECTIVE`, `EFFECTIVE`, `REVERSED` | Accounting effect |
| `review_kind` | `COMMENT`, `FLAG` | Sidecar review only |
| `flag_status` | `OPEN`, `RESOLVED` | Only Admin resolves |
| `attachment_role` | `RECEIPT`, `SUPPORTING_DOCUMENT` | Expense receipt uses `RECEIPT` |

Phase 2 manual income and expense require one Active same-workspace finance category.
Domain-originated events in later phases may omit that category only when their typed public
source contract owns the classification.

## 4. Role and capability contract

| Capability | Admin | Contributor | Advisor |
| --- | --- | --- | --- |
| List active categories | Yes | Yes | Yes |
| Create/rename/archive category | Yes | No | No |
| Create manual event | Approved immediately | Pending submission | No |
| View event | Permitted workspace records | Own permitted submissions; no restricted totals | Permitted Approved records |
| Edit event | No direct Approved edit | Own eligible Pending fields | No |
| Approve/reject | Yes | No | No |
| Reverse/correct/archive | Yes | No | No |
| Add comment/flag | As designed Admin response | No | Yes on permitted Approved event |
| Resolve flag | Yes | No | No |
| View monthly summary | Yes | No | Yes |

All decisions occur in backend policy and scoped repositories. Hidden controls improve
clarity but confer no authority.

## 5. Entity contract

### 5.1 Finance category

`finance_categories` contains ID, workspace, display name, normalized name, applicability,
optional activity scope, `ACTIVE/ARCHIVED` status, actor/timestamps, version, and archive
evidence. Active normalized names are unique within the compatible workspace scope. Archive
prevents new selection but preserves historical display. Category mutation requires
`If-Match`.

### 5.2 Canonical financial event

`financial_events` contains:

- ID, direct workspace, creator/updater, UTC timestamps, positive version;
- event kind, direction, activity classification, occurred date, category;
- exact `NUMERIC(24,4)` amount and currency code;
- payment method and bounded source/payee, reference, and Confidential notes;
- approval and posting status, reviewer/time and bounded decision reason code;
- reversal/replacement links, archive actor/time/reason, and canonical operation evidence.

Approved core facts are immutable. Contributor may edit only category, occurred date,
activity classification, amount, currency, payment method, source/payee, reference, notes,
and eligible receipt links while their own event is Pending. Kind and direction remain fixed.
Every Pending edit requires `If-Match`, increments version, and records safe evidence.

Rejected submissions remain read-only. Resubmission is a new event with a new idempotency
operation rather than a Rejected-to-Pending transition.

### 5.3 Review artifact

`financial_event_reviews` contains direct workspace and event references, kind, bounded
Confidential body, allowlisted reason code, creator/time, and—for a flag—status,
resolver/time, resolution code, and version. Advisor comment content is append-only. Advisor
cannot edit, delete, or resolve it. Admin may resolve an open flag without changing the
financial event.

### 5.4 Receipt association

`financial_event_files` contains direct workspace, event, protected file, attachment role,
attached/removed actor/time and bounded reason. One active association is unique. Removing a
link preserves association and checksum evidence; it does not ordinary-delete the file.

### 5.5 Idempotency evidence

`idempotency_records` contains workspace, operation, key, canonical request fingerprint,
`IN_PROGRESS/COMPLETED/FAILED` state, safe outcome reference/status, lease evidence, and
expiry. It stores no request/response body, credential, notes, counterparty, filename, or
amount. Terminal outcomes expire 14 days after completion; stale in-progress work is
reconciled before another execution is allowed.

Issue #81 implements this evidence in the Application Support module. The raw
`Idempotency-Key` is validated as 16 to 128 URL-safe ASCII characters and is reduced to a
SHA-256 digest before persistence. A record stores direct workspace and actor-membership
scope, a unique operation UUID, bounded operation code, key digest, request fingerprint,
state, two-minute execution lease, safe outcome code/status and optional canonical resource
reference, timestamps, and expiry. It never stores a request or response body.

The first claimant receives `STARTED`. A committed matching terminal record returns
`REPLAY`; a changed operation UUID or fingerprint raises `IDEMPOTENCY_KEY_REUSED`; a live
lease returns `IN_PROGRESS`; and an expired lease returns `RECOVERY_REQUIRED` without
executing again. Recovery must reconcile the owning canonical operation before a new attempt.
Terminal evidence is reusable until its exact 14-day expiry, after which a new claim may be
created; independent canonical-operation and source-link uniqueness still prevent a second
cash event. Every claim, completion, failure, and replay revalidates the current account,
membership, workspace, role, and required capability inside the caller-owned transaction.

Other modules import only `CanonicalFinanceEventCommand`, `FinanceCommandMetadata`, and
`CanonicalFinanceEventReference` from the Household Finance public package. They must not
import Household Finance repositories, SQLAlchemy mappings, or category/event internals.
The concrete income/expense command that implements this port remains owned by Issue #82.

## 6. State and lifecycle rules

### 6.1 Valid combinations and transitions

| Action | Before | After | Actor |
| --- | --- | --- | --- |
| Submit | None | `PENDING/NOT_EFFECTIVE` | Contributor |
| Admin create | None | `APPROVED/EFFECTIVE` | Admin |
| Edit submission | `PENDING/NOT_EFFECTIVE` | Same states, version + 1 | Owning Contributor |
| Approve | `PENDING/NOT_EFFECTIVE` | `APPROVED/EFFECTIVE` | Admin |
| Reject | `PENDING/NOT_EFFECTIVE` | `REJECTED/NOT_EFFECTIVE` | Admin |
| Reverse | `APPROVED/EFFECTIVE` | Original `APPROVED/REVERSED`; new opposite `APPROVED/EFFECTIVE` | Admin |
| Correct | `APPROVED/EFFECTIVE` | Atomic reversal plus optional replacement `APPROVED/EFFECTIVE` | Admin |
| Archive | Any terminal approval state | State unchanged; archive evidence added | Admin |

Approval/rejection requires an allowlisted reason code; rejection also requires a bounded
user explanation stored with the business decision but excluded from audit/logs. Correction,
reversal, and archive require reason, `If-Match`, explicit confirmation, and idempotency.

A reversal has the original magnitude and currency, opposite direction, and a caller-supplied
business occurred date. It cannot target itself, a reversal, a non-effective event, or a
foreign event. One effective reversal may target an original. Correction links an optional
replacement directly to the original. A later correction targets that replacement.

Archive hides an event from default active browsing but never removes an Approved effective
posting from official totals. Archived filters can retrieve it. Only reversal changes cash
effect.

### 6.2 Official dataset predicate

The Calculation/Data Quality owner exposes one reusable selector equivalent to:

`workspace matches AND approval = APPROVED AND posting = EFFECTIVE`

plus authorised period/currency/domain filters. No route, frontend, dashboard, report,
forecast, or AI module reimplements this rule. A reversal is itself effective and therefore
neutralises the reversed original through exact addition. Archived effective events remain
included.

## 7. Monthly summary and filter semantics

Business dates use `occurred_on`. A monthly bucket is the inclusive first day through the
exclusive first day of the next month in the selected workspace timezone. Since the event is
a `DATE`, server timezone cannot move it between months. UTC timestamps order audit and
creation activity only.

The summary endpoint returns an array of currency buckets. Each bucket contains exact decimal
strings for inflow, outflow, and net, its currency, `[from, to)` period, applied filters,
dataset/rule version, availability, and data-quality context. It never combines currencies or
silently converts to workspace base currency. An explicit currency filter returns one bucket.
Phase 2 has no FX conversion.

Event lists allow status, inclusive `occurred_from`, exclusive `occurred_to`, category,
event kind, direction, activity classification, payment method, currency, and documented
farming-link filters. Default order is `occurred_on DESC, created_at DESC, id ASC`; cursors
are opaque and integrity protected. Default page size is 25 and maximum 100. Unknown or
incompatible filters fail. Free-text search over Confidential finance fields is out of scope.

Contributor endpoints use distinct queries and schemas for the actor's permitted submissions.
They return no aggregate, total count, monetary summary, other submitter's Pending/Rejected
record, report, or equivalent value in body, pagination metadata, errors, files,
notifications, or caches.

## 8. API resource contract

All paths are under `/api/v1/workspaces/{workspace_id}`.

| Resource | Operations and rules |
| --- | --- |
| `/finance-categories` | GET/POST; item GET/PATCH with `If-Match`; archive command |
| `/financial-events` | GET/POST; item GET; Contributor-only eligible Pending PATCH with `If-Match` |
| `/financial-events/{id}/status-history` | Permitted chronological bounded lifecycle evidence; no payload copies or aggregates |
| `/financial-events/{id}/approvals` | Admin idempotent POST, Pending only |
| `/financial-events/{id}/rejections` | Admin idempotent POST, Pending only |
| `/financial-events/{id}/reversals` | Admin idempotent POST with `If-Match` |
| `/financial-events/{id}/corrections` | Admin atomic reversal/replacement POST with `If-Match` |
| `/financial-events/{id}/archivals` | Admin idempotent POST with `If-Match` |
| `/financial-events/{id}/reviews` | Permitted GET; Advisor/Admin designed POST |
| `/financial-event-reviews/{id}/resolutions` | Admin flag-resolution POST with `If-Match` |
| `/financial-events/{id}/receipts` | Reservation/link/status/list/removal; download through protected file route |
| `/financial-summaries/monthly` | Admin/Advisor GET; Contributor aggregate access denied |

Create, approval, rejection, reversal, correction, archive, receipt reservation/link/removal,
and review creation require `Idempotency-Key`. Current authorization is rechecked before a
stored safe outcome is returned. Lifecycle commands also require current ETag where specified;
idempotency never replaces concurrency control.

Issue #82 implements manual creation as strict `POST /financial-events`. The request carries a
client-stable canonical `operation_id`, event kind, classification, occurrence date, Active
same-workspace category, exact positive money object, payment method, and bounded optional
counterparty, reference, and notes. Direction and lifecycle state are server derived. Admin
creation commits `APPROVED/EFFECTIVE`; Contributor creation commits
`PENDING/NOT_EFFECTIVE`; Advisor creation is denied. Event, bounded audit action, and terminal
idempotency outcome commit in the same transaction, and matching replay returns the original
safe representation after current authorization is revalidated.

Issue #83 implements item and collection `GET /financial-events` reads with role predicates
inside the workspace-scoped repository. Admin reads permitted workspace events, Contributor
reads only their own submissions, and Advisor reads only Approved events. Lists accept the
allowlisted status, inclusive/exclusive occurred-date, category, kind, direction, activity,
payment, currency, and archive filters. Repeated categorical values are OR within one field;
fields combine with AND. Default browsing excludes archived events.

The stable order is `occurred_on DESC, created_at DESC, id ASC`; page size defaults to 25 and
is bounded at 100. The next cursor is integrity protected, expires after 24 hours, and is
bound to the current workspace, membership, role, filters, archive scope, and sort. List
metadata contains no count or aggregate. The response declares `ALL_PERMITTED`,
`OWN_SUBMISSIONS`, or `APPROVED_ONLY` visibility and preserves exact decimal strings.
Foreign and role-invisible item IDs are concealed, and protected responses remain no-store.
Because section 15 defers farming source links, a syntactically valid
`farming_investment_id` is recognized but returns `INVALID_FILTER` in Phase 2 rather than
being ignored or confused with FARM activity classification.

Issue #84 implements Contributor Pending correction as strict `PATCH
/financial-events/{id}`. The route accepts only a non-empty subset of category, occurred
date, activity classification, complete exact money object, payment method, counterparty,
reference, and notes. Omitted fields are unchanged; explicit null clears only optional text.
Kind, direction, creator, lifecycle state, operation identity, review evidence, and source
links remain immutable. The caller must be the original Active Contributor in the selected
workspace, the event must remain `PENDING/NOT_EFFECTIVE` and non-archived, and the effective
category/classification combination must remain Active and compatible.

Every edit requires `If-Match: "vN"`. The repository locks the own-submission row, compares
the current version, applies the validated update, preserves creator attribution, records
the current updater, increments version, and appends `FINANCIAL_EVENT_PENDING_UPDATED` audit
evidence atomically. Missing, malformed, and stale preconditions use the documented 428/412
contract; ineligible state returns `INVALID_STATE_TRANSITION`; other submitters and foreign
IDs are concealed. Admin and Advisor cannot use the Contributor edit route. Pending edits
never change posting status and therefore never enter an official dataset.

Issue #84 also implements `GET /financial-events/{id}/status-history` under the same
role-aware detail visibility. It returns chronological allowlisted action, approval status,
UTC time, and the bounded public actor classification `SUBMITTER` or `WORKSPACE_ADMIN` from
append-only audit evidence. It returns no raw membership identifier, financial value,
optional source text, payload copy, count, or aggregate.

Foreign, fabricated, disabled-module, or inaccessible identifiers return the existing safe
concealed contract. Protected finance JSON and downloads use `Cache-Control: no-store`.

## 9. Receipt lifecycle and security

Phase 2 accepts PDF, JPEG, and PNG up to 10 MiB per file. The limit is provisional and must be
capacity-tested before production. Authorization checks workspace, event, purpose, role,
declared type, and size before bytes are accepted. Storage uses a random server key; the user
filename is sanitised metadata only.

The file proceeds through `PENDING`, `QUARANTINED`, `AVAILABLE`, `FAILED`, `EXPIRED`, or
`DELETED`. Extension, MIME, signature, checksum, malware scan, and applicable sanitisation or
image re-encoding must pass before `AVAILABLE`. Partial, quarantined, failed, expired, and
deleted files are never downloadable. PDF/image inline rendering is disabled until the
implementation issue approves a safe renderer; downloads use attachment disposition,
`nosniff`, no-store, and an authorised reference valid for no more than five minutes.

The financial event may commit while a receipt is `PENDING/QUARANTINED`; scanning is outside
the finance transaction and communicates through durable file state/outbox intent. An unsafe
receipt fails without deleting or rewriting the event. If workspace policy requires a receipt,
approval fails until one linked receipt is `AVAILABLE`.

Failed/quarantined bytes are deleted 24 hours after terminal failure. Available receipts do
not automatically expire in Phase 2; they follow the linked financial record until an
approved legal/business retention rule permits deletion. Removal deactivates the link and
preserves evidence. No receipt is stored offline.

## 10. Audit and privacy contract

The Audit module adds `HOUSEHOLD_FINANCE`, resource types `FINANCE_CATEGORY`,
`FINANCIAL_EVENT`, `FINANCIAL_EVENT_REVIEW`, and `PROTECTED_FILE`, and contexts
`FINANCE_ENTRY`, `FINANCE_REVIEW`, `FINANCE_CORRECTION`, and `FINANCE_RECEIPT`.

Allowlisted action codes are:

- `FINANCE_CATEGORY_CREATED`, `FINANCE_CATEGORY_UPDATED`, `FINANCE_CATEGORY_ARCHIVED`;
- `FINANCIAL_EVENT_SUBMITTED`, `FINANCIAL_EVENT_CREATED_APPROVED`,
  `FINANCIAL_EVENT_PENDING_UPDATED`, `FINANCIAL_EVENT_APPROVED`,
  `FINANCIAL_EVENT_REJECTED`, `FINANCIAL_EVENT_REVERSED`,
  `FINANCIAL_EVENT_CORRECTED`, `FINANCIAL_EVENT_ARCHIVED`;
- `FINANCIAL_RECEIPT_RESERVED`, `FINANCIAL_RECEIPT_AVAILABLE`,
  `FINANCIAL_RECEIPT_QUARANTINED`, `FINANCIAL_RECEIPT_LINKED`,
  `FINANCIAL_RECEIPT_REMOVED`, `FINANCIAL_RECEIPT_DELETED_BY_RETENTION`; and
- `FINANCIAL_REVIEW_COMMENTED`, `FINANCIAL_REVIEW_FLAGGED`,
  `FINANCIAL_REVIEW_FLAG_RESOLVED`, `FINANCE_ACCESS_DENIED`.

Audit stores IDs, allowlisted codes, result, actor, UTC time, and correlation only. It never
stores money, currency amount, source/payee, reference, notes, review/rejection/correction
free text, filenames, file bytes, request payloads, or before/after copies. Required audit
failure rolls back the consequential finance transaction. Foreign probes carry no submitted
resource ID.

| Field group | Classification | Audience/channel rule | Retention owner |
| --- | --- | --- | --- |
| Category/event/status/date/currency code | Confidential | Workspace role/capability; no broad logs | Household Finance |
| Money, source/payee, reference, notes | Confidential; payment detail may be Restricted | Purpose-limited; masked/omitted from logs, audit, Contributor aggregates, and AI by default | Household Finance |
| Receipt bytes/name/checksum/storage key | Restricted | File Protection only; storage key never browser business data | File Protection |
| Review/rejection/correction text | Confidential | Permitted review audience; no logs/audit/AI by default | Household Finance |
| Idempotency fingerprint/outcome | Internal/Confidential | Application Support only; no raw payload | Application Support |

## 11. Transaction, concurrency, and failure boundaries

The owning application use case opens one database transaction. Event/category/review state,
required audit evidence, canonical link, and terminal idempotency outcome commit together.
External scan, email, and other integration work does not run inside it. Durable outbox intent
is committed when later processing is required.

Pending/category/review mutation uses optimistic versions. Approval/rejection/reversal locks
and rechecks current state so concurrent commands have one winner. Same idempotency key and
fingerprint returns the original safe result; a changed fingerprint returns
`IDEMPOTENCY_KEY_REUSED`. Stale state returns `VERSION_MISMATCH` or
`INVALID_STATE_TRANSITION` without partial mutation.

## 12. Migration and rollback

The additive migration order is categories, financial events, review/file associations,
same-workspace constraints/indexes, and support integration. It adds no sample or real finance
data. UUIDs are application generated. Database checks enforce positive amount, valid
state combinations, non-self reversal, and uniqueness where expressible; services enforce
cross-row transition and business rules.

Required indexes include workspace/date/id, status-kind-date, category/date,
payment/date, currency/date, creator/status/date, correction links, and open review flags.
Reference-volume query plans must prove workspace-leading access.

Clean and supported Phase 1 upgrades must pass row/constraint checks and two-workspace tests.
Before finance data exists, downgrade may remove empty Phase 2 objects. Once finance data
exists, destructive downgrade is prohibited. Rollback uses a schema-compatible prior app,
forward fix, or verified backup restore according to the incident decision; it never drops
financial history merely to deploy older code. Migrations reconcile row counts and exact
currency totals with zero unexplained difference.

## 13. UI and accessibility contract

Transactions exposes true-empty, filtered-empty, loading, unavailable, validation, conflict,
Pending, Approved, Rejected, Effective, and Reversed states. Status is not color-only. Forms
retain exact amount text and recoverable non-secret input, use persistent labels and an error
summary, and prevent duplicate submission. Approval, rejection, reversal, correction, and
archive require explicit consequence/reason confirmation.

The UI performs no official arithmetic. Summary values are backend strings in separate
currency sections. Workspace switch clears protected finance queries before rendering the new
workspace. All visible content and validation maps through English, Shan, Myanmar, and
Japanese resources and must pass keyboard, focus, 320 CSS-pixel reflow, 200-percent zoom,
30-percent expansion, and Shan linguistic review gates.

## 14. Test and acceptance matrix

| Risk | Required evidence |
| --- | --- |
| Exact values | Decimal string, scale/range/currency, no-float static checks |
| State | Full valid/invalid transition table and official-predicate tests |
| Isolation | Two-workspace IDs in URL/body/filter/cursor/review/file/summary paths |
| Roles | Admin/Contributor/Advisor positive and direct-denial matrix |
| Reconciliation | Original/reversal/replacement and monthly currency buckets at smallest unit |
| Retry/concurrency | Duplicate, changed fingerprint, in-progress, timeout-after-commit, stale ETag, concurrent decision/reversal |
| Files | Type/size/signature/name/traversal/polyglot/quarantine/expiry/download/removal |
| Privacy | Audit/log/error/cache/Contributor leakage canaries |
| Migration | Clean/prior upgrade, empty downgrade, populated rollback decision, restore reconciliation |
| UI | Component/browser/accessibility/responsive/localization and no-request assertions |

Synthetic fixtures include empty finance, two workspaces with every role, precision/currency
boundaries, all approval/posting states, reversal/replacement chains, files in every state,
and concurrent/idempotent operations. Real workspace finance data is prohibited.

## 15. Deferrals and exit conditions

Phase 2 does not implement FX conversion, farming source links, offline finance writes,
dashboard/report/AI consumers, general file management, or legal erasure. Later phases must
use the public canonical-event and official-dataset contracts established here.

The design gate is satisfied when ADR-018 is Accepted, this document and the Phase 2
traceability matrix are indexed, conflicting baseline text is corrected, and documentation
validation passes. Phase 2 exits only after Issues #78 through #96 provide executed evidence
for the milestone—not merely planned tests.
