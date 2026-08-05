# F2S REST API Design

## 1. Purpose and scope

This document defines the future F2S REST contract under `/api/v1/`: resources, methods, representation formats, authentication, household authorisation, validation, pagination, filtering, sorting, concurrency, idempotency, rate limiting, correlation, errors, asynchronous work, files, and compatibility.

It follows the [Functional Requirements](03_Functional_Requirements.md), [Use Cases](06_Use_Cases.md), [System Architecture](07_System_Architecture.md), [Database Design](08_Database_Design.md), and accepted numeric ADRs. It creates no FastAPI route, Pydantic schema, OpenAPI document, middleware, token, database object, or application code.

All examples are synthetic contract illustrations. UUIDs use reserved-looking zero-filled values and do not identify a real household, user, transaction, or farm.

## 2. Contract principles

1. Resources are nouns; methods and explicit subresources express intent.
2. Every household resource path includes `household_id`; the backend verifies active membership, capability, and every referenced resource.
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
| Household scope | `/households/{household_id}/...` for every household resource |
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
    "household_id": "00000000-0000-4000-8000-000000000101",
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

Protected requests use:

`Authorization: Bearer <access-token>`

The token is transmitted only in the header. Exact token format, signing, lifetimes, rotation grace, cookie/refresh transport, revocation storage, password rules, and CSRF design are finalized by Issue #11. The stable resource intentions are:

| Method and path | Purpose | Auth state |
| --- | --- | --- |
| `POST /api/v1/auth/activations` | Activate eligible invitation/account | Eligible activation evidence |
| `POST /api/v1/auth/sessions` | Authenticate and create session | Public with rate limit; no account enumeration |
| `POST /api/v1/auth/session-refreshes` | Rotate an eligible refresh session | Valid refresh credential |
| `DELETE /api/v1/auth/session` | Revoke current session/logout | Authenticated/current refresh context as designed |
| `POST /api/v1/auth/password-changes` | Change current password | Authenticated plus current/step-up proof |
| `GET /api/v1/me` | Return safe current actor/account summary | Authenticated |
| `GET /api/v1/me/households` | Return memberships eligible for selection | Authenticated |

Invalid, expired, reused, revoked, or deactivated credentials return safe authentication errors. Login, activation, refresh, and recovery responses do not reveal whether an unrelated account exists.

## 7. Household context and authorisation

All household business paths begin:

`/api/v1/households/{household_id}`

Examples:

- `/api/v1/households/{household_id}/financial-events`
- `/api/v1/households/{household_id}/farming-investments/{investment_id}`
- `/api/v1/households/{household_id}/reports/{report_request_id}`

The backend performs, in order:

1. authenticate the actor;
2. load an active membership for the path household;
3. evaluate the required capability against current role/delegation;
4. verify every path/body/query reference belongs to the same household;
5. scope repository queries by household; and
6. record policy-required safe audit evidence.

An `X-Household-ID` header does not override the path and is not an authorisation source. Body `household_id` is omitted where the path already supplies it or, if present in a documented schema, must match exactly.

Response semantics:

- Missing/invalid authentication: `401 UNAUTHENTICATED`.
- Authenticated actor lacks a general known capability in their household: `403 PERMISSION_DENIED`.
- Unknown, foreign-household, or intentionally concealed resource identifier: `404 RESOURCE_NOT_FOUND`, identical safe shape.
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

| Household-relative collection | Typical methods | Notes |
| --- | --- | --- |
| `/memberships`, `/invitations` | GET, POST, PATCH plus activation/deactivation/role subresources | Owner/delegated admin only; ownership transfer separate |
| `/settings`, `/farm-locations` | GET/PATCH; GET/POST/PATCH/archive | Consequential changes confirmed/audited |
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

`GET /api/v1/households/{household_id}/financial-events?page_size=25&after=<opaque>&sort=-occurred_on,id`

### 11.2 Filters

Filters are explicit allowlisted query parameters, for example `status`, `occurred_from`, `occurred_to`, `category_id`, `payment_method`, `crop_category_id`, or `farming_investment_id`. Repeating a documented parameter expresses OR within that field; different fields combine with AND unless documented otherwise.

- Date ranges are inclusive/exclusive semantics documented per field and validated for order.
- Unknown filters return `400 UNKNOWN_FILTER` rather than being ignored.
- A filter referencing another household is safely not found/denied and never broadens results.
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
2. Scope includes authenticated actor/current authority, household, method, canonical route/operation, and key.
3. Server stores a canonical request fingerprint and outcome for the approved retry window.
4. Same key and same fingerprint returns the original status/body/Location where safe, with replay metadata.
5. Same key and different fingerprint returns `409 IDEMPOTENCY_KEY_REUSED`.
6. In-progress duplicate returns the documented original/in-progress response, never executes a second operation.
7. Current authentication, membership, and authorisation are revalidated before replaying protected output.
8. Numeric retention duration is set by Issues #10/#11 after offline/retry evidence.

Idempotency does not replace optimistic concurrency, uniqueness constraints, or canonical-event links.

## 14. Correlation and observability

- Client may send `X-Correlation-ID` only in the documented safe syntax/length; invalid values are replaced or rejected per Issue #11.
- Server generates a correlation ID when absent and always returns `X-Correlation-ID`.
- Every error envelope includes `correlation_id`.
- Correlation propagates to safe logs, audit intent, database transaction metadata where appropriate, report/AI requests, and external-call metadata.
- Correlation IDs contain no household/user/business meaning and do not grant access.

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
- Errors contain no stack trace, SQL, secret, token, internal class/path, raw provider payload, another household's existence, or prohibited personal/payment data.
- HTML proxy errors are normalised where the edge/backend contract allows; clients must still handle transport failure.

### 15.1 Status and stable code catalogue

| HTTP | Stable code | Meaning |
| --- | --- | --- |
| 400 | `MALFORMED_REQUEST`, `INVALID_CURSOR`, `UNKNOWN_FILTER`, `INVALID_SORT` | Request/query cannot be interpreted safely |
| 401 | `UNAUTHENTICATED`, `SESSION_EXPIRED`, `TOKEN_REUSED` | Authentication absent/invalid/expired/reused |
| 403 | `PERMISSION_DENIED`, `MEMBERSHIP_INACTIVE` | Known household capability denied without foreign-resource disclosure |
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

- Limits are defined by endpoint/risk class, actor, household, credential/IP/device signals as approved by Issue #11; exact numbers are `TBD-VALIDATE`.
- Authentication, activation/recovery, uploads, report generation, exports, AI, and expensive search/aggregation have distinct policies.
- A rejected request returns `429 RATE_LIMITED`, safe message/correlation, and `Retry-After` when the server knows the delay.
- Rate-limit metadata never reveals another account/household or internal capacity.
- Limits are enforced before expensive/provider work and cannot be bypassed by changing household IDs or idempotency keys.
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

- Upload request is authorised for household, purpose, parent resource, type, and size before content is accepted.
- User filename is metadata only; storage key/path is server generated.
- Media type, extension, content signature, checksum, and malware/quarantine policy follow Issue #11/#13.
- Upload status is explicit; partial/quarantined/failed file is unavailable.
- Download uses an authorised endpoint or short-lived unguessable reference; access rechecks household, purpose, resource, status, and expiry.
- `Content-Disposition` uses a sanitised safe filename.
- Range/caching behavior is explicitly allowlisted; protected JSON/files default to `Cache-Control: no-store` unless a later design safely approves private caching.
- Cross-household, traversed, expired, or guessed file references return safe not-found behavior.

## 19. Caching and conditional requests

- Protected business responses default to `Cache-Control: no-store` until endpoint-specific private caching is approved.
- ETag is used for concurrency/conditional reads where documented, not shared public caching.
- `304 Not Modified` may be used only when authorisation is revalidated and representation scope/filters/household are identical.
- API/proxy caches must include authorisation and household boundaries; a shared cache of household responses is prohibited by default.

## 20. Compatibility and deprecation

- `/api/v1` is the first major contract. Paths, field meaning, numeric semantics, permission behavior, and stable error codes are compatibility surface.
- Additive optional response fields may be added within v1; clients must ignore unknown response fields.
- Request schemas reject unknown fields unless a documented extension object exists.
- Removing/renaming fields, changing meaning/type/nullability, narrowing accepted values unexpectedly, changing auth/household semantics, or reusing an error/state code requires v2 or an approved staged migration.
- Deprecation is documented with replacement, notice period, telemetry/privacy review, and when applicable `Deprecation`/`Sunset`/`Link` headers.
- Retired codes remain documented and are not reused for different meaning.
- Database identifiers/internal module names are not API compatibility guarantees unless explicitly exposed.

## 21. Representative synthetic examples

### 21.1 Create a farming investment

```http
POST /api/v1/households/00000000-0000-4000-8000-000000000101/farming-investments HTTP/1.1
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

The same shape applies whether the UUID is absent or belongs to another household.

## 22. Security and privacy requirements

- Authentication/authorisation occurs before protected parsing/query/provider work where possible.
- Every referenced ID, filter, cursor, include, aggregate, job, file, report, audit query, and AI dataset remains household scoped.
- Logs/audit/errors exclude credentials, headers, secrets, full payment data, report bytes, sensitive attachments, and unmasked AI payloads.
- Sensitive request/response bodies are not recorded by default observability middleware.
- CORS, CSRF, cookies, security headers, token storage, cryptography, exact limits, upload scanning, and retention are finalized by Issue #11 without weakening this contract.
- OpenAPI/docs exposure in production is an explicit security/deployment decision; documentation never includes real credentials or household examples.

## 23. Validation matrix

| Area | Required future evidence |
| --- | --- |
| Resource consistency | Naming/method/subresource review across every module |
| Authentication | Missing/invalid/expired/reused/revoked/deactivated lifecycle tests |
| Authorisation | Two-household URL/body/filter/cursor/include/file/job/report/AI identifier substitution |
| Errors | Every code/status/envelope validated; no stack/SQL/existence/sensitive leak |
| Decimals | String, range, scale, currency, rate, ratio, quantity, zero-denominator cases |
| Pagination | Stable order, no duplicate/skip under updates, invalid/tampered/incompatible cursor |
| Idempotency | Same/different fingerprint, concurrent, in-progress, timeout-after-commit, expired key, lost permission |
| Concurrency | Missing/stale/matching ETag and conflicting lifecycle transitions |
| Rate limit | Threshold, Retry-After, recovery, distributed signal, no account enumeration |
| Async/provider | Queued/success/failure/cancel/timeout/retry; core records unchanged |
| Files | Type/size/signature/name/traversal/quarantine/expiry/cross-household/download tests |
| Compatibility | Contract diff detects breaking field/code/auth/permission changes |

## 24. Deferred decisions and Issue #9 acceptance

Deferred to later issues: exact request/response schemas per feature, access/refresh token format/lifetime/transport, CORS/CSRF/cookie details, numeric rate-limit thresholds, cursor signing mechanism, upload malware tooling, report/AI payload schemas, polling intervals, OpenAPI generation/hosting, and code layout.

Issue #9 is satisfied when review confirms a consistent `/api/v1` resource/method model, stable safe error envelope/codes, explicit household authorisation, decimal formats, cursor/filter/sort rules, idempotency/concurrency/rate-limit/correlation behavior, synthetic-only examples, compatibility rules, and no routes, schemas, OpenAPI implementation, or application code.
