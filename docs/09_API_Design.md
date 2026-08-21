# F2S REST API Design

## 1. Purpose and scope

This document defines the future F2S REST contract under `/api/v1/`: resources, methods, representation formats, authentication, workspace authorisation, validation, pagination, filtering, sorting, concurrency, idempotency, rate limiting, correlation, errors, asynchronous work, files, and compatibility.

It follows the [Functional Requirements](03_Functional_Requirements.md), [Use Cases](06_Use_Cases.md), [System Architecture](07_System_Architecture.md), [Database Design](08_Database_Design.md), and accepted numeric ADRs. It creates no FastAPI route, Pydantic schema, OpenAPI document, middleware, token, database object, or application code.

All examples are synthetic contract illustrations. UUIDs use reserved-looking zero-filled values and do not identify a real workspace, user, transaction, or farm.

## 2. Contract principles

1. Resources are nouns; methods and explicit subresources express intent.
2. Every workspace resource path includes `workspace_id`; the backend verifies Active membership, capability, and every referenced resource.
3. Frontend visibility, client role claims, cached permissions, and guessed UUIDs are never authorisation.
4. Authoritative decimals cross JSON as strings and retain currency/unit context.
5. Every unsafe retry has an explicit idempotency policy; every mutable aggregate has explicit concurrency behavior.
6. Error codes are stable, safe, machine-readable, and correlated without exposing protected existence or internals.
7. Lists have allowlisted filters/sorts and stable cursor pagination.
8. Long-running/external work returns a request resource; it does not keep a core transaction open.
9. Breaking behavior requires a new major API version or an approved migration/deprecation plan.

## 3. Base URL, transport, and media type

- Production requests use HTTPS only.
- The version prefix is `/api/v1` with no trailing slash in canonical links.
- JSON endpoints use `Content-Type: application/json; charset=utf-8` and accept `Accept: application/json`.
- Unsupported request media type returns `415 UNSUPPORTED_MEDIA_TYPE`.
- Upload endpoints explicitly use `multipart/form-data`; arbitrary multipart bodies are not accepted elsewhere.
- Response character encoding is UTF-8.
- Request bodies have endpoint-specific size limits. Oversize requests fail before domain processing.
- Secrets, access/refresh credentials, idempotency keys, and sensitive identifiers never appear in URL query strings.

## 4. URI and JSON naming

| Concern | Convention |
| --- | --- |
| Resource collection | Plural lowercase kebab-case: `/farming-investments` |
| Resource identifier | UUID path segment: `/farming-investments/{investment_id}` |
| Workspace scope | `/workspaces/{workspace_id}/...` for every workspace resource |
| JSON fields | Lowercase `snake_case`, aligned with canonical data terms |
| Machine codes | Stable uppercase values such as `ACTIVE` or `VALIDATION_FAILED` |
| Dates | ISO 8601 full date: `2026-01-15` |
| Instants | RFC 3339 UTC: `2026-01-15T03:04:05Z` |
| UUIDs | Lowercase canonical hyphenated string |
| Decimals | Plain decimal JSON strings; no exponent or locale separators unless a field explicitly says otherwise |
| Money | Object containing `amount` and `currency_code` |
| Quantity | Object containing `value` and `unit_code` |
| Null | Allowed only where the field contract defines absent/not-applicable/unknown meaning |

The API never uses an unlabeled numeric `amount`, `rate`, `total`, or `balance` when currency, unit, direction, period, or basis is required.

## 5. Standard response shapes

### 5.1 Single resource

```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000201",
    "workspace_id": "00000000-0000-4000-8000-000000000101",
    "status": "ACTIVE",
    "version": 3,
    "updated_at": "2026-01-15T03:04:05Z"
  }
}
```

Creation returns `201 Created`, the representation, and a canonical `Location` header. A successful action with no body returns `204 No Content`. The API does not wrap success inside `success: true`.

### 5.2 Collection

```json
{
  "data": [],
  "page": {
    "page_size": 25,
    "has_more": false,
    "next_cursor": null
  },
  "meta": {
    "filters_applied": {
      "status": ["ACTIVE"]
    },
    "sort": ["-updated_at", "id"]
  }
}
```

An empty authorised collection is `200 OK` with `data: []`; it is not `404` and never contains sample records.

### 5.3 Included metadata

`meta` is purpose-specific and may contain safe filter, period, currency/unit, formula/rule version, dataset version, availability, and data-quality context. It never widens data access or contains server internals.

## 6. Authentication and session endpoints

Protected requests use a short-lived opaque access credential:

`Authorization: Bearer <opaque-access-credential>`

The access credential is transmitted only in the header. Rotating opaque refresh credentials are server-side sessions delivered through the approved `__Host-` Secure, HttpOnly, SameSite cookie and protected by CSRF and Origin checks. Raw credentials never persist. The stable Phase 1 route families are:

| Method and path | Purpose | Auth state |
| --- | --- | --- |
| `GET /api/v1/setup/bootstrap` | Return only whether one-time installation bootstrap remains available | Public, read-only, `no-store` at the hardened edge |
| `POST /api/v1/setup/bootstrap` | Atomically create the first account, workspace, Active Admin owner membership, and audit evidence | Available only before bootstrap completion |
| `POST /api/v1/auth/activate` | Activate eligible account/membership | Eligible single-use activation evidence |
| `POST /api/v1/auth/login` | Authenticate and create server-side session | Public with rate limit; no account enumeration |
| `POST /api/v1/auth/refresh` | Rotate an eligible refresh session | Valid refresh credential plus CSRF/Origin controls |
| `POST /api/v1/auth/logout` | Revoke current session/logout | Authenticated/current refresh context as designed |
| `POST /api/v1/auth/password/change` | Change current password | Authenticated plus current/step-up proof |
| `POST /api/v1/auth/recovery/request` | Begin concealed recovery | Public with rate limit and indistinguishable response |
| `POST /api/v1/auth/recovery/confirm` | Complete eligible recovery and required revocation | Valid single-use recovery evidence |
| `GET /api/v1/me` | Return safe current actor/account summary | Authenticated |
| `GET /api/v1/me/workspaces` | Return Active memberships eligible for selection | Authenticated |

Password change accepts only strict JSON with `current_password` and `new_password`, requires
the exact configured Origin plus the current bearer session, and returns `204` on success.
Recovery request accepts an email and always returns `202` with
`{"data":{"status":"ACCEPTED"}}` after its concealed rate-limit boundary. Recovery confirm
accepts the one-time value and `new_password`; it returns `204` for the single atomic winner
or the standard concealed `401 UNAUTHENTICATED` error for invalid, expired, revoked, replayed,
ineligible, or concurrent-loser attempts. These routes use `Cache-Control: no-store` and
never return or place challenge/password material in a URL.

Invalid, expired, reused, revoked, or inactive credentials return safe authentication errors. Login, activation, refresh, and recovery responses do not reveal whether an unrelated account exists.

The initial login request is `{ "email": "...", "password": "..." }`. A successful login or
refresh returns `access_token`, `csrf_token`, `token_type`, `access_expires_at`, and
`absolute_expires_at` under `data`; it never returns the refresh value. Login, activation,
refresh, and logout are strict JSON browser mutations with exact Origin validation. Refresh
and logout require the refresh cookie plus `X-CSRF-Token`. Logout accepts
`{ "scope": "CURRENT" }` or `{ "scope": "ALL" }`, defaults to `CURRENT`, returns `204`, and
expires the cookie even when the current session is already unavailable.

Phase 1 workspace and membership routes are:

| Method and path | Purpose | Required authority |
| --- | --- | --- |
| `POST /api/v1/workspaces` | Create an additional workspace with its Active Admin owner atomically | Authenticated eligible account |
| `GET /api/v1/workspaces/{workspace_id}` | Read permitted workspace metadata and module configuration | Active workspace membership |
| `PATCH /api/v1/workspaces/{workspace_id}` | Change documented settings without changing stable identity/history | Admin |
| `GET /api/v1/workspaces/{workspace_id}/members` | List safe workspace membership information | Admin |
| `POST /api/v1/workspaces/{workspace_id}/members` | Create Pending Contributor or Advisor access | Admin |
| `PATCH /api/v1/workspaces/{workspace_id}/members/{membership_id}` | Change permitted profile, role, or suspension state | Admin; cannot create/remove Admin ownership |
| `POST /api/v1/workspaces/{workspace_id}/members/{membership_id}/reactivate` | Reactivate an eligible membership | Admin |
| `POST /api/v1/workspaces/{workspace_id}/members/{membership_id}/activation/restart` | Revoke prior activation evidence and issue a replacement | Admin |
| `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}` | Revoke eligible Contributor or Advisor access | Admin |
| `POST /api/v1/workspaces/{workspace_id}/ownership-transfers` | Initiate dedicated high-assurance ownership transfer | Current owner with recent reauthentication |
| `POST /api/v1/workspaces/{workspace_id}/ownership-transfers/{transfer_id}/confirm` | Confirm and atomically complete eligible transfer | Confirmed target plus transfer proof |
| `POST /api/v1/workspaces/{workspace_id}/ownership-transfers/{transfer_id}/cancel` | Cancel an initiated transfer | Current owner plus current transfer version |

Bootstrap, workspace creation, member creation, activation restart, recovery confirmation, and ownership-transfer confirmation define explicit idempotency and concurrency behavior. Generic membership mutation never creates a second Admin, removes the sole owner, or transfers ownership.

### 6.1 Implemented workspace selection and settings contract

`GET /api/v1/me/workspaces` returns only Active memberships whose account and workspace are
also Active. Each item contains `membership_id`, current `role`, and a safe workspace
reference: stable `id`, `name`, `type`, `base_currency_code`, `timezone`,
`preferred_language`, and `version`. It never returns administration/profile fields.

`GET /api/v1/workspaces/{workspace_id}` requires an Active membership and returns that same
safe workspace reference plus the complete explicit module configuration. An Admin also
receives `administration` with nullable `description`, `address`,
`business_category_code`, and `farm_type_code`; Contributor and Advisor responses omit that
property. The response is `Cache-Control: no-store` and carries `ETag: "vN"` for the
workspace aggregate version.

`PATCH /api/v1/workspaces/{workspace_id}` is an Admin-only strict-JSON browser mutation. It
accepts any documented subset of `name`, `type`, `base_currency_code`, `timezone`,
`preferred_language`, the four administration fields, and `modules` entries containing a
known code and Boolean `enabled`. Omitted fields remain unchanged; explicit null is accepted
only for nullable administration fields. The exact configured Origin and `If-Match: "vN"`
are required. Missing If-Match returns `428 PRECONDITION_REQUIRED`; malformed or stale values
return `412 VERSION_MISMATCH`. The repository locks and compares the workspace aggregate,
applies the complete validated state atomically, increments versions, writes settings/rename/
module audit evidence as applicable, and returns the complete Admin representation with the
new ETag.

Workspace type controls defaults only when a workspace is created. Changing type does not
reset explicit module flags, replace the stable workspace ID, delete configuration rows, or
reclassify history. Disabling a module makes it unavailable to future protected module routes
but retains existing records and configuration for later re-enablement. Unknown or foreign
workspace identifiers use the ordinary concealed `RESOURCE_NOT_FOUND` response.

### 6.2 Finance categories

Finance-category resources are always selected through
`/api/v1/workspaces/{workspace_id}/finance-categories`. `GET` is available to active Admin,
Contributor, and Advisor memberships when the Household Finance module is enabled. It lists
active categories by default; `include_archived=true` adds archived categories so historical
records remain explainable. No route exposes a category from another workspace.

`POST` creates an active category and accepts `name`, `applicability` (`INCOME`, `EXPENSE`, or
`BOTH`), and optional `activity_classification` (`HOUSEHOLD`, `FARM`, or `BUSINESS`). `PATCH
/{category_id}` renames it, and `POST /{category_id}/archivals` with an empty `{}` body archives
it. All three mutations require an active Admin membership, exact configured Origin, strict
JSON, and, for rename/archive, `If-Match: "vN"`. Successful responses contain the complete
category representation and current ETag.

Names are NFKC-normalised, trimmed, whitespace-collapsed, and compared case-insensitively
within workspace, applicability, and activity scope. An active duplicate returns `409
DUPLICATE_RESOURCE`; missing, malformed, and stale mutation versions use 428/412; attempting
to mutate an archived category returns `409 INVALID_STATE_TRANSITION`. Archival retains the
row and its historical financial-event references, while archived categories are unavailable
for selection by new financial events. Foreign identifiers use the same concealed `404
RESOURCE_NOT_FOUND` shape as absent identifiers, and successful mutations, denials, stale
versions, and invalid state transitions produce bounded audit evidence.

### 6.3 Manual income and expense creation

`POST /api/v1/workspaces/{workspace_id}/financial-events` creates one manual income or
expense. It requires an Active Admin or Contributor membership, the enabled Household
Finance module, exact configured browser Origin, strict JSON, and `Idempotency-Key`.
Advisor mutation is denied. The body contains:

- client-stable `operation_id` UUID, reused for every retry of the same canonical action;
- `event_kind` as `MANUAL_INCOME` or `MANUAL_EXPENSE`, from which the server derives
  `INFLOW` or `OUTFLOW`;
- `activity_classification`, `occurred_on`, and an Active same-workspace
  `finance_category_id` compatible with the kind and classification;
- `money` containing a strictly positive ordinary decimal string and approved
  `currency_code`;
- `payment_method`; and
- optional bounded `counterparty`, `reference`, and `notes` strings.

The client cannot submit direction, creator, approval status, posting status, reviewer, or
version. An Admin create returns `APPROVED/EFFECTIVE`; a Contributor create returns
`PENDING/NOT_EFFECTIVE`, and the Pending event is excluded from official datasets. Success
returns `201`, the complete event representation, `Location`, and
`Idempotency-Replayed: false|true`. Money remains a fixed-scale JSON string paired with its
currency.

The event, required safe audit evidence, and terminal idempotency outcome use one caller-owned
database transaction. A matching retry returns the original event after current authority is
revalidated. A changed fingerprint returns `409 IDEMPOTENCY_KEY_REUSED`; a live or stale
execution lease returns a safe conflict without running again. Missing, archived, or foreign
categories use concealed `404 RESOURCE_NOT_FOUND`; locally incompatible categories and exact
numeric violations use safe validation failure. No error stores or reflects money,
counterparty, reference, notes, raw idempotency key, or request body in audit/idempotency
evidence.

### 6.4 Financial-event detail and filtered lists

`GET /api/v1/workspaces/{workspace_id}/financial-events/{event_id}` and collection `GET`
require an Active same-workspace membership and the enabled Household Finance module. Admin
may read permitted workspace events, Contributor reads only their own submissions, and
Advisor reads only Approved events. These predicates are applied in the database query;
foreign, fabricated, and role-invisible item IDs all return the same concealed `404
RESOURCE_NOT_FOUND`. Item responses carry the current ETag. Every protected response uses
`Cache-Control: no-store`.

The collection accepts repeated `status`, `category_id`, `event_kind`, `direction`,
`activity_classification`, `payment_method`, and `currency` parameters as OR within that
field. Different fields combine with AND. `occurred_from` is inclusive and `occurred_to` is
exclusive; both are business dates and `occurred_from` must be earlier than `occurred_to`.
`archived=ACTIVE|ARCHIVED|ALL` defaults to `ACTIVE`. Default and only Phase 2 sort is
`-occurred_on,-created_at,id`. `page_size` defaults to 25 and accepts 1 through 100.

`farming_investment_id` is a recognized but incompatible Phase 2 filter because the focused
design explicitly defers canonical farming source links. It returns `400 INVALID_FILTER`
rather than being ignored or interpreted as FARM classification. Unknown parameters return
`400 UNKNOWN_FILTER`; unsupported sorts return `400 INVALID_SORT`; malformed, unsupported,
or role-incompatible values return `400 INVALID_FILTER`.

Lists use keyset pagination over `occurred_on DESC, created_at DESC, id ASC`. `next_cursor`
is an integrity-protected, 24-hour, opaque value bound to the workspace, current membership,
role, filters, archive scope, and sort. A malformed, expired, tampered, cross-scope, or
filter-incompatible cursor returns `400 INVALID_CURSOR`. Responses contain `data` and only
`next_cursor`, `page_size`, effective `sort`, and a role visibility code in `meta`; they never
contain a total count or financial aggregate. Money is always a fixed-scale string paired
with its currency.

### 6.5 Contributor Pending edits and status history

`PATCH /api/v1/workspaces/{workspace_id}/financial-events/{event_id}` is available only to
an Active Contributor for their own `PENDING/NOT_EFFECTIVE`, non-archived submission. It
requires the configured browser Origin and `If-Match: "vN"`. A successful edit increments
the version and returns the complete Pending representation with its new ETag.

The allowlisted mutable fields are `activity_classification`, `occurred_on`,
`finance_category_id`, the complete `money` object, `payment_method`, `counterparty`,
`reference`, and `notes`. Omitted fields remain unchanged. Explicit null clears only the
three optional text fields. Event kind, cash direction, creator, lifecycle state, operation
identity, review evidence, and canonical links are never client-mutable. Any selected
category must remain Active, same-workspace, and compatible with the fixed event kind and
effective activity classification; money retains the strict exact-decimal contract.

The repository locks the own-submission row, compares its version, rechecks state and
category policy, applies the complete validated change, preserves creator attribution, and
records the current Contributor as updater in the same transaction as bounded
`FINANCIAL_EVENT_PENDING_UPDATED` audit evidence. Missing `If-Match` returns `428
PRECONDITION_REQUIRED`; malformed or stale values return `412 VERSION_MISMATCH`; Approved,
Rejected, or otherwise ineligible records return `409 INVALID_STATE_TRANSITION`. Another
Contributor's event and foreign or fabricated IDs use concealed `404 RESOURCE_NOT_FOUND`.
Admin and Advisor calls are denied because this PATCH is Contributor-only.

`GET /api/v1/workspaces/{workspace_id}/financial-events/{event_id}/status-history` follows
the same role and workspace visibility predicate as event detail. It returns chronological,
bounded action/status/time entries derived from append-only audit evidence. The public actor
classification is only `SUBMITTER` or `WORKSPACE_ADMIN`; raw membership identifiers, request
payloads, money, optional text, counts, and aggregates are not returned. Pending edits remain
`NOT_EFFECTIVE` and therefore stay outside every official dataset.

### 6.6 Admin financial-event decisions

`POST /api/v1/workspaces/{workspace_id}/financial-events/{event_id}/approvals` and
`POST /api/v1/workspaces/{workspace_id}/financial-events/{event_id}/rejections` are
available only to an Active Admin with the Household Finance module enabled. Both require
the configured browser Origin, strict JSON, and `Idempotency-Key`. They do not require
`If-Match`: the repository serializes decisions with a row lock and rechecks the current
state after acquiring it.

The approval body contains a client-stable `operation_id` and the sole approval reason code
`REVIEWED_AND_CONFIRMED`. The rejection body contains a client-stable `operation_id`, one of
`DUPLICATE`, `INCORRECT_AMOUNT`, `INCORRECT_CATEGORY`, `INCORRECT_DATE`,
`INSUFFICIENT_EVIDENCE`, or `OTHER`, and a required explanation of 1 through 512 normalized
characters. Approval explanations are not accepted. Rejection explanations are
Confidential business evidence: they are stored on the financial event but never copied to
audit, logs, idempotency evidence, safe errors, or the decision response.

Only `PENDING/NOT_EFFECTIVE` can transition. Approval atomically produces
`APPROVED/EFFECTIVE`; rejection atomically produces `REJECTED/NOT_EFFECTIVE`. The decision
records reviewer/time/reason, increments the version, appends the corresponding bounded
`FINANCIAL_EVENT_APPROVED` or `FINANCIAL_EVENT_REJECTED` audit event, and completes the
terminal idempotency outcome in the same transaction. Success returns the complete event,
its new ETag, and `Idempotency-Replayed: false|true`.

Matching retries return the original safe result after current Admin authority is
revalidated. Changed fingerprints return `409 IDEMPOTENCY_KEY_REUSED`; a repeated, stale,
or losing concurrent decision returns `409 INVALID_STATE_TRANSITION`. Contributor and
Advisor requests return `403 PERMISSION_DENIED`; foreign or fabricated event identifiers
use concealed `404 RESOURCE_NOT_FOUND`. Exactly one concurrent decision can win. Only the
`APPROVED/EFFECTIVE` result satisfies the official-dataset predicate; Rejected and failed
decisions contribute nothing.

### 6.7 Implemented membership lifecycle contract

`GET /api/v1/workspaces/{workspace_id}/members` is Admin-only and returns membership ID,
associated email, display name, role, membership status, bounded account status, language,
timezone, last-login time, creation time, and membership version. It does not expose a global
account ID, password/credential data, session identifiers, or another workspace's membership.

Every membership mutation requires an Active Admin context, exact configured Origin, strict
JSON content type, and `If-Match: "vN"`. Missing, malformed, or stale versions use the same
428/412 precondition outcomes as workspace settings. PATCH accepts exactly one operation:
`{"role":"CONTRIBUTOR|ADVISOR"}` or `{"status":"SUSPENDED"}`. Reactivation, activation
restart, and DELETE accept an empty `{}` command body. DELETE revokes access and retains the
historical membership row. Successful non-DELETE mutations return the resulting
representation or an empty command response with the new membership ETag; DELETE returns 204
with the new ETag.

| Current status | Operation | Result |
| --- | --- | --- |
| Pending | Contributor/Advisor role change | Pending with new role |
| Pending | Activation restart | Pending with replacement single-use challenge |
| Pending | Revoke | Revoked; issued activation challenges revoked |
| Active | Contributor/Advisor role change | Active with new role |
| Active | Suspend | Suspended |
| Active | Revoke | Revoked |
| Suspended | Contributor/Advisor role change | Suspended with new role |
| Suspended | Reactivate, when account is Active | Active |
| Suspended | Revoke | Revoked |
| Revoked | Any generic lifecycle operation | `409 INVALID_STATE_TRANSITION` |
| Admin owner | Any generic role/lifecycle operation | `409 OWNERSHIP_TRANSFER_REQUIRED` |

Role change, suspension, and revocation revoke every Active account-scoped session for the
affected user. This intentionally requires reauthentication even for another workspace;
Phase 1 has no workspace-bound session that could be revoked more narrowly. Protected
authorization also rechecks current membership state and role on every request. Foreign IDs
remain concealed, stale writes have no lifecycle side effect, and successful/denied changes
write bounded audit evidence without submitted profile or identifier payloads.

### 6.8 Implemented ownership-transfer contract

Ownership transfer is a strict-JSON, exact-Origin browser workflow and never a membership
PATCH. Initiation accepts `target_membership_id`, the former owner's destination role
(`CONTRIBUTOR` or `ADVISOR`), and `current_password`. The active session and Argon2id current
password are revalidated against the sole Active Admin owner. The target must be a distinct
Active same-workspace Contributor or Advisor backed by an Active account.

A successful initiation returns `201`, `Location`, `Cache-Control: no-store`, `ETag: "v1"`,
and a safe transfer representation. It creates a 30-minute random confirmation value, stores
only its purpose-separated keyed digest, and sends the clear value exactly once through the
configured target delivery boundary. Reauthentication failure returns
`401 REAUTHENTICATION_REQUIRED`; foreign or ineligible target identifiers remain concealed as
`404 RESOURCE_NOT_FOUND`. Starting a replacement transfer cancels an earlier live transfer
under the workspace lock and audits that transition.

Confirmation requires an authenticated Active target membership and the clear transfer value.
The repository locks the workspace, transfer, and both memberships. It validates target
binding, digest, state, expiry, account/membership eligibility, and the unchanged current
owner. One transaction records confirmation, demotes the former owner to the selected role,
promotes the target to Admin, moves the workspace owner reference, completes the transfer,
revokes every Active session for both accounts, appends audit evidence, and emits one batch of
completion-notification intents. Required audit or notification failure rolls back the whole
transaction. Concurrent confirmation has one winner; replay and invalid/expired proof return
the same `401 TRANSFER_CONFIRMATION_DENIED` representation without echoing identifiers or
proof material.

Cancellation accepts `{}` and requires `If-Match: "vN"`; it returns `204` only while the
current owner and transfer are still eligible. Missing versions return 428, stale versions
return 412, and terminal or expired state returns 409. The persisted lifecycle is
`INITIATED` to `COMPLETED` through confirmation, or `INITIATED` to `CANCELLED`/`EXPIRED`.
`CONFIRMED` evidence is stored before the same transaction reaches `COMPLETED`; it is never a
window in which two owners can commit.

## 7. Workspace context and authorisation

All workspace business paths begin:

`/api/v1/workspaces/{workspace_id}`

Examples:

- `/api/v1/workspaces/{workspace_id}/financial-events`
- `/api/v1/workspaces/{workspace_id}/farming-investments/{investment_id}`
- `/api/v1/workspaces/{workspace_id}/reports/{report_request_id}`

The backend performs, in order:

1. authenticate the actor;
2. load an Active membership for the path workspace;
3. evaluate the required capability against the current `ADMIN`, `CONTRIBUTOR`, or `ADVISOR` role;
4. verify every path/body/query reference belongs to the same workspace;
5. scope repository queries by workspace; and
6. record policy-required safe audit evidence.

An `X-Workspace-ID` header does not override the path and is not an authorisation source. Body `workspace_id` is omitted where the path already supplies it or, if present in a documented schema, must match exactly. Client-supplied user, role, owner, approval, or workspace claims are never authoritative.

Response semantics:

- Missing/invalid authentication: `401 UNAUTHENTICATED`.
- Authenticated actor lacks a general known capability in their workspace: `403 PERMISSION_DENIED`.
- Unknown, foreign-workspace, or intentionally concealed resource identifier: `404 RESOURCE_NOT_FOUND`, identical safe shape.
- Inactive/deactivated membership: `403 MEMBERSHIP_INACTIVE` without protected data.

## 8. HTTP method semantics

| Method | Use | Requirements |
| --- | --- | --- |
| `GET` | Read collection/resource/status | Safe, read-only, no hidden mutation |
| `POST` | Create resource or explicit command/subresource | Idempotency required where retry could duplicate or cause harm |
| `PATCH` | Partial update of documented mutable source fields | `If-Match` required; omitted fields unchanged; null follows field contract |
| `PUT` | Complete replacement | Not used unless a resource explicitly defines replace semantics |
| `DELETE` | Remove/revoke only resources whose domain permits deletion | Never ordinary deletion of finance/farming/payment/audit history |

Lifecycle and correction behavior uses explicit subresources rather than ambiguous patches:

- `POST .../farming-investments/{id}/cancellations`
- `POST .../farming-investments/{id}/archivals`
- `POST .../farming-investments/{id}/restorations`
- `POST .../financial-events/{id}/reversals`
- `POST .../receivable-payments/{id}/reversals`

These commands require confirmation fields/reasons where specified and return the resulting authoritative resource/state.

## 9. Resource catalogue

The catalogue defines resource families, not complete route/schema implementation.

| Workspace-relative collection | Typical methods | Notes |
| --- | --- | --- |
| `/members` | GET, POST, PATCH, DELETE plus reactivation and activation-restart subresources | Admin only; roles limited to Contributor/Advisor; ownership transfer separate |
| `/ownership-transfers` | POST plus confirmation subresource | Dedicated recent-reauthenticated owner flow; never generic role PATCH |
| Workspace resource and module configuration | GET/PATCH workspace; validated module changes | Admin only; consequential changes confirmed/audited |
| `/farm-locations` | GET/POST/PATCH/archive | Workspace-scoped; historical references preserved |
| `/finance-categories`, `/crop-categories` | GET/POST/PATCH/archive | Archive preserves history |
| `/financial-events` | GET/POST; item GET; reversal subresource | Posted facts immutable; filtered authorised lists |
| `/farming-investments` | GET/POST/PATCH; lifecycle subresources | Calculated fields read-only |
| `/farm-costs`, `/harvests`, `/crop-sales` | GET/POST/PATCH/correction as allowed | Canonical links and atomic validation |
| `/remittances`, `/debts`, `/receivables` | GET/POST/PATCH plus payment/correction subresources | Balances/outstanding derived |
| `/planning-scenarios` | GET/POST/PATCH/archive; version resources | Hypothetical only; immutable versions |
| `/crop-comparisons`, `/dashboard` | GET | Verified datasets with period/quality context |
| `/report-requests` | GET/POST; status; cancellation | Asynchronous generation; artifact/download links protected |
| `/ai-advice-requests` | GET/POST; status/cancellation where possible | Authorised/masked before provider call |
| `/audit-events` | GET | Separately permissioned, read-only, allowlisted filters |
| `/files` | Purpose-specific upload metadata/status/download | Type/size/name/path/expiry enforcement |

Nested resources are used when the parent is necessary to establish meaning, such as `/debts/{debt_id}/payments`. Deep nesting beyond the ownership/use-case need is avoided.

## 10. Validation and decimal rules

- Malformed JSON, duplicate keys where detected, unknown query syntax, or structurally invalid request framing returns `400 MALFORMED_REQUEST`.
- Well-formed JSON failing field/domain validation returns `422 VALIDATION_FAILED` with safe field details.
- Unknown request fields are rejected by default for commands; forward-compatible metadata is never silently persisted.
- Required strings are trimmed only where the field contract permits; empty string is not automatically null.
- Authoritative decimals are strings and validated for sign, digits, scale, range, and semantic context before `Decimal` construction.
- Money is `{ "amount": "10.50", "currency_code": "USD" }`; ordinary excess scale is rejected, not rounded silently.
- Quantity is `{ "value": "125.750", "unit_code": "KG" }`.
- Ratio `"0.075"` means 7.5 percent; API field names distinguish ratio, percent display, interest basis, and FX direction.
- Zero-denominator calculations return typed unavailable results/reasons in verified datasets, not transport errors when the request itself is valid.
- Cross-field/date/state/relationship failures identify stable codes without exposing foreign data.

## 11. Pagination, filtering, searching, and sorting

### 11.1 Cursor pagination

- Collection default `page_size` is 25; initial maximum is 100 and remains configurable/validated.
- `after` carries an opaque signed or integrity-protected cursor; clients do not construct/inspect it.
- Cursor encodes the allowlisted sort position and filter compatibility, not sensitive raw data.
- Stable ordering always includes `id` as final tie-breaker.
- Invalid/expired/incompatible cursor returns `400 INVALID_CURSOR`.
- Offset/page-number pagination is not the default for mutable business collections.

Example:

`GET /api/v1/workspaces/{workspace_id}/financial-events?page_size=25&after=<opaque>&sort=-occurred_on,id`

### 11.2 Filters

Filters are explicit allowlisted query parameters, for example `status`, `occurred_from`, `occurred_to`, `category_id`, `payment_method`, `crop_category_id`, or `farming_investment_id`. Repeating a documented parameter expresses OR within that field; different fields combine with AND unless documented otherwise.

- Date ranges are inclusive/exclusive semantics documented per field and validated for order.
- Unknown filters return `400 UNKNOWN_FILTER` rather than being ignored.
- A filter referencing another workspace is safely not found/denied and never broadens results.
- Free-text search is purpose-specific, length-limited, normalised, escaped/parameterised, and never searches Restricted fields by default.

### 11.3 Sorting

`sort=field,-descending_field` uses an allowlist. Unknown/duplicate/incompatible sort fields return `400 INVALID_SORT`. The response reports the effective stable sort.

## 12. Optimistic concurrency

Mutable resource responses include:

`ETag: "v3"`

`PATCH` and lifecycle commands that depend on current state require:

`If-Match: "v3"`

- Missing required precondition: `428 PRECONDITION_REQUIRED`.
- Stale/mismatched version: `412 VERSION_MISMATCH` with safe current-resource link/instruction, not an overwrite.
- Successful mutation returns the new representation and ETag.
- ETags are opaque validators, not security tokens.
- Immutable posted events and version rows do not support ordinary PATCH.

## 13. Idempotency and duplicate protection

`Idempotency-Key` is required for retryable/high-impact POST commands including finance creation/reversal, farm costs, sales/payments, remittances, debt/receivable payments, farming-investment creation, report requests, AI requests, and approved offline queue replay.

Rules:

1. Key is an opaque client-generated bounded value and contains no personal data.
2. Scope includes authenticated actor/current authority, workspace, method, canonical route/operation, and key.
3. Server stores a canonical request fingerprint and outcome for the approved retry window.
4. Same key and same fingerprint returns the original status/body/Location where safe, with replay metadata.
5. Same key and different fingerprint returns `409 IDEMPOTENCY_KEY_REUSED`.
6. In-progress duplicate returns the documented original/in-progress response, never executes a second operation.
7. Current authentication, membership, and authorisation are revalidated before replaying protected output.
8. Household Finance terminal outcomes are retained for exactly 14 days under ADR-018.
   Other operation classes require an approved owner-specific retention value.

The implemented finance-support boundary stores only SHA-256 key and canonical-request
digests plus a safe outcome status/reference; it never stores the raw key, request body, or
response body. Its internal dispositions are `STARTED`, `REPLAY`, `IN_PROGRESS`, and
`RECOVERY_REQUIRED`. A live or stale lease never authorizes a second execution. Concrete
finance endpoints map these dispositions to their documented safe HTTP response in the issue
that implements the command, while changed fingerprints always use `409
IDEMPOTENCY_KEY_REUSED`.

Idempotency does not replace optimistic concurrency, uniqueness constraints, or canonical-event links.

## 14. Correlation and observability

- Client may send `X-Correlation-ID` only in the documented safe syntax/length; invalid values are replaced or rejected per Issue #11.
- Server generates a correlation ID when absent and always returns `X-Correlation-ID`.
- Every error envelope includes `correlation_id`.
- Correlation propagates to safe logs, audit intent, database transaction metadata where appropriate, report/AI requests, and external-call metadata.
- Correlation IDs contain no workspace/user/business meaning and do not grant access.

## 15. Error contract

All non-success JSON errors use:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "The request contains invalid fields.",
    "correlation_id": "00000000-0000-4000-8000-000000000901",
    "details": [
      {
        "field": "planned_budget.amount",
        "code": "INVALID_SCALE",
        "message": "The value has too many decimal places for the selected currency."
      }
    ]
  }
}
```

Rules:

- `code` is stable and used by clients/tests; HTTP reason text and translated UI messages are not stable identifiers.
- `message` is safe English fallback; clients map code/details to localised Shan-first text.
- `details` is optional and ordered deterministically; field paths use request JSON names.
- Errors contain no stack trace, SQL, secret, token, internal class/path, raw provider payload, another workspace's existence, or prohibited personal/payment data.
- HTML proxy errors are normalised where the edge/backend contract allows; clients must still handle transport failure.

### 15.1 Status and stable code catalogue

| HTTP | Stable code | Meaning |
| --- | --- | --- |
| 400 | `MALFORMED_REQUEST`, `INVALID_CURSOR`, `UNKNOWN_FILTER`, `INVALID_SORT` | Request/query cannot be interpreted safely |
| 401 | `UNAUTHENTICATED`, `SESSION_EXPIRED`, `TOKEN_REUSED` | Authentication absent/invalid/expired/reused |
| 403 | `PERMISSION_DENIED`, `MEMBERSHIP_INACTIVE` | Known workspace capability denied without foreign-resource disclosure |
| 404 | `RESOURCE_NOT_FOUND` | Missing or concealed foreign resource; same safe shape |
| 409 | `CONFLICT`, `DUPLICATE_RESOURCE`, `IDEMPOTENCY_KEY_REUSED`, `INVALID_STATE_TRANSITION` | Current state/uniqueness/replay conflict |
| 412 | `VERSION_MISMATCH` | `If-Match` no longer current |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Request media not supported |
| 422 | `VALIDATION_FAILED` | Field/domain validation failed |
| 428 | `PRECONDITION_REQUIRED` | Required ETag/precondition omitted |
| 429 | `RATE_LIMITED` | Approved limit exceeded; includes `Retry-After` when known |
| 500 | `INTERNAL_ERROR` | Unexpected internal failure; safe correlation only |
| 502/503/504 | `DEPENDENCY_UNAVAILABLE`, `SERVICE_UNAVAILABLE`, `DEPENDENCY_TIMEOUT` | Provider/service unavailable or timed out |

Specific validation detail codes include `REQUIRED`, `INVALID_FORMAT`, `OUT_OF_RANGE`, `INVALID_SCALE`, `CURRENCY_MISMATCH`, `UNIT_MISMATCH`, `INVALID_DATE_RANGE`, `RELATIONSHIP_INVALID`, and `ZERO_DENOMINATOR` only where a requested operation cannot proceed rather than where an unavailable calculated result is valid output.

## 16. Rate limiting and abuse controls

- Limits are defined by endpoint/risk class, actor, workspace, credential/IP/device signals as approved by the security design; exact numbers are `TBD-VALIDATE`.
- Authentication, activation/recovery, uploads, report generation, exports, AI, and expensive search/aggregation have distinct policies.
- A rejected request returns `429 RATE_LIMITED`, safe message/correlation, and `Retry-After` when the server knows the delay.
- Rate-limit metadata never reveals another account/workspace or internal capacity.
- Limits are enforced before expensive/provider work and cannot be bypassed by changing workspace IDs or idempotency keys.
- Successful idempotent replay may have a separate low-cost policy but still checks abuse controls.

## 17. Asynchronous requests

Report generation, AI advice, and other approved long-running work use request resources.

1. `POST` validates auth/scope/input/idempotency and creates request state.
2. Return `202 Accepted` with `Location` to the request resource unless work completed synchronously under a documented contract.
3. Client `GET`s the resource or uses approved future notification; aggressive polling is rate-limited.
4. States are stable codes from the data dictionary with timestamps and safe failure code.
5. Cancellation is an explicit subresource and is best effort after external transmission/rendering starts.
6. A successful report exposes a protected expiring artifact/download link only after complete validation.
7. Provider/render failure never changes committed source finance/farming data.

## 18. Files and downloads

- Upload request is authorised for workspace, purpose, parent resource, type, and size before content is accepted.
- User filename is metadata only; storage key/path is server generated.
- Media type, extension, content signature, checksum, and malware/quarantine policy follow Issue #11/#13.
- Upload status is explicit; partial/quarantined/failed file is unavailable.
- Download uses an authorised endpoint or short-lived unguessable reference; access rechecks workspace, purpose, resource, status, and expiry.
- `Content-Disposition` uses a sanitised safe filename.
- Range/caching behavior is explicitly allowlisted; protected JSON/files default to `Cache-Control: no-store` unless a later design safely approves private caching.
- Cross-workspace, traversed, expired, or guessed file references return safe not-found behavior.

## 19. Caching and conditional requests

- Protected business responses default to `Cache-Control: no-store` until endpoint-specific private caching is approved.
- ETag is used for concurrency/conditional reads where documented, not shared public caching.
- `304 Not Modified` may be used only when authorisation is revalidated and representation scope/filters/workspace are identical.
- API/proxy caches must include authorisation and workspace boundaries; a shared cache of workspace responses is prohibited by default.

## 20. Compatibility and deprecation

- `/api/v1` is the first major contract. Paths, field meaning, numeric semantics, permission behavior, and stable error codes are compatibility surface.
- Additive optional response fields may be added within v1; clients must ignore unknown response fields.
- Request schemas reject unknown fields unless a documented extension object exists.
- Removing/renaming fields, changing meaning/type/nullability, narrowing accepted values unexpectedly, changing auth/workspace semantics, or reusing an error/state code requires v2 or an approved staged migration.
- Deprecation is documented with replacement, notice period, telemetry/privacy review, and when applicable `Deprecation`/`Sunset`/`Link` headers.
- Retired codes remain documented and are not reused for different meaning.
- Database identifiers/internal module names are not API compatibility guarantees unless explicitly exposed.

## 21. Representative synthetic examples

### 21.1 Create a farming investment

```http
POST /api/v1/workspaces/00000000-0000-4000-8000-000000000101/farming-investments HTTP/1.1
Authorization: Bearer <access-token>
Content-Type: application/json
Idempotency-Key: synthetic-create-investment-001

{
  "crop_category_id": "00000000-0000-4000-8000-000000000301",
  "farm_location_id": "00000000-0000-4000-8000-000000000302",
  "season": "SYNTHETIC_SEASON",
  "year": 2026,
  "field_size": {"value": "1.25000000", "unit_code": "HECTARE"},
  "planned_budget": {"amount": "125000", "currency_code": "MMK"},
  "initial_status": "PLANNED"
}
```

### 21.2 Safe concealed resource response

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found.",
    "correlation_id": "00000000-0000-4000-8000-000000000902"
  }
}
```

The same shape applies whether the UUID is absent or belongs to another workspace.

## 22. Security and privacy requirements

- Authentication/authorisation occurs before protected parsing/query/provider work where possible.
- Every referenced ID, filter, cursor, include, aggregate, job, file, report, audit query, and AI dataset remains workspace scoped.
- Contributor response schemas and queries omit restricted totals, reports, and indirect aggregates; official consumers select only Approved records.
- Logs/audit/errors exclude credentials, headers, secrets, full payment data, report bytes, sensitive attachments, and unmasked AI payloads.
- Sensitive request/response bodies are not recorded by default observability middleware.
- CORS, CSRF, cookies, security headers, token storage, cryptography, exact limits, upload scanning, and retention are finalized by Issue #11 without weakening this contract.
- OpenAPI/docs exposure in production is an explicit security/deployment decision; documentation never includes real credentials or workspace examples.

## 23. Validation matrix

| Area | Required future evidence |
| --- | --- |
| Resource consistency | Naming/method/subresource review across every module |
| Authentication | Missing/invalid/expired/reused/revoked/deactivated lifecycle tests |
| Authorisation | Two-workspace URL/body/filter/cursor/include/file/job/report/AI identifier substitution plus role/capability denial |
| Errors | Every code/status/envelope validated; no stack/SQL/existence/sensitive leak |
| Decimals | String, range, scale, currency, rate, ratio, quantity, zero-denominator cases |
| Pagination | Stable order, no duplicate/skip under updates, invalid/tampered/incompatible cursor |
| Idempotency | Same/different fingerprint, concurrent, in-progress, timeout-after-commit, expired key, lost permission |
| Concurrency | Missing/stale/matching ETag and conflicting lifecycle transitions |
| Rate limit | Threshold, Retry-After, recovery, distributed signal, no account enumeration |
| Async/provider | Queued/success/failure/cancel/timeout/retry; core records unchanged |
| Files | Type/size/signature/name/traversal/quarantine/expiry/cross-workspace/download tests |
| Compatibility | Contract diff detects breaking field/code/auth/permission changes |

## 24. Deferred decisions and Issue #9 acceptance

Deferred to later issues: exact request/response schemas per feature, access/refresh token format/lifetime/transport, CORS/CSRF/cookie details, numeric rate-limit thresholds, cursor signing mechanism, upload malware tooling, report/AI payload schemas, polling intervals, OpenAPI generation/hosting, and code layout.

Issue #9 remains satisfied when review confirms a consistent `/api/v1` resource/method model, stable safe error envelope/codes, explicit workspace authorisation, decimal formats, cursor/filter/sort rules, idempotency/concurrency/rate-limit/correlation behavior, synthetic-only examples, compatibility rules, and no routes, schemas, OpenAPI implementation, or application code.
