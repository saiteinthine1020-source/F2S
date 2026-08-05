# F2S Non-Functional Requirements

## 1. Purpose

This document defines measurable quality targets for F2S. It complements the [Functional Requirements](03_Functional_Requirements.md) and applies to every implementation issue unless a stricter approved requirement applies.

These requirements describe the intended complete product. They do not provision infrastructure, implement controls, or authorise work outside the active milestone.

## 2. Status and measurement convention

Every target has one of these statuses:

- **Required:** a release or milestone must meet the target.
- **Provisional:** the target is reasonable for the initial deployment but must be confirmed in the named validation issue or production-like environment.
- **TBD-VALIDATE:** evidence is not yet sufficient for a numeric value. The named issue must replace it with a measured target before the affected feature is released.

Terms:

- `p95` means at least 95 percent of measured samples complete within the target.
- `p75` means at least 75 percent of measured user sessions meet the target.
- `Zero known` means no unresolved finding is present in the evidence available at the release decision; it is not a guarantee that no undiscovered defect exists.
- A verification result is reported as passed only when the named check actually executes successfully.

## 3. Reference test profiles

Performance and capacity results are meaningless without a declared profile. These initial profiles are provisional and shall be finalised by the architecture, database, deployment, and test-strategy issues.

| Profile | Initial definition | Status | Rationale | Verification |
| --- | --- | --- | --- | --- |
| Reference workspace | Up to 10 active members, 10 years of history, 100,000 finance events, 5,000 farming investments, and 50,000 related cost/harvest/sale/payment records | Provisional | Exceeds the expected first-workspace dataset while exposing inefficient list and aggregate designs. | Issue #8 shall validate entity volumes; performance fixtures shall generate the approved distribution. |
| Reference interactive load | 10 concurrent authenticated sessions for one or more isolated workspaces | Provisional | Provides initial headroom above expected simultaneous use without implying internet-scale capacity. | Issue #15 and the test strategy shall define a production-like load environment and workload mix. |
| Normal mobile network | 10 Mbps down, 2 Mbps up, 100 ms round-trip latency | Provisional | Represents usable mobile connectivity without assuming broadband. | Browser/network shaping tests on the approved reference mobile devices. |
| Constrained mobile network | 1 Mbps down, 256 Kbps up, 300 ms round-trip latency, with intermittent loss | Provisional | Represents the unstable connectivity central to the product context. | Repeatable network-shaping scenarios including disconnect and recovery. |
| Reference mobile device | Lowest supported Android class, memory, browser version, and viewport | TBD-VALIDATE | The actual family device range is not yet documented. | Issue #10 shall record tested devices and Issue #17 shall define the device matrix. |
| Production-like server | Hetzner plan, CPU, memory, disk, PostgreSQL version, and container limits matching the deployment design | TBD-VALIDATE | Numeric server targets cannot be credible before topology and plan selection. | Issue #15 shall define the profile; performance evidence shall state exact resources and versions. |

## 4. Security requirements

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-SEC-001 | 100 percent of protected endpoint, service, repository, aggregate, report, download, and AI-preparation test cases shall reject cross-workspace access. | Required | Workspace isolation is the primary confidentiality boundary. | Automated positive and negative isolation suites using at least two workspaces and identifier substitution. |
| NFR-SEC-002 | Production releases shall have zero unresolved known Critical or High vulnerabilities in direct application dependencies, container images, and deployed configuration, unless a documented risk acceptance includes owner, expiry, and mitigation. | Required | Known high-impact vulnerabilities must not be silently shipped. | Dependency/container scanning plus release review of exceptions and expiry dates. |
| NFR-SEC-003 | Production traffic shall use HTTPS; deprecated protocols and ciphers shall be disabled according to the approved security design. | Required | Financial and authentication data require transport confidentiality and integrity. | Automated TLS configuration scan and production smoke test; exact minimum protocol is confirmed by Issue #11. |
| NFR-SEC-004 | Repository, images, logs, CI output, artifacts, backups, and generated reports shall contain zero passwords, tokens, private keys, API keys, or production credentials. | Required | A secret in any delivery artifact creates account and data risk. | Secret scanning, artifact inspection, log tests, and pre-release checklist. |
| NFR-SEC-005 | Password hashing shall use Argon2 with parameters that meet the approved security baseline while keeping p95 verification latency within the production capacity budget. | TBD-VALIDATE | Secure parameters depend on measured production hardware and threat design. | Issue #11 benchmarks candidate parameters on the production-like server and records memory, time, parallelism, and p95 latency. |
| NFR-SEC-006 | Access-token lifetime, refresh-token lifetime, rotation grace, idle expiry, and absolute session lifetime shall be explicitly configured and tested. | TBD-VALIDATE | Arbitrary lifetimes may harm security or field usability. | Issue #11 records values and Phase 1 tests expiry, reuse detection, revocation, logout, and deactivation. |
| NFR-SEC-007 | Authentication, export, upload, AI, and other abuse-sensitive operations shall have endpoint-specific rate limits and safe responses. | TBD-VALIDATE | Limits require realistic usage and threat evidence. | Issue #11 identifies abuse cases and owns the initial limits; load/security tests verify thresholds and recovery without leaking account existence. |
| NFR-SEC-008 | 100 percent of supported file uploads and generated downloads shall validate authorisation, type/size policy, safe name/path handling, and expiry. | Required | Uploads and exports introduce traversal, malware, disclosure, and storage risks. | Malicious filename, traversal, content-type, oversize, expired-link, and cross-workspace test matrix. |
| NFR-SEC-009 | Security-sensitive configuration shall fail closed when required secrets, trusted origins, cookie settings, or production flags are absent or unsafe. | Required | Silent insecure defaults are unacceptable in production. | Configuration-schema tests and negative deployment smoke tests. |

## 5. Privacy and data-protection requirements

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-PRIV-001 | Every persisted, logged, exported, backed-up, or externally transmitted field shall have a documented purpose, sensitivity classification, and authorised audience before production use. | Required | Data minimisation cannot be verified without an inventory. | Issue #8 data dictionary plus Issue #11 data-flow review and sampling of each output channel. |
| NFR-PRIV-002 | Logs and audit metadata shall contain zero passwords, tokens, authorisation headers, API keys, full bank/payment details, or unmasked AI payloads. | Required | Operational evidence must not become a secondary sensitive-data store. | Automated redaction tests, structured-log schema checks, and representative log review. |
| NFR-PRIV-003 | AI masking fixtures shall remove or replace 100 percent of fields classified as prohibited for Gemini. | Required | External AI processing must receive only necessary masked data. | Deterministic masking tests covering names, contacts, addresses, payment details, references, authentication data, secrets, and free-text edge cases. |
| NFR-PRIV-004 | Backups and production data stores shall be access-controlled and protected at rest according to the approved deployment and backup designs. | Required | Backups contain the same sensitive data as the live system. | Configuration review, access test, storage-encryption evidence, and restore test from protected media. |
| NFR-PRIV-005 | Retention and deletion periods for operational logs, audit records, uploads, generated exports, AI metadata, and backups shall be documented before production. | TBD-VALIDATE | Different records have legal, historical, security, and operational needs; guessing a single period is unsafe. | Issues #11, #13, #14, and #16 produce an approved retention matrix and automated expiry tests where applicable. |
| NFR-PRIV-006 | Production, support, test, analytics, and documentation environments shall use zero real workspace financial data unless a separately approved protected-data procedure exists. | Required | Unnecessary copies increase disclosure risk. | Fixture review, environment audit, repository scan, and release checklist. |

## 6. Financial correctness and data integrity

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-COR-001 | Decimal storage and calculation shall introduce zero binary floating-point values into money, rate, percentage, quantity, or verified result paths. | Required | Financial outputs must be reproducible and explainable. | Static/schema checks plus boundary tests for precision, scale, rounding, currency, and unit conversion. |
| NFR-COR-002 | Every approved financial formula shall have 100 percent coverage of its documented normal, boundary, missing-input, negative-input, and zero-denominator cases. | Required | A single misleading result can distort family decisions. | Formula decision tables mapped to parameterised unit/service tests. |
| NFR-COR-003 | Canonical-event reconciliation shall produce zero unexplained difference at the smallest supported currency unit between source events, cash flow, project totals, debt balances, and receivable balances. | Required | Double counting and omitted payments are core product risks. | Reconciliation fixtures spanning finance, sales, remittances, debts, receivables, reversals, and shared allocations. |
| NFR-COR-004 | A failed multi-record financial operation shall leave zero partial committed business records. | Required | Partial writes can permanently corrupt balances. | Transaction rollback and injected-failure integration tests at each atomic boundary. |
| NFR-COR-005 | Migrations shall preserve 100 percent of valid historical records and constraints in tested upgrade paths; destructive transformations require an approved backup and rollback plan. | Required | Historical financial and farming data must remain trustworthy. | Migration tests against representative snapshots, row/count reconciliation, constraints, and restore/rollback rehearsal. |
| NFR-COR-006 | Required high-risk actions shall produce an audit event in 100 percent of successful and policy-defined failed cases. | Required | Traceability is necessary for corrections, security review, and family trust. | Event-to-audit coverage matrix and integration tests using correlation IDs. |

## 7. Performance and responsiveness

Targets exclude third-party outage time unless stated and must be measured against the approved reference profiles.

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-PERF-001 | Authenticated read endpoints shall complete within 800 ms p95 and ordinary write endpoints within 1,200 ms p95 at reference load, excluding report and AI jobs. | Provisional | Interactive field entry needs prompt feedback on modest infrastructure. | Production-like API load test with declared dataset, concurrency, warm-up, and percentile report. |
| NFR-PERF-002 | Login and token-refresh operations shall complete within 1,500 ms p95 on the production-like server, excluding client network delay. | Provisional | Authentication must remain usable while applying strong hashing and rotation. | Phase 1 benchmark including configured Argon2 cost and database access. |
| NFR-PERF-003 | A standard filtered dashboard shall return verified data and render its primary content within 3 seconds p95 under the normal mobile profile. | Provisional | The dashboard is a primary decision surface but aggregates many modules. | End-to-end performance test using approved standard filters and reference dataset. |
| NFR-PERF-004 | Primary mobile pages shall present usable core content within 4 seconds p75 under the constrained mobile profile after a normal cached return visit. | Provisional | Field users may have limited bandwidth and latency. | Browser performance runs on the approved reference device; record payload, cache state, and network shaping. |
| NFR-PERF-005 | Local interaction feedback for taps, typing, focus, and client validation shall begin within 100 ms in supported reference devices, excluding intentional confirmation waits. | Provisional | Immediate feedback prevents duplicate actions and confusion. | Automated timing where stable plus manual device checks on critical forms. |
| NFR-PERF-006 | Standard PDF/CSV generation shall complete within 30 seconds p95 and standard Excel generation within 60 seconds p95 for the reference dataset. | Provisional | Reports may be heavy but must not appear stalled or encourage repeats. | Issue #13 defines standard reports; production-like timed generation verifies success, failure, and retry behaviour. |
| NFR-PERF-007 | Operations exceeding 2 seconds shall expose a loading/progress state and shall prevent duplicate submission without hiding failure. | Required | Slow networks and generation tasks need clear status and idempotency. | UI/service integration tests with delayed responses, double activation, retry, and timeout. |

## 8. Availability, reliability, and graceful degradation

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-REL-001 | Production monthly availability shall be at least 99.5 percent, excluding announced maintenance, after monitoring is operational. | Provisional | A single-family VPS needs dependable access without claiming enterprise redundancy. | External uptime monitor and monthly calculation with documented exclusions; Issue #15 validates feasibility. |
| NFR-REL-002 | Production hosting shall not suspend or sleep because of inactivity. | Required | The product baseline requires continuous availability independent of recent traffic. | Deployment-plan review and an idle-period availability test. |
| NFR-REL-003 | Health monitoring shall detect loss of application or database health within 5 minutes and create an operator-visible alert. | Provisional | Timely detection limits unnoticed downtime. | Controlled service/database failure and alert-delivery drill. |
| NFR-REL-004 | Failure of Gemini, email, report rendering, or another non-core integration shall not corrupt or roll back an already committed independent core financial record. | Required | Optional/external services must not endanger source-of-truth data. | Dependency fault injection, timeout, retry, and transaction-boundary tests. |
| NFR-REL-005 | User-visible failures shall include a safe stable error code and correlation ID for 100 percent of unexpected server errors. | Required | Support needs traceability without exposing internals. | Error-contract integration tests and representative log correlation review. |
| NFR-REL-006 | Retryable operations shall be idempotent or carry duplicate-detection safeguards; replay shall create at most one intended business event. | Required | Unstable connections make retries normal. | Repeated, concurrent, timeout-after-commit, and queued-replay tests. |
| NFR-REL-007 | Incident acknowledgement and restoration objectives beyond backup RTO shall be defined before production support begins. | TBD-VALIDATE | A single maintainer cannot credibly promise an untested response schedule. | Issue #16 assigns ownership, escalation, contact paths, and drill evidence. |

## 9. Backup, recovery, and continuity

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-REC-001 | Initial production recovery point objective shall be no more than 24 hours of committed data loss. | Provisional | Daily protected backups are a realistic initial baseline but require operational validation. | Issue #16 defines schedule and measures the oldest recoverable committed event during restore tests. |
| NFR-REC-002 | Initial production recovery time objective shall be no more than 4 hours from declared recovery start to verified service restoration. | Provisional | The family needs restoration the same day without claiming high-availability failover. | Timed full restore drill on documented replacement infrastructure. |
| NFR-REC-003 | A complete restore shall be tested before first production release and at least quarterly thereafter, and after material backup-format or topology changes. | Required | An untested backup is not evidence of recoverability. | Signed restore record containing backup ID, environment, duration, integrity checks, result, and follow-up actions. |
| NFR-REC-004 | Restore verification shall reconcile critical row counts, constraints, workspace isolation, representative financial totals, and authenticated application health with zero unexplained differences. | Required | File restoration alone does not prove business-data integrity. | Automated restore-verification checklist plus sampled end-to-end calculations. |
| NFR-REC-005 | Backup retention, off-host copy count, encryption/key custody, and failed-backup alert thresholds shall be set before production. | TBD-VALIDATE | Values depend on cost, topology, and threat model. | Issue #16 records the approved matrix and tests expiry, access, failure alerting, and key recovery. |

## 10. Connectivity, PWA, and synchronisation

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-OFF-001 | The approved application shell shall reopen without network access after one successful supported online load. | Required | Installable offline access is a core resilience goal. | Browser PWA test with cache inspection followed by complete network disablement. |
| NFR-OFF-002 | Connection, local draft, queued, synchronising, synchronised, failed, and conflicted states shall be visibly distinguishable in 100 percent of supported offline-write flows. | Required | Users must know whether financial information reached the server. | State-transition UI tests and manual constrained-network checks. |
| NFR-OFF-003 | Network loss at any tested point in a write shall cause either one committed event, one retained local draft/queue item, or an explicit conflict; never silent loss or duplicate creation. | Required | Partial connectivity is expected, not exceptional. | Fault injection before request, during transfer, after commit before response, and during retry. |
| NFR-OFF-004 | Synchronisation shall use bounded retry with backoff and shall stop for authentication, validation, permanent, or conflict errors. | Required | Infinite retry wastes bandwidth and can repeat unsafe operations. | Deterministic queue tests with each error class; numeric retry policy is set by Issue #10 and validated by Issue #17. |
| NFR-OFF-005 | Maximum offline draft age, queue size, and locally cached sensitive-data scope shall be defined before offline financial writes are released. | TBD-VALIDATE | Device security and storage limits are not yet measured. | Issues #10 and #11 document values; tests verify expiry, capacity response, logout, and data clearing. |

## 11. Accessibility, mobile usability, and internationalisation

F2S targets WCAG 2.2 Level AA for supported user-facing flows, using the [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) as the reference.

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-A11Y-001 | Supported critical flows shall have zero known WCAG 2.2 Level A or AA failures at release. | Required | Workspace members must be able to use essential finance and farming workflows. | Automated accessibility scans plus manual keyboard, screen-reader, zoom, contrast, focus, and error-state review. |
| NFR-A11Y-002 | 100 percent of interactive controls shall be operable by keyboard and expose an accessible name, role, state, and visible focus. | Required | Hidden or icon-only controls otherwise exclude keyboard and assistive-technology users. | Component tests and end-to-end keyboard/screen-reader walkthroughs. |
| NFR-A11Y-003 | Content and critical actions shall remain usable at 200 percent text zoom and at a 320 CSS-pixel-wide reflow viewport without two-dimensional scrolling except for documented data tables. | Required | Phone and magnification use are core scenarios. | Responsive visual/manual checks across critical pages and translated content. |
| NFR-A11Y-004 | Primary touch targets shall be at least 44 by 44 CSS pixels; any justified exception shall still meet WCAG 2.2 target-size requirements. | Provisional | Larger targets reduce field-entry errors on phones. | Computed-size checks and manual device verification; Issue #10 documents exceptions. |
| NFR-A11Y-005 | Status, validation, charts, profit/loss, and data quality shall never rely on colour alone. | Required | Meaning must survive colour-vision differences and grayscale reports. | Design review, contrast checks, grayscale inspection, and accessible-name/text assertions. |
| NFR-I18N-001 | 100 percent of planned user-facing strings, validation messages, dates, numbers, currencies, and units shall pass through the approved internationalisation/formatting layer. | Required | Shan-first delivery and later languages cannot depend on hardcoded English. | Static checks where practical, translation-key tests, and UI audit. |
| NFR-I18N-002 | Shan shall pass linguistic review for every critical flow before that flow is released; Myanmar, English, and Japanese follow their enabled-language release plan. | Required | Technical translation correctness is not sufficient for family comprehension. | Reviewer sign-off using a flow checklist and screenshots on reference devices. |
| NFR-I18N-003 | Layouts shall tolerate at least 30 percent text expansion without clipping, overlap, hidden actions, or loss of meaning. | Provisional | Translation length varies and mobile space is constrained. | Pseudo-localisation and visual-regression checks at supported breakpoints. |

## 12. Maintainability and engineering quality

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-MNT-001 | Main-branch CI shall have zero lint, formatting, static-type, secret-scan, and configured test failures. | Required | Consistent automated gates prevent avoidable defects. | Required GitHub checks after Issue #19 establishes stable jobs. |
| NFR-MNT-002 | New or changed business behaviour shall have tests mapped to its functional requirement and issue acceptance criteria. | Required | Traceability matters more than an arbitrary global coverage percentage. | Pull-request traceability review and test-to-requirement matrix. |
| NFR-MNT-003 | Numeric coverage thresholds for backend and frontend shall be set only after representative Phase 1 code and risk areas exist. | TBD-VALIDATE | An early percentage can reward low-value tests or block a documentation-only repository. | Issue #17 measures a baseline, identifies critical modules, and records justified thresholds. |
| NFR-MNT-004 | Automated architecture checks and review shall report zero prohibited cross-module dependencies or cycles. | Required | The modular monolith depends on enforceable boundaries. | Import/dependency rule checks plus architecture review. |
| NFR-MNT-005 | Every material architecture, schema, API, security, operational, or formula change shall update its ADR/design and affected requirement references in the same issue. | Required | Documentation must describe deployed behaviour rather than lag behind it. | Pull-request checklist and link/traceability validation. |
| NFR-MNT-006 | Critical dependency updates shall be assessed within 7 calendar days and High updates within 30 calendar days of reliable notification. | Provisional | Timely review reduces known-vulnerability exposure without promising unsafe blind upgrades. | Dependency-alert timestamps, triage issue, decision, tests, and documented exception. |
| NFR-MNT-007 | A clean checkout shall be reproducible using documented commands and locked dependencies without untracked manual production steps. | Required | Repeatability supports review, recovery, and deployment. | CI clean-build job and periodic developer setup rehearsal. |

## 13. Observability, logging, and monitoring

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-OBS-001 | 100 percent of backend requests shall carry or receive a correlation ID that is returned in safe error responses and propagated to relevant logs, jobs, reports, and external-call metadata. | Required | Operators need one trace key across modules without exposing internals. | Integration tests across success, validation, denial, unexpected failure, and background work. |
| NFR-OBS-002 | Application logs shall be structured and include timestamp, level, service/module, event, correlation ID, and safe context where applicable. | Required | Searchable consistent logs are essential on a small VPS. | Log-schema tests and production sample validation. |
| NFR-OBS-003 | System clocks and persisted event timestamps shall be UTC and timezone-aware; user display shall use workspace timezone. | Required | Finance periods and audit order cannot depend on server locale. | Timestamp schema tests, timezone-boundary fixtures, and deployment configuration review. |
| NFR-OBS-004 | Production monitoring shall cover availability, HTTP error rate, latency, CPU, memory, disk, database health/connections, backup success/age, and certificate expiry. | Required | These signals cover common single-server failure modes and recovery readiness. | Monitoring inventory and controlled alert tests before production. |
| NFR-OBS-005 | Warning/critical thresholds, notification channels, escalation ownership, and alert-suppression rules shall be documented before production. | TBD-VALIDATE | Thresholds must reflect selected infrastructure and normal load. | Issues #15 and #16 establish baselines and run alert-delivery drills. |
| NFR-OBS-006 | Monitoring and application logs shall not expose prohibited sensitive fields and shall follow the approved retention matrix. | Required | Observability must not violate privacy. | Redaction tests, access review, retention/expiry tests, and sampled log inspection. |

## 14. Reporting and AI service quality

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-RPT-001 | Equivalent dashboard, PDF, Excel, and CSV filters shall produce zero unexplained value differences at the documented precision. | Required | Users must not receive conflicting financial truth by format. | Golden dataset reconciliation across all supported outputs. |
| NFR-RPT-002 | Required PDF pages shall render with zero clipped/overlapping content, unreadable symbols, broken page numbering, or grayscale-dependent meaning in the approved report fixtures. | Required | Reports may be printed or shared where colour and fonts vary. | Automated rendering to images plus visual QA at supported page sizes. |
| NFR-RPT-003 | Excel files shall open without repair warnings and contain zero broken formulas, chart references, or invalid named ranges in the approved workbook checks. | Required | A technically generated but damaged workbook is unusable. | Programmatic workbook inspection plus opening in supported spreadsheet software. |
| NFR-AI-001 | Gemini calls shall have a finite timeout and bounded retry; initial timeout and total retry budget are TBD-VALIDATE before Phase 9. | TBD-VALIDATE | External latency and cost must not block core functions indefinitely. | Issue #14 defines policy; fault tests simulate timeout, rate limit, malformed response, and outage. |
| NFR-AI-002 | Invalid, unsafe, structurally incompatible, or unavailable AI output shall produce a safe fallback in 100 percent of defined failure fixtures without altering verified data. | Required | AI is advisory and must fail without corrupting source-of-truth results. | Contract, safety, timeout, and fallback tests. |
| NFR-AI-003 | AI response latency and cost budgets shall be measured and approved before production enablement. | TBD-VALIDATE | Model, prompt size, network, and pricing may change. | Issue #14 defines a Phase 9 production-like benchmark recording p50/p95 latency, tokens/size, estimated cost, and timeout rate. |

## 15. Deployment, portability, and capacity

| ID | Target | Status | Rationale | Verification method |
| --- | --- | --- | --- | --- |
| NFR-OPS-001 | Local and production configuration shall use the same versioned service boundaries while keeping secrets and production-only settings external. | Required | Environment drift creates unreproducible defects and insecure shortcuts. | Compose/config comparison, schema validation, and clean-environment smoke tests. |
| NFR-OPS-002 | Deployment shall provide documented health verification and a tested rollback or restore path before production changes are considered complete. | Required | A successful command is not proof of a healthy release. | Staged deployment drill including failed health check and rollback/restore evidence. |
| NFR-OPS-003 | Database storage shall alert before exhaustion, with initial warning at 70 percent and critical at 85 percent of allocated capacity. | Provisional | Disk exhaustion can stop writes and damage availability; thresholds need operational headroom. | Controlled threshold test and monitoring evidence; Issue #15 validates filesystem/reserved-space assumptions. |
| NFR-OPS-004 | The approved production-like profile shall sustain the reference dataset and interactive load while meeting NFR-PERF-001 to NFR-PERF-003. | Provisional | Capacity must be demonstrated rather than inferred from provider specifications. | Combined load, database, and resource-utilisation test with bottleneck report. |
| NFR-OPS-005 | Maximum supported attachment size, report size, queue depth, database growth rate, and concurrent report jobs shall be defined before the respective capability is released. | TBD-VALIDATE | Limits depend on storage, memory, security, and user evidence. | Issues #10, #13, #15, and #17 record the relevant measured limits and verify rejection or backpressure behaviour. |

## 16. Validation ownership and unresolved targets

| Validation area | Resolving issue(s) | Required evidence |
| --- | --- | --- |
| Device, mobile layout, accessibility, translated expansion | #10 and #17 | Device matrix, WCAG checks, linguistic review, performance samples |
| Authentication parameters, session lifetime, rate limits, retention, privacy | #11 | Threat model, benchmarks, config values, negative tests |
| Test layers and coverage thresholds | #12 | Test strategy, representative baseline, critical-path gates |
| Report sizes, rendering time, file security | #13 | Standard fixtures, timed generation, visual/workbook checks |
| AI timeout, retry, latency, cost, masking | #14 | Contract/fault tests, masking fixtures, benchmark and budget |
| Production profile, availability, monitoring, capacity | #15 | Topology, resources, load results, monitoring thresholds |
| Backup, RPO, RTO, retention, incident response | #16 | Restore drill, retention matrix, alert/escalation runbook |
| CI enforcement | #19 | Stable named checks and reproducible local equivalents |

No item marked `TBD-VALIDATE` may be silently treated as satisfied. Its resolving issue must replace or explicitly retain it with measured evidence and documented rationale.

## 17. Phase 0 acceptance for this document

This quality baseline is complete for Issue #4 when:

- every requirement has a stable ID, target, status, rationale, and verification method;
- security, privacy, correctness, performance, reliability, accessibility, connectivity, recovery, logging, monitoring, maintainability, reporting, AI, deployment, and capacity are covered;
- unsupported guarantees are avoided;
- unknown numeric values are marked `TBD-VALIDATE` with an owner issue; and
- no infrastructure, schema, API, frontend, or backend implementation is added.
