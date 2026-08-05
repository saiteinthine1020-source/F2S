# F2S Test Strategy and Quality Gates

## 1. Purpose and status

This document defines the future F2S test levels, suites, fixtures, environments, traceability, execution evidence, failure reporting, and quality gates. It is the Phase 0 test baseline for implementation issues.

It follows the [Product Requirements](02_Product_Requirements.md), [Functional Requirements](03_Functional_Requirements.md), [Non-Functional Requirements](04_Non_Functional_Requirements.md), [Use Cases](06_Use_Cases.md), [System Architecture](07_System_Architecture.md), [Database Design](08_Database_Design.md), [REST API Design](09_API_Design.md), [UI/UX Design](10_UI_UX_Design.md), [Security Design](15_Security_Design.md), accepted ADRs, and the [GitHub Milestones](project_management/GitHub_Milestones.md).

This document creates no product test, application code, test configuration, CI workflow, fixture database, coverage threshold, or claim that an unimplemented feature passed. Tool choices below are planned contracts and become executable only in their implementation issues.

## 2. Testing principles

1. Tests trace to a requirement, risk, contract, defect, or milestone exit condition.
2. Financial correctness, household isolation, privacy, and recovery receive stronger evidence than ordinary presentation details.
3. A result is reported as passed only when the named command and assertions execute successfully against the stated commit/environment.
4. Skipped, expected-failure, blocked, flaky, not-run, and not-applicable checks are not passed checks.
5. Tests use synthetic deterministic data; real family/production data is prohibited outside a separately approved protected-data procedure.
6. Repository, migration, transaction, concurrency, and numeric database tests use the approved PostgreSQL major version, not SQLite substitution.
7. External providers are stubbed for deterministic pull-request tests; protected live contract checks use synthetic payloads only.
8. Tests assert behavior and invariants, not framework implementation details.
9. A retry may diagnose instability but cannot erase the original failure.
10. Automated tests complement, not replace, security review, accessibility/linguistic review, report visual QA, restore drills, and operator verification.
11. Tests remain isolated, parallel-safe, order-independent, repeatable, and bounded in time/resources.
12. Quality gates grow with implemented risk; documentation-only phases do not fabricate product coverage.

## 3. Result vocabulary and honest reporting

| Result | Meaning | May be reported as passed? |
| --- | --- | --- |
| `PASSED` | Named command exited successfully and all required assertions executed | Yes |
| `FAILED` | At least one assertion or required quality threshold failed | No |
| `ERROR` | Environment, collection, setup, timeout, crash, or tooling prevented valid completion | No |
| `SKIPPED` | Test was discovered but intentionally not executed | No |
| `XFAIL` | Known expected failure executed or was selected under an approved marker | No |
| `XPASS` | Expected failure unexpectedly passed; requires review/removal of stale expectation | No until policy resolves it |
| `NOT RUN` | Command/test was not executed | No |
| `NOT APPLICABLE` | Reviewed scope has no relevant behavior; rationale recorded | Not a pass; acceptable scope disposition |
| `BLOCKED` | A verified dependency or environment prevents execution | No |
| `FLAKY/QUARANTINED` | Result is nondeterministic or removed from the required gate under an owned exception | No |

An empty test selection, collection failure, missing dependency, unavailable database/browser, expired credential, or command typo is `ERROR`, `BLOCKED`, or `NOT RUN`; it is never converted to `PASSED`.

Manual validation is passed only when the named reviewer executes the documented procedure and records date, commit/build, environment/device, expected outcome, actual outcome, and evidence location without protected data.

## 4. Traceability model

### 4.1 Stable identifiers

Future suites use stable IDs:

- suite: `TS-<AREA>` such as `TS-AUTHZ`, `TS-CALC`, or `TS-OFFLINE`;
- test/evidence item: `TST-<AREA>-NNN`; and
- defect regression: links the defect/issue plus affected requirement and test ID.

Test names remain readable behavior statements. Requirement IDs belong in test metadata/docstrings/markers or a generated manifest rather than relying only on filenames.

### 4.2 Required mapping

Every behavior-changing pull request records:

| Trace field | Required content |
| --- | --- |
| Issue/milestone | Active issue and delivery phase |
| Requirement/design | Applicable `PR-*`, `FR-*`, `NFR-*`, ADR, API/design section, or explicit rationale |
| Behavior/risk | Normal, negative, boundary, failure, recovery, security, privacy, accessibility impact |
| Test level/suite | Unit, service, repository, API, component, browser, system, manual, etc. |
| Test IDs/locations | Added/updated/existing evidence; no vague `covered by tests` statement |
| Commands | Exact commands that were actually executed |
| Result | Honest vocabulary from Section 3 plus counts and material warnings |
| Non-applicable/not-run | Explicit reason, risk disposition, and follow-up issue when required |

Traceability review rejects a requirement whose acceptance outcome has no evidence or justified future dependency.

## 5. Test levels

| Level | Purpose | Planned tools/environment | Typical ownership |
| --- | --- | --- | --- |
| Documentation/static | Links, Markdown, schemas, formatting, lint, types, prohibited patterns, architecture imports | Repository scripts; Python/TypeScript linters/type checkers selected by scaffold issues | All changes |
| Domain unit | Pure value objects, rules, formulas, state transitions, masking functions | `pytest`; `Vitest` for pure frontend utilities | Module owner |
| Application/service | Use-case coordination, capability decisions, transaction intent, audit/idempotency behavior | `pytest` with ports/fakes and focused integration | Backend owner |
| Repository/database | PostgreSQL mappings, constraints, indexes, transactions, locking, query scope | `pytest` against isolated real PostgreSQL | Backend/data owner |
| Migration | Clean upgrade and every supported prior-state upgrade, reconciliation, compatibility | Alembic plus approved PostgreSQL and representative snapshots | Data/release owner |
| API contract/integration | HTTP methods, schemas, status/error envelope, auth, isolation, pagination, concurrency | `pytest` with running ASGI/application and PostgreSQL | Backend/API owner |
| Frontend component | Accessible states, forms, validation, translations, server-state rendering | `Vitest` and React Testing Library | Frontend owner |
| Browser critical flow | Integrated user workflows, keyboard/focus, responsive/offline behavior | Playwright against production-like built frontend/backend | Cross-stack owner |
| Report/artifact | Dataset reconciliation, PDF render, Excel structure/charts, CSV bytes/safety | Python inspectors/renderers plus supported viewer/manual checks | Reporting owner |
| Provider/AI contract | Masking, request/response schemas, failure fallback; limited live compatibility | Deterministic fake adapter; separately protected synthetic live check | AI/security owner |
| Security | Threat/control, isolation, injection, secret/dependency/image/configuration/browser tests | Layer-appropriate tests and approved scanners | Security/release owner |
| Performance/capacity | Latency percentiles, throughput, resources, query plans, artifact limits | Production-like load/browser/database tools selected later | Performance/operations owner |
| Deployment/system | Images, configuration, TLS/headers, health, rollback, monitoring, backup/restore | Disposable staging/replacement environment | Operations owner |
| Manual specialist | Shan language, accessibility, visual reports, exploratory/security/restore review | Documented checklist and evidence | Qualified reviewer |

Unit tests cannot substitute for repository/API/browser evidence when the risk crosses that boundary. End-to-end tests cover critical integration paths but do not replace focused unit/service failure matrices.

## 6. Planned repository placement and markers

The future monorepo keeps tests near their owning application while making cross-stack suites discoverable:

| Area | Intended placement |
| --- | --- |
| Backend unit/service/repository/API/migration | `backend/tests/` grouped by level and module |
| Frontend unit/component/accessibility | `frontend/src/` colocated or `frontend/tests/` by approved convention |
| Browser/critical flow | `frontend/tests/e2e/` or one approved root integration location |
| Architecture/contract/shared golden fixtures | One documented test-support area with strict ownership |
| Infrastructure/deployment/restore checks | `infrastructure/` test/runbook locations established by their issues |

Markers/tags may distinguish `unit`, `service`, `postgres`, `migration`, `api`, `component`, `e2e`, `security`, `report`, `ai_contract`, `offline`, `performance`, `restore`, and `manual`. A marker describes requirements and environment; it must not become a permanent way to skip a required gate.

## 7. Synthetic fixture and privacy policy

### 7.1 Prohibited data

Tests, snapshots, screenshots, videos, traces, reports, database dumps, CI artifacts, documentation, and provider fixtures contain zero real household financial or personal data. Copying then `anonymising` production data is prohibited unless a separately approved protected-data procedure defines necessity, access, transformation validation, retention, and deletion.

Synthetic identities use clearly artificial values such as reserved-looking UUIDs and `example.invalid` addresses. Fixtures avoid real names, phone numbers, addresses, payment references, credentials, or plausible secrets. Security-canary strings are synthetic and labelled so scanners/tests do not confuse them with usable credentials.

### 7.2 Canonical fixture packs

| Fixture pack | Purpose |
| --- | --- |
| `EMPTY_HOUSEHOLD` | Honest no-record state; no sample KPI/chart/project |
| `MINIMAL_VALID` | Smallest valid record/relationship for one behavior |
| `TWO_HOUSEHOLDS` | Alpha/Beta users, roles, inactive membership, foreign identifiers for isolation |
| `FINANCIAL_BOUNDARIES` | Exact decimal, scale, sign, currency, unit, rate, rounding, zero cases |
| `LIFECYCLE_HISTORY` | Active/cancelled/archived/reversed/deactivated history preservation |
| `REFERENCE_HOUSEHOLD` | Generated capacity dataset: 10 members, 10 years, 100,000 finance events, 5,000 investments, 50,000 related records |
| `REPORT_GOLDEN` | Versioned verified dataset for API/dashboard/PDF/Excel/CSV reconciliation |
| `MASKING_CANARIES` | One synthetic prohibited marker per AI/log/export field and free-text edge case |
| `OFFLINE_STATE_MACHINE` | Draft/queued/syncing/synced/failed/conflicted/expired/lost-authority entries |
| `MIGRATION_PRIOR_STATES` | Supported schema versions with valid, boundary, and historical records |

Fixture packs are versioned with formula, currency/unit registry, dataset, schema, and locale assumptions. A golden fixture update requires review of the intentional behavior change; blindly regenerating expected output to make a failure pass is prohibited.

### 7.3 Determinism and isolation

- Clock, timezone, random seed, UUID generator, provider response, and network faults are controlled where the behavior depends on them.
- Time tests cover UTC, household timezones, date boundaries, leap days, month/year transitions, and daylight-saving changes where an enabled timezone observes them.
- Tests do not depend on wall-clock sleeps, execution order, a developer's locale, shared account state, or public network availability.
- Parallel tests use isolated database/schema/storage/browser contexts and prove no cross-worker leakage.
- Setup and cleanup are idempotent; failure cleanup does not delete outside its explicit synthetic namespace.
- Expected values are independently derived from documented rules/decision tables, not copied from the implementation under test.

## 8. Environment matrix

| Environment | Purpose | Data/dependency policy |
| --- | --- | --- |
| Developer local | Focused fast feedback and debugging | Locked dependencies; disposable synthetic database/files |
| Pull-request CI | Required deterministic gates | Clean checkout; ephemeral services; no production secrets/data; providers faked |
| Scheduled CI | Wider browsers, longer security/property/performance smoke | Synthetic fixtures; controlled network; retained safe evidence |
| Production-like staging | Capacity, deployment, TLS/config, report, rollback/restore rehearsal | Matches approved versions/resources; synthetic reference dataset only |
| Production smoke | Minimal non-destructive availability/security health | No mutation or data extraction beyond approved synthetic/health account policy |
| Isolated restore | Backup restoration and integrity/isolation verification | Network/provider side effects disabled; restricted access; destroyed after evidence |

PostgreSQL repository, migration, transaction, locking, and numeric tests use the same approved major version as production. SQLite is prohibited as a substitute for those behaviors.

### 8.1 Browser/device coverage

- Chromium executes critical flows on pull requests once stable.
- Firefox and WebKit critical-flow compatibility execute on scheduled and phase-release gates; a critical browser-specific change may promote them to the pull-request gate.
- Responsive automation covers at least 320 CSS-pixel reflow, a representative mobile viewport, and a wider layout.
- Manual/reference-device checks cover the approved lowest supported Android class when identified; until then the device is `TBD-VALIDATE` and cannot be claimed supported.
- Accessibility checks include 200 percent text zoom and at least 30 percent pseudo-localised expansion.

### 8.2 Network profiles

| Profile | Definition |
| --- | --- |
| Normal mobile | 10 Mbps down, 2 Mbps up, 100 ms round-trip latency |
| Constrained mobile | 1 Mbps down, 256 Kbps up, 300 ms round-trip latency plus repeatable intermittent loss |
| Offline transitions | Disconnect before request, during transfer, after commit/before response, during retry, and during provider/artifact work |

Every performance/offline report records shaping tool/version and the exact transition point; a generic `slow network` claim is insufficient.

## 9. Financial precision and calculation strategy

### 9.1 Mandatory numeric matrix

| Area | Input/example | Required outcome |
| --- | --- | --- |
| Float prohibition | Binary float enters a verified money/rate/quantity path | Static/runtime/schema rejection |
| Decimal exactness | Exact decimal `0.1 + 0.2` | Exactly `0.3` |
| Money scale | Ordinary `10.235 USD` | Rejected; not silently rounded |
| Currency mismatch | `1000 MMK + 5.00 USD` without conversion | Rejected |
| Half-even | Quantise `2.345` and `2.355` to 2 places | `2.34` and `2.36` |
| Allocation | Split `10.00 USD` among 3 stable IDs | Deterministic `3.34`, `3.33`, `3.33`; total exactly `10.00` |
| Percentage | Enter/display 7.5 percent | Ratio `0.075`; display context `7.5%` |
| Exchange direction | `100.00 USD` at `154.275 JPY/USD` | `15428 JPY` after one final approved quantisation |
| Inconsistent FX triplet | Source/rate conflicts with submitted destination | Atomic rejection |
| Zero denominator | ROI with zero actual investment | Typed `ZERO_DENOMINATOR` unavailable result, no numeric value |
| Negative ordinary event | Ordinary expense `-1.00 USD` | Rejected; correction uses explicit reversal |
| Precision/range boundary | Largest valid value and one digit/scale beyond | Exact acceptance then safe rejection |
| Unit mismatch/conversion | Incompatible or missing unit/conversion rule | Rejected or typed unavailable result |
| Missing/partial input | Each formula dependency absent/pending | Documented quality/availability state; no misleading zero |
| Cross-output | Identical filters through every consumer | Exact reconciliation at documented scale and availability state |

### 9.2 Formula decision tables and properties

- Every approved formula has normal, boundary, missing-input, invalid/negative-input, and zero-denominator cases.
- Golden formula cases are owned by the Calculation module and consumed through its public contract; routes, frontend, reports, forecasts, and AI do not reproduce formulas in tests.
- Property/invariant tests cover allocation conservation, stable residual assignment, order independence where promised, reversal conservation, balance reconciliation, no double counting, monotonic constraints where valid, and round-trip format boundaries.
- Property-generated values stay inside explicit decimal/range/unit domains and record the reproducible seed on failure.
- Snapshots are never the sole assertion for financial truth; exact values, currencies, units, rule versions, quality, and unavailable reasons are asserted structurally.

### 9.3 Reconciliation suites

Canonical-event fixtures span finance, farming costs, harvests, sales, remittances, debts, receivables, payments, allocations, reversals, partial payments, overpayment policy, cancellations, and archives. They prove one real-world event contributes exactly once to cash flow and relevant balances with zero unexplained smallest-unit difference.

## 10. Household authorisation and isolation strategy

Every protected resource family receives positive and negative tests with at least two households, users with different roles, a multi-household user, and inactive/deactivated membership.

Identifier substitution covers:

- list, detail, create, patch, lifecycle transition, reversal, archive, restore, and delete where permitted;
- foreign IDs in paths, bodies, nested relationships, parents, filters, search, sorts, cursors, includes, and batch inputs;
- counts, totals, calculations, comparisons, dashboard aggregates, and data-quality results;
- uploads, file status/preview/download, reports/exports, jobs, notifications, audit/correlation queries, and AI preparation/results;
- idempotency keys, request fingerprints, ETags/versions, cached responses, service-worker data, and offline queues; and
- restored backups, migrations, role changes, household switching, logout, and deactivation.

Negative assertions verify safe status/envelope, no content/existence/count/timing distinction, no mutation, no audit leak, no file/provider work, no cache contamination, and no background side effect. `NFR-SEC-001` requires 100 percent of implemented protected endpoint/service/repository/aggregate/report/download/AI-preparation cases to reject cross-household access.

## 11. Backend domain, service, and architecture suites

### 11.1 Domain/unit

- value objects and enums reject invalid construction;
- lifecycle state machines cover every allowed and prohibited transition;
- date/order, currency/unit, allocation, correction, and quality invariants are parameterised;
- pure formula/masking rules have no database, network, framework, locale, or wall-clock dependency; and
- unavailable states and reasons are first-class outcomes.

### 11.2 Application/service

- current actor/household/capability is passed explicitly;
- required repository/module ports are called with scoped values;
- validation/authorisation occurs before mutation or external calls;
- transaction-required business records, audit intent, and idempotency outcome commit together or not at all;
- injected failures at each step prove atomicity and safe retry; and
- optional email/report/AI failure cannot roll back or corrupt an independent committed core fact.

### 11.3 Architecture checks

Automated dependency rules and review reject:

- internal cross-module imports and dependency cycles;
- domain imports of FastAPI, SQLAlchemy, rendering, frontend, or provider SDKs;
- direct writes or unapproved reads of another module's tables;
- formulas duplicated outside Calculation;
- reports/AI querying source tables rather than verified datasets; and
- a shared kernel accumulating workflows, ORM/HTTP schemas, role policy, report layouts, or provider prompts.

An architecture-test exception requires a new/superseding ADR; disabling the check in one pull request is insufficient.

## 12. PostgreSQL repository, migration, and concurrency suites

- Constraints reject orphan, ownership mismatch, duplicate canonical links, invalid code/range/scale/date, self-reversal, and allocation inconsistency.
- Runtime role tests prove denied schema/role/database/migration/other-module privileges.
- Repository queries always include household scope and stable pagination/order.
- Query-plan fixtures validate named high-volume lists/aggregates against the reference dataset without asserting brittle exact planner internals.
- Concurrency tests use independent database connections/transactions and explicit synchronization barriers, not timing sleeps.
- Duplicate create, concurrent payment/allocation, stale version, deadlock retry, timeout-after-commit, refresh rotation, and idempotency races result in one intended mutation or explicit conflict.
- Transaction isolation/locking behavior is documented per use case and asserted rather than relying on database defaults.

Migration gates include clean upgrade, every supported prior version, repeat execution behavior, model/schema drift inspection, constraint/index/ownership checks, preserved history/counts/totals, and application compatibility. Destructive/non-reversible changes require protected backup plus tested rollback or forward-fix/restore plan; a successful migration command alone is not sufficient.

## 13. API and session contract suites

API tests cover:

- canonical `/api/v1` paths, methods, media types, success envelopes, `Location`, and status codes;
- strict request fields, decimal strings, dates, UUIDs, size/range/cross-field validation, and stable safe errors;
- cursor pagination under inserts/updates, stable tie-breakers, tampered/expired/incompatible cursors, allowlisted filters/sorts;
- ETag/`If-Match` missing, matching, stale, and concurrent mutation behavior;
- idempotency same/different fingerprint, concurrent/in-progress, timeout-after-commit, expired key, lost permission, and replay response;
- correlation creation/validation/propagation across errors, audit, jobs, reports, and providers;
- rate-limit threshold, safe `429`, `Retry-After`, recovery, distributed scope, and no enumeration; and
- async queued/success/failure/cancel/timeout/retry with protected status/artifact access.

Session tests cover activation, valid/invalid password, uniform enumeration response, access expiry, refresh idle/absolute expiry, rotation, reuse-family revocation, zero grace/lost response, single-flight refresh, logout, password change, account/membership deactivation, step-up freshness, CSRF, CORS, cookie attributes, access-token memory policy, and revocation on every protected request.

## 14. Security, privacy, files, and observability suites

Threat/control tests derive from `docs/15_Security_Design.md` and include:

- SQL/XSS/mass-assignment/header/path/CSV-formula/template/command/SSRF payloads where applicable;
- CSP/CORS/CSRF/origin/proxy-trust/cache/security-header configuration;
- secret scan, dependency/container scan, SBOM/provenance, unsafe production configuration, and public-port checks;
- upload extension/type/signature/size/name/traversal/decompression/malware/quarantine/scan-failure/expiry/isolation;
- download clean-status, current authority, safe filename, `nosniff`, no-store, range/preview, expiry, and deleted/partial artifacts;
- structured logs/audit required fields, UTC time, correlation, append behavior, authorised queries, and retention; and
- synthetic prohibited-value canaries proving absence of passwords, tokens, cookies, authorisation/CSRF headers, API keys, private keys, full bank/payment details, raw files/reports, and unmasked AI payloads.

Scanner success does not replace targeted tests or review. A Critical/High finding cannot be hidden by excluding a path; a time-bound risk acceptance requires owner, mitigation, expiry, and release approval.

## 15. Frontend component, accessibility, and internationalisation suites

### 15.1 Component behavior

Vitest and React Testing Library verify behavior through accessible roles/names and user interactions rather than component internals. Each applicable data surface covers initial loading, refreshing, true empty, filtered empty, insufficient data, permission unavailable, offline, stale/partial, validation failure, request failure, success, conflict, and session expiry.

Forms cover persistent labels, instructions, required/optional state, locale input, exact money/unit context, summary plus inline errors, focus movement, preserved input, dirty-exit warning, double activation, delayed response, and safe retry.

### 15.2 Accessibility

- Automated accessibility scans have zero known WCAG 2.2 A/AA violations in supported critical flows.
- Keyboard tests cover task completion, logical/unobscured focus, modal return, route changes, menus, tables, charts, files, and no traps.
- Screen-reader/manual checks cover landmarks, headings, names/roles/states, live announcements, errors, progress, tables, charts, and dialogs.
- Visual/manual checks cover contrast, non-colour meaning, reduced motion, 200 percent text zoom, 320 CSS-pixel reflow, target sizes, and grayscale.
- Automated scans never replace screen-reader, keyboard, zoom, touch, and cognitive review.

### 15.3 Internationalisation

- Static/runtime checks find no planned hardcoded user-facing strings or raw translation keys.
- Shan critical flows require linguistic sign-off; unreviewed machine translation is not acceptance evidence.
- Pseudo-localisation expands text at least 30 percent and covers plural/select variables, long words, mixed numerals, missing glyphs, dates, currencies, units, and error/assistive text.
- Layout/screenshots prove no clipping, overlap, hidden action, fixed-height loss, or contradictory reading/focus order.

## 16. Browser critical-flow suite

Critical Playwright flows are derived from use cases and include normal, alternate, failure, recovery, audit, isolation, responsive, and accessibility paths. At minimum as phases arrive:

- activation/login/refresh/logout/password change and household selection;
- role-appropriate household/member action and denied direct request;
- finance event create/view/filter/reversal with exact displayed context;
- blank Farming Investments state, explicit creation, edit, cancel/archive/restore;
- cost/harvest/sale/payment/allocation/profitability workflows;
- remittance/debt/receivable payment and balance reconciliation;
- dashboard filtering and honest empty/data-quality/chart states;
- report preview/request/status/download/failure/expiry;
- AI purpose/request/safe response/fallback with masked verified data; and
- install/offline draft/queue/reconnect/retry/conflict/logout/household-switch behavior.

Tests use semantic locators, not fragile CSS structure. Screenshots/traces are retained on failure under short safe retention and are scanned/constructed to contain synthetic data only.

## 17. Reports and export verification

One versioned `REPORT_GOLDEN` dataset and identical filter contract drive API, dashboard, PDF, Excel, CSV, forecast, and AI-preparation comparisons.

| Artifact | Automated evidence | Manual/supported-viewer evidence |
| --- | --- | --- |
| PDF | Page count/size, text/metadata, fonts, links, timestamps, values, rendered page images, no clipping/overlap heuristic | A4 print, grayscale, zoom, accessibility/readability review |
| Excel | Workbook opens programmatically, required sheets/cells/types/formulas/named ranges/charts/references/styles, formula-injection protection | Opens without repair warning in supported spreadsheet software; charts/print usability |
| CSV | Exact UTF-8/BOM policy, columns/order/rows/escaping/newlines, raw-data semantics, spreadsheet-injection protection | Representative import/open behavior |
| Preview/print | Same verified dataset/version/filters, accessible states, print layout | Browser print/device review |

Golden visual differences require human review and documented intentional update. Pixel snapshots are not the sole correctness check and use controlled fonts/render versions to reduce noise.

Generation tests cover standard and maximum approved datasets, authorisation loss, timeout, renderer crash, partial output, duplicate request, concurrency/backpressure, filename/path, retention, download expiry, deletion, and audit. A failed job never exposes a partial artifact.

## 18. AI masking and provider suites

Deterministic pull-request tests use a fake provider and cover:

- authentication, household, role, purpose, dataset quality/version, and abuse limit before provider call;
- 100 percent removal/replacement of prohibited-field canaries across names, contacts, addresses, bank/payment details, references, authentication data, secrets, unnecessary descriptions, and adversarial free text;
- outbound allowlisted schema, currency/unit/period/quality/assumption context, and no request for authoritative calculation;
- prompt-injection content treated as data;
- valid/invalid JSON/schema, unknown fields, fabricated/mismatched numeric references, unsafe language, guarantee, missing uncertainty, wrong language, oversize, timeout, rate limit, and outage;
- bounded retry/idempotency/cancellation and safe fallback;
- no source mutation or core transaction rollback; and
- safe audit/log metadata with no raw unmasked prompt/provider payload.

Live provider compatibility checks are never required for ordinary pull requests. When approved, they run manually/scheduled in a restricted environment with synthetic masked payloads, bounded cost/time, no production data, and an explicit `LIVE CONTRACT` result distinct from deterministic tests.

## 19. PWA, offline, retry, and conflict suites

State-machine and browser tests cover application-shell install/cache/reopen, connection detection, local draft, queued, synchronising, synchronised, failed, conflicted, expired, capacity, and lost-authority states.

Fault injection occurs:

1. before request creation;
2. during request transfer;
3. after server commit but before response;
4. during idempotent retry;
5. during refresh/auth expiry;
6. during household/membership change; and
7. during report/provider/file work.

Every write produces exactly one committed event, one retained valid local item, or an explicit conflict--never silent loss, duplicate creation, or overwrite. Retry stops on authentication, validation, permanent, and conflict errors and obeys bounded backoff for retryable failures.

Storage inspection proves no access/refresh/session/CSRF secret, Restricted field, attachment, report, or unmasked AI source enters local/session storage, IndexedDB, Cache API, service-worker cache, queued bodies, traces, or URLs. Draft age, queue count/bytes, recent-cache age/bytes, logout, explicit clear, household switch, and deactivation behavior match the security design.

## 20. Performance, reliability, and capacity

Performance results are valid only when they record commit/build, environment resources/limits, PostgreSQL/version/configuration, fixture/version/distribution, concurrency/workload mix, warm-up, cache state, duration/sample count, network profile, tool/version, percentiles, error rate, and CPU/memory/disk/database metrics.

Initial targets from the non-functional requirements:

| Workload | Target/profile |
| --- | --- |
| Authenticated read / ordinary write | 800 ms p95 / 1,200 ms p95 at reference load |
| Login / token refresh | 1,500 ms p95 on production-like server |
| Filtered dashboard | Primary content within 3 seconds p95 under normal mobile profile |
| Cached-return primary mobile page | Usable core content within 4 seconds p75 under constrained profile |
| Local interaction feedback | Begins within 100 ms on supported reference device |
| Standard PDF/CSV / Excel | 30 seconds p95 / 60 seconds p95 for reference dataset |
| Interactive load | 10 concurrent authenticated sessions across isolated households |

Performance tests are scheduled/release gates on production-like infrastructure, not mocked unit timing. Regression budgets are established after a measured baseline; one fast local run cannot prove percentile compliance. Operations longer than 2 seconds also receive UI progress and duplicate-prevention tests.

Reliability/fault tests cover database/provider/email/renderer/storage timeout, bounded retry, process restart, disk/capacity threshold, network partition, health degradation, and post-failure reconciliation. Optional dependency failure cannot corrupt committed core data.

## 21. Backup, restore, and deployment verification

- A complete restore is rehearsed before first production release, at least quarterly, and after material format/topology/key changes.
- The timed restore uses replacement/isolated infrastructure and measures the approved 24-hour RPO and 4-hour RTO baselines.
- Verification reconciles schema/migration version, constraints, row counts, files, memberships/sessions, audit references, representative financial totals, calculations, and the full household-isolation suite with zero unexplained differences.
- Email/provider/background side effects are disabled in restore environments.
- Deployment tests cover clean build, locked dependencies, image health, non-root/privilege, configuration fail-closed, secrets absent, exposed ports, TLS/headers, database access, migration, health check, failed-health rollback/restore, monitoring/alert delivery, backup age, certificate and disk thresholds.

A backup command exit code without a successful verified restore is not recovery evidence.

## 22. CI quality-gate model

Issue #19 will implement stable GitHub Actions jobs only after their commands are reproducible. Planned check families are:

| Gate | Pull-request expectation when applicable |
| --- | --- |
| Documentation | Markdown/link/index/reference checks; no broken authoritative links |
| Repository hygiene | Formatting, generated-file drift, prohibited file/secret/credential patterns |
| Backend static | Formatting/lint, type checking, architecture/import boundaries, numeric/static prohibitions |
| Backend tests | Unit/service plus PostgreSQL repository/API/migration suites selected by risk |
| Frontend static | Formatting/lint, TypeScript, translation-key/user-string checks, production build |
| Frontend tests | Vitest/React Testing Library component/accessibility suites |
| Critical browser | Playwright critical flows in required browser/profile |
| Security | Secret, dependency, image/configuration and targeted threat/control checks |
| Artifact/report | Dataset/PDF/Excel/CSV checks for affected changes |
| Contract | API/schema/provider/compatibility drift checks |

Path-aware jobs may avoid irrelevant expensive execution, but the required check name must report a truthful successful applicability decision rather than disappear. A documentation-only change runs documentation/repository checks and reports product suites `NOT APPLICABLE/NOT RUN`, not passed.

Main/release adds all applicable required suites, clean build/migration, wider browser matrix, security scans, and deployment artifact verification. Scheduled jobs handle longer property/security, dependency freshness, capacity smoke, provider compatibility, and backup/restore cadence.

## 23. Gate policy, coverage, and flaky tests

### 23.1 Merge blockers

A pull request cannot merge when:

- an applicable required check is failed, errored, blocked, missing, skipped, flaky/quarantined without approved exception, or stale for another commit;
- changed behavior lacks requirement/risk and test traceability;
- a Critical/High security issue lacks approved time-bound risk acceptance;
- a required migration/fixture/golden/design update is absent;
- a test was disabled, assertion weakened, expected output regenerated, or coverage excluded without reviewed rationale; or
- results are claimed passed without exact successful execution evidence.

### 23.2 Coverage

No arbitrary global line-coverage percentage is set before representative Phase 1 code exists. The scaffold/CI issue measures baselines and proposes backend/frontend changed-code thresholds without replacing risk evidence.

Regardless of global percentage:

- documented financial formula decision cases require 100 percent coverage;
- implemented protected surfaces require complete two-household negative coverage;
- prohibited AI masking fields require 100 percent canary removal/replacement coverage;
- supported critical flows require zero known WCAG 2.2 A/AA failures at release; and
- every fixed high-impact defect requires a regression test at the lowest effective level plus boundary evidence where needed.

Branch/decision coverage is monitored for critical policy/calculation code, but a number alone cannot prove correct assertions. Mutation testing may be introduced selectively after stable critical modules exist.

### 23.3 Flaky/quarantined policy

- Required gates target zero known flaky tests.
- Automatic retry may collect diagnostic evidence; the initial failure remains visible and the job does not silently turn green.
- Quarantine requires issue, owner, risk, scope, reason, expiry (normally at most 7 days for a required critical flow), and compensating evidence.
- Quarantined tests do not count as passing coverage or milestone evidence.
- Repeated failures are fixed at root cause; increasing sleeps/timeouts without evidence is not an accepted fix.

## 24. Test execution evidence

Every reported command records where applicable:

- commit SHA and dirty/clean state;
- exact command and working directory;
- tool/runtime/dependency versions;
- operating system/container/service versions;
- database/schema/fixture version and seed;
- browser/device/viewport/zoom/locale/network profile;
- start/end time and duration;
- selected/collected/passed/failed/error/skipped/xfail/xpass counts;
- warning, coverage, performance percentile, or scan summary;
- safe artifact/report link and retention; and
- explicit unexecuted/non-applicable suites.

CI evidence is attached to the exact commit. Local manual claims include captured terminal summary where safe. Logs, traces, screenshots, videos, databases, and reports follow the synthetic-data and secret rules.

## 25. Milestone test map and exit gates

| Phase | Required evidence before milestone exit |
| --- | --- |
| 0 Foundation/docs | Documentation links/traceability; accepted designs/ADRs; reproducible scaffold/CI commands when their issues land; no product-test pass claims |
| 1 Authentication/household | Password/session lifecycle, CSRF/CORS/cookies, roles, membership, audit, two-household repository/service/API/browser isolation |
| 2 Household finance | Exact input/storage, category/filter/date, canonical event/no double count, reversal, summary reconciliation, audit/isolation |
| 3 Farming foundation | True blank state, explicit create, locations/categories, lifecycle/history, expense link, idempotency/conflict, accessibility |
| 4 Harvest/sales/profitability | Complete formula decision/property matrices, allocations, harvest/sale/payment, missing/zero/partial/precision/reconciliation |
| 5 Analytics/planning | Historical/data-quality, transparent indicators, scenario inputs/assumptions/version/uncertainty, no recommendation without evidence |
| 6 Funds/obligations | Remittance allocations, debt/receivable payments, FX, partial/overpayment, canonical cash links, exact balance reconciliation |
| 7 Dashboard | Verified dataset/filter reconciliation, honest states, accessible charts/tables, responsive/performance and household isolation |
| 8 Reports/exports | Golden cross-output reconciliation, PDF/Excel/CSV/preview/print, authorisation, files/expiry/audit, performance/accessibility |
| 9 AI adviser | Purpose/auth, 100 percent prohibited canary masking, structured provider contract, uncertainty/Shan/fallback, no mutation/log leak |
| 10 PWA/offline | Install/cache shell, all sync states, fault points, idempotency/conflict, storage limits/privacy, logout/switch/deactivation |
| 11 Production | Clean deploy/migrate/health, TLS/config/secrets/ports, monitoring/alerts, capacity, rollback, protected backup and verified timed restore |

A milestone cannot use future test plans as evidence for implemented behavior. Deferred evidence has an owned dependency and prevents exit when it covers the exit condition.

## 26. Review responsibilities

| Role | Responsibility |
| --- | --- |
| Change author | Map requirements/risks, add appropriate tests, execute/report truthfully, protect fixtures/evidence |
| Reviewer | Challenge assertions/negative boundaries, confirm commands/results/scope, reject false pass or blind golden update |
| Module/data owner | Maintain contracts, canonical fixtures, calculation/reconciliation and migration evidence |
| Security reviewer | Threat/control, isolation, secret/privacy, dependency/configuration and exception review |
| Frontend/accessibility reviewer | Component/browser, keyboard/screen-reader/zoom/touch/translation evidence |
| Shan linguistic reviewer | Critical-flow translation meaning and context; does not rely on automated checks alone |
| Operations/release owner | Production-like performance, deployment, monitoring, backup/restore and release decision |

Small-team role overlap is allowed, but high-impact manual evidence records who performed and who reviewed it. Self-review alone is insufficient for a production security exception or destructive migration/recovery claim.

## 27. Strategy validation matrix

| Acceptance area | Evidence defined by this strategy |
| --- | --- |
| Requirements/milestones | Stable test IDs, PR mapping fields, Section 25 exit matrix |
| Backend/frontend levels | Sections 5, 11-16 and planned tool ownership |
| Financial precision/boundaries | Exact Section 9 matrix, properties, reconciliation, cross-output gates |
| Household isolation | Complete Section 10 two-household surfaces and no-side-effect assertions |
| Reports/AI/audit/offline/accessibility | Dedicated Sections 14-19 with failure/privacy/manual evidence |
| Fixtures/privacy | Synthetic-only packs, canaries, deterministic generation, no production copies |
| Honest reporting | Section 3 vocabulary and Section 24 command/environment/result evidence |
| CI feasibility | Tiered/path-aware Section 22 jobs, scheduled/release separation, stable required names |
| Failure/flakiness | Merge blockers, no hidden rerun, owned short quarantine |
| Environment parity | PostgreSQL/browser/network/production-like/restore profiles |

## 28. Deferred decisions and Issue #12 acceptance

Deferred to scaffold/CI and feature issues: exact lint/type/coverage tools and versions, GitHub Actions job names, backend/frontend numeric coverage thresholds, test-directory convention, parallel worker isolation mechanism, browser/device versions, performance/load tool, PDF/Excel inspection stack, scanner vendors, provider live-check schedule, evidence retention, and production-like server specification.

Issue #12 is satisfied when review confirms that:

- test levels, critical suites, fixtures, environments, ownership, and quality gates map to requirements and all milestones;
- financial precision, rounding, boundaries, zero denominators, allocations, FX, units, reconciliation, and binary-float prohibition are explicit;
- household isolation, reports/exports, AI masking/fallback, audit/log privacy, offline conflicts, accessibility, migrations, security, performance, deployment, and restore are covered;
- PostgreSQL behavior is not substituted with SQLite;
- fixtures and evidence use no real family data or usable secrets;
- unexecuted, skipped, blocked, flaky, and non-applicable checks are never reported as passed;
- CI gates are feasible and staged without claiming current product tests exist; and
- no tests for unimplemented features, product code, CI workflow, or test configuration are created.
