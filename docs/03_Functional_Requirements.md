# F2S Functional Requirements

## 1. Purpose

This document translates the [Product Requirements](02_Product_Requirements.md) into traceable system behaviours and observable acceptance outcomes. It describes the intended complete product while preserving phased delivery. A requirement does not authorise implementation before its target milestone and prerequisite issues are active.

## 2. Requirement convention

Each requirement has a stable identifier in the form `FR-<AREA>-<NUMBER>`.

- **Priority:** Must, Should, or May, using the meanings defined in the product requirements.
- **Target:** the earliest milestone that may implement the behaviour.
- **Dependencies:** prerequisite requirement areas or decisions; detailed issue dependencies remain authoritative.
- **Acceptance outcome:** an observable result that later use cases and tests can verify.

Requirement IDs are not renumbered after publication. Retired requirements remain recorded as superseded rather than being reused.

## 3. Cross-cutting authorisation and data rules

These rules apply to every protected module.

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-AUTHZ-001 | The backend shall identify the authenticated actor, active workspace membership, and required capability before processing a protected operation. | IAM-004, IAM-005 | Must | Phase 1 | Workspace and identity design | A request without a valid actor and Active workspace membership is rejected without protected data. |
| FR-AUTHZ-002 | The backend shall verify workspace ownership for every protected list, view, create, update, archive, cancel, export, and analysis operation. | IAM-005, IAM-006 | Must | Phase 1 | ADR-012; data design | A valid user cannot access or mutate a record owned by another workspace, including by changing an identifier. |
| FR-AUTHZ-003 | List, search, aggregate, dashboard, report, and AI-preparation queries shall return only records authorised for the active workspace and role capability. | IAM-005, RPT-006, AI-001 | Must | Phase 1 | FR-AUTHZ-001 | Cross-workspace values do not appear in results, counts, totals, files, logs, or AI payloads; Contributor responses omit restricted aggregates. |
| FR-AUTHZ-004 | The system shall enforce permissions on the backend; hidden or disabled frontend controls shall not be treated as authorisation. | IAM-004, PR-007 | Must | Phase 1 | Role policy | Direct requests for an unauthorised action are denied consistently. |
| FR-AUTHZ-005 | A failed authorisation check shall not reveal whether another workspace's resource or global account exists or expose its content in an error. | SEC-001, SEC-002 | Must | Phase 1 | Error-contract design | Unauthorised identifiers receive a safe, consistent response and no sensitive detail. |
| FR-AUTHZ-006 | Important protected actions and denied attempts shall produce safe audit events according to policy. | AUD-001, AUD-002 | Must | Phase 1 | Audit design | The event records actor, workspace, action, target type, result, time, and correlation ID without prohibited secrets. |

## 4. Roles and permission baseline

The [Workspace and Identity Foundation](12_Workspace_Identity_Design.md) owns detailed
permissions. This baseline defines the minimum backend-enforced capability contract.

| Capability | Admin | Contributor | Advisor |
| --- | --- | --- | --- |
| Manage workspace settings, members, and ownership | Allowed | Denied | Denied |
| Create financial records | Allowed | Allowed as Pending | Denied |
| Approve or reject Pending records | Allowed | Denied | Denied |
| View official totals, full profitability/debt data, and reports | Allowed | Denied | Allowed when permitted |
| Comment or flag for review | Allowed | Denied | Allowed |
| Change Contributor/Advisor membership roles | Allowed | Denied | Denied |
| View safe audit information | Allowed | Own submission status only | Review evidence when permitted |

No role may bypass workspace isolation, edit calculated outputs directly, expose secrets,
or allow AI to execute a financial action. Ownership is attached to the sole active Admin
membership and is not a fourth role.

## 5. Identity and workspace management

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-IAM-001 | The system shall allow exactly one successful bootstrap that atomically creates the first account, workspace, Active Admin membership, ownership link, and audit events. | IAM-001, IAM-007 | Must | Phase 1 | ADR-013, ADR-015 | Concurrent attempts produce one winner; no partial user, ownerless workspace, or second owner remains. |
| FR-IAM-002 | A user shall activate an eligible account, authenticate, rotate a refresh session, log out, change a password, and complete concealed recovery. | IAM-002, IAM-003, IAM-010 | Must | Phase 1 | ADR-014, ADR-015 | Valid lifecycle actions succeed; invalid, expired, reused, revoked, or suspended credentials are rejected safely. |
| FR-IAM-003 | An Admin shall create, suspend, reactivate, restart activation for, and revoke Contributor or Advisor memberships without deleting historical actor references. | IAM-008, IAM-009, AUD-001 | Must | Phase 1 | FR-AUTHZ-001 | Access and affected sessions are removed while historical records retain safe attribution. |
| FR-IAM-004 | An Admin shall change an Active member between Contributor and Advisor; only the ownership-transfer workflow may create a new Admin. | IAM-004, IAM-007 | Must | Phase 1 | ADR-013 | Generic role changes cannot create zero or two Admins and denied attempts are audited. |
| FR-IAM-005 | A user belonging to multiple workspaces shall explicitly select an authorized workspace before protected data is shown. | IAM-005, IAM-008 | Must | Phase 1 | FR-AUTHZ-001 | Changing context changes the authorized dataset without mixing records or carrying privileges between workspaces. |
| FR-IAM-006 | The current owner shall transfer ownership only through reauthentication, target confirmation, expiry, notifications, and one atomic transaction. | IAM-007, IAM-010 | Must | Phase 1 | ADR-013, ADR-015 | Success leaves exactly one Active Admin owner; failure preserves the original owner. |
| FR-WS-001 | An Admin shall create and maintain workspace name, type, base currency, timezone, preferred language, optional profile fields, and module configuration. | WS-001 to WS-003 | Must | Phase 1 | ADR-016 | Valid settings persist against a stable workspace ID; unauthorized changes are denied. |
| FR-WS-002 | Consequential workspace changes shall be confirmed and audited without silently rewriting historical facts or exposing disabled-module data. | WS-001, AUD-001 | Must | Phase 1 | Audit and data designs | Historical records retain original context unless an explicit migration or correction is approved. |
| FR-HH-001 | Superseded by FR-WS-001; household settings are workspace configuration for Household-capable workspaces. | HH-001 | Must | Phase 1 | FR-WS-001 | No separate household tenant boundary is introduced. |
| FR-HH-002 | Superseded by FR-WS-002; historical currency, timezone, and unit behavior remains required. | HH-002 | Must | Phase 1 | FR-WS-002 | Existing references trace to the replacement requirement. |

## 6. Household finance

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-FIN-001 | An authorized user shall create income with category, household/farm/business classification, decimal amount, currency, date, source, payment method, optional reference, notes, and audit metadata. | FIN-001, FIN-005 | Must | Phase 2 | Phase 1; numeric-storage decision | A valid record is workspace-scoped, visible in permitted views, and contributes once to the correct totals after approval when required. |
| FR-FIN-002 | An authorized user shall create an expense with category, household/farm/business classification, decimal amount, currency, date, payee, payment method, optional reference, receipt, notes, and audit metadata. | FIN-002, FIN-005 | Must | Phase 2 | Phase 1; upload design | A valid record is workspace-scoped and contributes once after approval when required; unsafe attachments and unauthorized access are rejected. |
| FR-FIN-003 | The system shall reject negative amounts unless the operation uses a separately documented adjustment or reversal workflow. | FIN-003 | Must | Phase 2 | Adjustment decision | Ordinary create/update requests cannot store negative transaction values. |
| FR-FIN-004 | Users shall filter authorised transactions by period, category, type, payment method, farming link, and other documented fields. | FIN-001, FIN-002 | Must | Phase 2 | Query/API design | Results and permitted totals match the filter and never include another workspace. |
| FR-FIN-005 | A financial event linked from remittance, sale, debt, receivable, or farming workflows shall have one canonical representation or an explicit reference that prevents double counting. | FIN-004, REM-002, SALE-002 | Must | Phase 2 | Data model | Reconciliation tests show one real event contributes once to cash flow and relevant balances. |
| FR-FIN-006 | Corrections, reversals, archival, and attachment changes shall preserve audit history and shall not hard-delete linked financial facts through an ordinary action. | DATA-002, AUD-001 | Must | Phase 2 | Correction and archival policy | The current state and prior action history remain attributable after a permitted correction. |
| FR-FIN-007 | A Contributor-created financial record shall begin Pending and shall not affect any official dataset before Admin approval. | FIN-006, PR-008 | Must | Phase 2 | Phase 1 role policy | Pending values are absent from official balances, dashboards, reports, exports, forecasts, and AI inputs. |
| FR-FIN-008 | An Admin shall Approve or Reject a Pending submission; Rejected history remains attributable and Approved facts use correction or reversal rather than silent state rollback. | FIN-007 | Must | Phase 2 | Audit and correction policies | State transitions are authorized, atomic, and audited. |
| FR-FIN-009 | Contributor queries and representations shall omit restricted totals, reports, complete debt/profit data, and equivalent indirect aggregates. | FIN-008, IAM-004 | Must | Phase 2 | FR-AUTHZ-003 | Contract and leakage tests find no restricted value in bodies, metadata, counts, errors, files, notifications, or caches. |
| FR-FIN-010 | An Advisor shall read permitted Approved information and comment or flag for review but shall not create, edit, delete, or approve financial records. | FIN-009, IAM-004 | Must | Phase 2 | Role policy | Direct mutation attempts are denied and audited where policy requires. |

## 7. Crop catalogue and farming investments

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-FARM-001 | An authorised user shall create, edit, search, reuse, and archive crop categories independently from farming investments. | FARM-001, FARM-002 | Must | Phase 3 | Phase 1; data design | Category actions never create a project, cost, harvest, sale, total, or chart. |
| FR-FARM-002 | A new household shall see a true blank Farming Investments page with explanatory copy and a visible, accessible `Add Farming Investment` action. | FARM-005, PR-003 | Must | Phase 3 | UI/UX design | No sample project, category, KPI, chart, forecast, or recommendation appears before verified records exist. |
| FR-FARM-003 | An authorised user shall explicitly create a distinct farming investment for crop, season, year, location, and planting cycle. | FARM-003, FARM-004 | Must | Phase 3 | FR-FARM-001 | Submitting the create flow produces one project only; selecting or creating a crop category alone produces none. |
| FR-FARM-004 | The creation flow shall validate crop category, season, year, location, optional positive field size with compatible unit, planting dates, non-negative planned budget, explicit currency, initial status, and length-limited notes. | FARM-006 | Must | Phase 3 | Unit and numeric decisions | Invalid or contradictory input is rejected without a partial project and valid input is preserved after recoverable errors. |
| FR-FARM-005 | A newly created project shall show actual investment and revenue as zero with missing-record context, while profit/loss and ROI are unavailable and recommendation is insufficient data. | FARM-007 | Must | Phase 3 | Calculation-state design | The UI distinguishes real zero values from unavailable analysis and renders no fabricated graph. |
| FR-FARM-006 | An authorised user shall view and edit permitted project fields without manually editing calculated outputs. | FARM-004, CALC-002 | Must | Phase 3 | FR-AUTHZ-002 | Editable facts update with audit history; calculated fields remain read-only. |
| FR-FARM-007 | The project lifecycle shall support Planned, Active, Harvesting, Completed, Cancelled, and Archived states with validated transitions. | FARM-008 | Must | Phase 3 | Lifecycle design | Invalid transitions are denied; valid transitions record actor, time, prior state, and reason when required. |
| FR-FARM-008 | Cancelling a project shall require confirmation and reason, preserve linked records, and identify its treatment in later analytics and forecasts. | FARM-008, FARM-009 | Must | Phase 3 | FR-FARM-007 | A cancelled project remains authorised and auditable; linked costs, harvests, sales, and notes are not erased. |
| FR-FARM-009 | Archiving shall hide a permitted project from default active views while preserving history and authorised retrieval; restoration shall be an explicit audited action. | FARM-008, FARM-009 | Must | Phase 3 | FR-FARM-007 | Archived records remain available to authorised history/report queries and are not hard-deleted. |
| FR-FARM-010 | Repeated, retried, or later queued submissions shall not silently create duplicate projects or overwrite a newer version. | OFF-003, FARM-003 | Must | Phase 3/10 | Idempotency and conflict designs | Duplicate/replay tests result in one intended project or an explicit conflict. |

## 8. Costs, harvests, sales, and profitability

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-COST-001 | An authorised user shall record a direct cost against exactly one farming investment and its canonical financial event. | COST-001, FIN-004 | Must | Phase 4 | Phases 2-3 | The cost contributes once to the selected project and household finance. |
| FR-COST-002 | An authorised user shall record a shared cost and allocate it using a documented basis and values across authorised projects. | COST-002 | Must | Phase 4 | Allocation design | The allocation basis and each project share are stored and auditable. |
| FR-COST-003 | Percentage allocations shall total 100 percent before confirmation and every allocation change shall recalculate affected projects. | COST-003 | Must | Phase 4 | FR-COST-002; calculation service | Invalid totals are rejected; valid changes update all affected verified results consistently. |
| FR-HARV-001 | An authorised user shall create harvest records with quantity, compatible unit, quality, loss, usable quantity, storage, date, notes, and audit metadata. | HARV-001 | Must | Phase 4 | Phase 3; unit design | Valid harvest data belongs to one authorised project and incompatible or negative values are rejected. |
| FR-HARV-002 | The calculation service shall derive total harvest, usable harvest, loss, loss percentage, and yield per field-area unit with safe missing/zero handling. | HARV-002, CALC-001 | Must | Phase 4 | FR-HARV-001 | Verified examples and boundary tests produce documented results or an explicit unavailable state. |
| FR-SALE-001 | An authorised user shall create crop sales with quantity, compatible unit, decimal unit price, gross amount, buyer, dates, payment status, cash received, outstanding amount, selling costs, and notes. | SALE-001 | Must | Phase 4 | Phase 3; numeric/unit decisions | Valid sales are linked to one project and invalid quantities, amounts, or payment relationships are rejected. |
| FR-SALE-002 | The system shall distinguish recognised revenue, cash received, and outstanding receivable and shall link payments without double counting. | SALE-002, SALE-003, FIN-004 | Must | Phase 4 | Receivable model | An unpaid sale increases receivable but not available cash; later payment reduces the balance once. |
| FR-CALC-001 | One backend calculation service shall calculate investment, revenue, profit/loss, margin, ROI, capital recovery, break-even, unit cost, and field-area profit using documented formulas. | PR-001, CALC-001, CALC-002 | Must | Phase 4 | ADR-008; formula design | API, dashboard, report, forecast, and AI preparation consume identical verified results. |
| FR-CALC-002 | Calculations shall use decimal-safe arithmetic, explicit rounding, compatible units, safe zero-denominator behaviour, and strong unit and boundary tests. | CALC-001, CALC-003, FIN-005 | Must | Phase 4 | Numeric and unit decisions | Boundary matrices never emit invalid floating-point artefacts, division errors, or misleading zeros. |
| FR-CALC-003 | Calculation availability shall reflect project lifecycle, missing inputs, partial payments, and data quality. | FARM-007, DQ-001 | Must | Phase 4 | FR-CALC-001 | A result is labelled available, pending, incomplete, or unreliable with a reason. |

## 9. Analytics, data quality, and investment planning

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-DQ-001 | Each farming investment shall expose Complete, Mostly complete, Incomplete, or Unreliable data quality with transparent reasons. | DQ-001 | Must | Phase 5 | Phases 3-4; quality rules | The same inputs always produce the same quality state and reasons. |
| FR-DQ-002 | Forecasts, rankings, recommendations, dashboards, and reports shall display or enforce limitations caused by poor data quality. | DQ-002 | Must | Phase 5 | FR-DQ-001 | Insufficient or unreliable evidence cannot appear as a confident result. |
| FR-ANL-001 | An authorised user shall compare eligible farming investments by crop, season, year, location, field size, production, cost, price, profit, ROI, and data quality. | ANALYTICS-001 | Must | Phase 5 | Phase 4 | Filters produce workspace-scoped comparisons with periods, units, and quality context. |
| FR-ANL-002 | Crop rankings and indicators shall use documented configurable rules that consider costs, net profit, unpaid sales, shared costs, losses, consistency, and completeness. | ANALYTICS-002, ANALYTICS-003 | Must | Phase 5 | FR-DQ-001; analytics design | Each ranking exposes its inputs and reason; revenue alone cannot determine the result. |
| FR-PLAN-001 | An authorised user shall create a planning scenario with crop, field, production, price, cost change, reserve, investment limit, risk, notes, and assumptions. | PLAN-001 | Must | Phase 5 | Phase 4; forecasting design | Inputs are validated, workspace-scoped, versioned or audited, and do not create a real investment. |
| FR-PLAN-002 | The deterministic backend shall produce Conservative, Expected, and Optimistic scenarios with investment, revenue, profit/loss, ROI, break-even price, pre-harvest cash, funding gap, and assumptions. | PLAN-002, PLAN-003 | Must | Phase 5 | FR-CALC-001; ADR-011 | Repeating the same verified inputs and rules produces the same scenarios. |
| FR-PLAN-003 | Every forecast shall state its period, source data, assumptions, data quality, uncertainty, and estimate status. | PR-004, PLAN-004 | Must | Phase 5 | FR-PLAN-002 | A user can distinguish historical fact, entered assumption, and calculated estimate. |
| FR-PLAN-004 | When historical evidence is insufficient, the system shall request explicit assumptions and shall not invent missing values. | PLAN-005, PR-003 | Must | Phase 5 | FR-DQ-001 | The scenario remains blocked or clearly limited until the user supplies permitted assumptions. |
| FR-REC-001 | Recommendation status and reasons shall be produced from transparent verified inputs and shall never guarantee profit. | PR-005, REC-001, REC-002 | Must | Phase 5 | FR-PLAN-002 | The result cites reasons and limitations, leaves the final decision with the family, and cannot create projects or transactions. |

## 10. Remittances, debts, and receivables

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-REM-001 | An authorised user shall record remittance sender/receiver references, source and destination amounts/currencies, exchange rate, fee, dates, method, reference, purpose, and notes. | REM-001 | Must | Phase 6 | Phase 2; currency design | Amount relationships validate, sensitive fields follow policy, and the event is workspace-scoped. |
| FR-REM-002 | An authorised user shall allocate a remittance among household, farm, education, debt, savings, and other uses without duplicating income. | REM-002, FIN-004 | Must | Phase 6 | FR-REM-001 | Allocations reconcile to the permitted remittance amount and cash-flow totals count the event once. |
| FR-DEBT-001 | An authorised user shall create and maintain debts with lender, original amount, currency, interest terms, due dates, purpose, collateral notes, status, and audit history. | DEBT-001 | Must | Phase 6 | Phase 2; numeric design | The debt belongs to the household and its balance is calculated from canonical events. |
| FR-DEBT-002 | An authorised user shall record repayments linked to one debt and canonical financial events. | DEBT-001, FIN-004 | Must | Phase 6 | FR-DEBT-001 | A repayment reduces the correct balance once and cannot exceed documented constraints silently. |
| FR-RECV-001 | An authorised user shall create receivables or use receivables generated from crop sales, with original amount, outstanding amount, dates, status, debtor reference, and audit history. | RECV-001, SALE-002 | Must | Phase 6 | Phases 2 and 4 | Sale-linked and standalone receivables remain distinguishable and workspace-scoped. |
| FR-RECV-002 | Payments shall reduce the linked receivable and contribute once to cash received, with overpayment and reversal handled explicitly. | RECV-001, FIN-004 | Must | Phase 6 | FR-RECV-001 | Balances and cash reconcile to payment events with no silent negative outstanding amount. |

## 11. Dashboard, reports, and exports

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-DASH-001 | An authorised user shall view permitted household, business, cash-flow, farm, crop, remittance, debt, receivable, and planning KPIs available for the selected period and filters. | DASH-001 | Must | Phase 7 | Phases 2-6 | Every displayed value is workspace-scoped, period-labelled, sourced from Approved verified datasets, and omitted when the role lacks the capability. |
| FR-DASH-002 | Missing or insufficient data shall produce an explicit empty or limited state rather than fabricated totals or zero-filled charts. | DASH-002, PR-003 | Must | Phase 7 | Data-quality rules | A new or incomplete household sees explanations and permitted next actions, not fake analysis. |
| FR-DASH-003 | The MVP shall expose only the Basic dashboard level; Standard and Advanced remain named future levels. | DASH-003 | Must | Phase 7 | Product requirements | Phase 1 and MVP interfaces do not claim or expose later dashboard levels. |
| FR-DASH-004 | Dashboard and report navigation shall be capability-driven so Contributors receive no restricted totals or report entry points and direct requests remain denied. | DASH-004, IAM-004 | Must | Phase 7 | FR-AUTHZ-003 | UI and API tests prove role-consistent access without treating hidden controls as security. |
| FR-RPT-001 | An authorised user shall select report type, period, filters, and permitted format, then preview, print, or download the result. | RPT-001 | Must | Phase 8 | Reporting and authorisation designs | Unauthorised report requests fail without generating or exposing a file. |
| FR-RPT-002 | Dashboard and export values shall use the same versioned verified report datasets and calculation outputs. | RPT-002 | Must | Phase 8 | FR-CALC-001, FR-DASH-001 | Equivalent filters produce reconcilable values across screen, PDF, Excel, and CSV. |
| FR-RPT-003 | PDF reports shall be backend-generated, A4, print-friendly, grayscale-readable, and contain relevant period, KPIs, tables, graphs, assumptions, warnings, timestamp, and page numbers. | RPT-003 | Must | Phase 8 | Report design | Rendered output passes content and visual verification for required report types. |
| FR-RPT-004 | Excel reports shall contain detailed sheets, summaries, a dashboard, native charts linked to worksheet data, totals, formatting, and useful filters. | RPT-004 | Must | Phase 8 | ADR-010 | Formula and chart references remain valid when the workbook is opened in supported software. |
| FR-RPT-005 | CSV exports shall contain raw tabular data only with documented columns and Excel-compatible UTF-8 encoding where necessary. | RPT-005 | Must | Phase 8 | Report design | Exported rows match the authorised filtered dataset without presentation-only totals or charts. |
| FR-RPT-006 | Generated files shall use safe names and temporary storage, resist path traversal, be audited, and be deleted according to policy. | RPT-006 | Must | Phase 8 | Security and operations designs | A user cannot retrieve another workspace's or expired file; cleanup and audit behavior are verifiable. |

## 12. AI adviser

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-AI-001 | An authorised user shall request an AI explanation only for a permitted verified dataset and purpose. | AI-001 | Must | Phase 9 | Phases 5 and 8; ADR-006 | The backend rejects unauthorised, unsupported, or insufficient-data requests before calling Gemini. |
| FR-AI-002 | Before an external AI request, the backend shall remove or replace personal names, contact details, addresses, bank/payment details, transaction references, authentication data, secrets, and unnecessary descriptions. | AI-002 | Must | Phase 9 | Masking design | Inspection tests confirm prohibited fields never enter the outbound payload. |
| FR-AI-003 | AI input shall contain structured verified facts, estimates, periods, assumptions, uncertainty, and data-quality context; AI shall not calculate authoritative financial values. | PR-002, AI-001, AI-003, AI-004 | Must | Phase 9 | FR-CALC-001, FR-DQ-001 | Returned numbers cannot replace backend results and structural validation rejects incompatible output. |
| FR-AI-004 | AI explanations shall distinguish facts from forecasts, identify missing information, avoid guarantees and fabricated values, and support Shan as the initial language. | AI-004, AI-005 | Must | Phase 9 | I18N design | Valid output includes required limitations in Shan; unsafe or invalid output falls back without corrupting data. |
| FR-AI-005 | AI requests and results shall be audited with safe metadata without storing unmasked prompts or sensitive payloads. | AI-006, AUD-002 | Must | Phase 9 | Audit and retention designs | Audit evidence identifies actor, workspace, purpose, result, and model metadata without prohibited content. |

## 13. UX, language, PWA, and offline behaviour

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-UX-001 | Primary flows shall provide clear titles, visible actions, accessible labels, usable touch targets, validation, and loading, error, empty, success, and confirmation states. | UX-001, PR-006 | Must | Incremental | UI/UX design | Keyboard, touch, and assistive-technology checks can identify and operate required controls. |
| FR-I18N-001 | User-facing text shall use translation resources and be localization-ready for English, Shan, Myanmar, and Japanese from the first frontend implementation. | I18N-001 | Must | Phase 1 onward | I18N design | No planned user-facing component depends on hardcoded display strings; layouts tolerate every supported language. |
| FR-PWA-001 | The frontend shall be installable as a PWA and cache the approved application shell. | OFF-001 | Must | Phase 10 | ADR-009 | Supported devices can install and reopen the shell under the documented offline conditions. |
| FR-MOBILE-001 | Native packaging shall reserve `com.saiteinthine.f2s` and use the approved Capacitor decision before a store release. | MOBILE-001 | Should | Phase 10 | Packaging ADR | Package metadata remains stable across supported releases. |
| FR-MOBILE-002 | Mobile clients shall send a documented client version compatible with the supported `/api/v1` contract. | MOBILE-002 | Must | Phase 1 onward | API compatibility policy | An unsafe obsolete client is rejected with a stable upgrade response without weakening authorization. |
| FR-OFF-001 | The product should provide authorised recent-data access, offline drafts, queued entry, retry, and visible connection state where approved. | OFF-002 | Should | Phase 10 | Offline data classification | Users can distinguish local draft, queued, synchronised, failed, and conflicted states. |
| FR-OFF-002 | Offline and retried writes shall use duplicate protection and shall not silently overwrite a newer financial record. | OFF-003 | Must | Phase 10 | Idempotency and conflict designs | Replay and concurrency tests produce one intended mutation or an explicit conflict. |
| FR-OFF-003 | Conflict resolution shall show the affected record and safe choices according to a documented policy; unsupported conflicts shall require online review. | OFF-004 | Must | Phase 10 | Conflict-resolution design | No automatic resolution loses a newer authorised financial value silently. |

## 14. Audit, data preservation, and delivery

| ID | Functional requirement | Source | Priority | Target | Dependencies | Acceptance outcome |
| --- | --- | --- | --- | --- | --- | --- |
| FR-AUD-001 | Authentication, membership, role, finance, farming, export, forecast, recommendation, and AI actions shall create structured audit records where policy requires. | AUD-001 | Must | Phase 1 onward | Audit design | Required events are queryable by authorised roles and correlate with the originating operation. |
| FR-AUD-002 | Audit records shall include actor, workspace, action, resource, timestamp, correlation ID, result, and safe metadata while excluding prohibited secrets and unnecessary raw values. | AUD-002, SEC-003 | Must | Phase 1 onward | Audit design | Logging tests prove required fields exist and prohibited fields are absent. |
| FR-DATA-001 | Historical financial and farming records shall be archived, cancelled, corrected, or reversed according to policy rather than hard-deleted through ordinary operations. | DATA-002 | Must | Phase 2 onward | Lifecycle and reversal policy | Linked history remains consistent and attributable after permitted lifecycle actions. |
| FR-DEL-001 | Each implementation shall trace changed behaviour to requirement IDs, an active issue, validation, and updated documentation. | TEST-003, DEL-001, DEL-003 | Must | All phases | Repository governance | A pull request identifies its requirements, reports checks as passed only when they executed successfully, and contains no unrelated future-phase behaviour. |
| FR-DEL-002 | A schema change shall use approved relational identifiers, constraints, indexes, timezone-aware timestamps, and migrations and shall include its model, contract, validation, tests, and documentation in the same coherent issue. | DATA-001, DEL-002 | Must | Phase 1 onward | Database and test designs | Review can verify forward migration and documented compatibility without missing required artifacts. |
| FR-DEL-003 | Backend and frontend behaviour shall receive the appropriate unit, service, repository, API, authorisation, isolation, calculation, reporting, AI, audit, component, and critical-flow tests defined by the test strategy. | TEST-001, TEST-002 | Must | Phase 1 onward | Test strategy and implemented feature scope | The linked pull request identifies the applicable test levels and provides successful results or an explicit verified reason a level does not apply. |

## 15. Module and phase traceability

| Capability | Functional requirement range | Primary source requirements | Earliest milestone |
| --- | --- | --- | --- |
| Authorization and workspace isolation | FR-AUTHZ-001 to FR-AUTHZ-006 | IAM-004 to IAM-006, SEC-001 | Phase 1 |
| Identity and workspace | FR-IAM-001 to FR-WS-002 | IAM-001 to IAM-010, WS-001 to WS-003 | Phase 1 |
| Household finance | FR-FIN-001 to FR-FIN-010 | FIN-001 to FIN-009; PR-008; IAM-004; DATA-002; AUD-001 | Phase 2 |
| Crop catalogue and investments | FR-FARM-001 to FR-FARM-010 | FARM-001 to FARM-009 | Phase 3 |
| Costs, harvests, sales, calculations | FR-COST-001 to FR-CALC-003 | COST-001 to SALE-003, CALC-001 to CALC-002 | Phase 4 |
| Analytics, quality, planning | FR-DQ-001 to FR-REC-001 | ANALYTICS-001 to REC-002 | Phase 5 |
| Remittances, debts, receivables | FR-REM-001 to FR-RECV-002 | REM-001 to RECV-001 | Phase 6 |
| Dashboard | FR-DASH-001 to FR-DASH-002 | DASH-001 to DASH-002 | Phase 7 |
| Reports and exports | FR-RPT-001 to FR-RPT-006 | RPT-001 to RPT-006 | Phase 8 |
| AI adviser | FR-AI-001 to FR-AI-005 | AI-001 to AI-006 | Phase 9 |
| PWA and offline | FR-PWA-001 to FR-OFF-003 | OFF-001 to OFF-004 | Phase 10 |
| UX, language, audit, preservation, delivery | FR-UX-001 to FR-DEL-003 | UX-001, I18N-001, AUD-001 to AUD-002, DATA-001 to DATA-002, TEST-001 to TEST-003, DEL-001 to DEL-003 | Incremental |

## 16. Validation expectations

Later test and use-case documents shall map their identifiers back to these requirements. At minimum, validation must cover:

- allowed and denied actions for every role;
- cross-workspace identifier substitution, list, aggregate, export, and AI-preparation attempts;
- exactly-one-owner bootstrap and transfer behavior under retry, failure, and concurrency;
- Contributor restricted-total leakage and Advisor mutation attempts;
- empty, missing, incomplete, unreliable, and zero-denominator states;
- duplicate, retry, concurrent, and offline-conflict behaviour;
- decimal precision, unit compatibility, payment reconciliation, and no double counting;
- archive, cancellation, correction, reversal, and historical preservation; and
- phase boundaries proving that no requirement is implemented prematurely.

This document defines behaviour only. It creates no API schema, database model, UI component, or application code.
