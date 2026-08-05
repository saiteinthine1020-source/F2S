# F2S End-to-End Use Cases

## 1. Purpose

This document defines the critical F2S workflows from a user's trigger to an observable
outcome. It translates the [Functional Requirements](03_Functional_Requirements.md),
[Non-Functional Requirements](04_Non_Functional_Requirements.md), [User
Stories](05_User_Stories.md), and [Workspace and Identity
Foundation](12_Workspace_Identity_Design.md) into normal, alternate, failure, recovery,
authorization, audit, approval, and workspace-isolation paths.

The use cases describe intended product behaviour across all delivery phases. They do not authorise implementation before the corresponding milestone and prerequisite design issues are active.

## 2. Use-case convention

Each use case has a stable identifier in the form `UC-<AREA>-<NUMBER>` and records:

- actors and permissions;
- preconditions and trigger;
- normal flow;
- alternate, incomplete-data, empty, cancellation, archive, and failure paths where applicable;
- postconditions and recovery guarantees;
- required audit evidence and workspace-isolation checks; and
- traceability to functional requirements and user stories.

References to an `authorized user` mean an authenticated actor whose Active membership,
selected workspace, and backend capability permit the action. A hidden or disabled client
control is not an authorization control.

## 3. Cross-cutting rules

These rules apply to every use case unless a stricter referenced requirement applies:

1. The backend establishes the actor, selected workspace, membership state, and capability before protected data is read or changed.
2. Record identifiers, filters, aggregates, generated files, AI inputs, audit searches, and queued operations remain scoped to the selected workspace.
3. A denial uses a safe, consistent response that does not confirm whether another workspace's resource or global account exists.
4. A failed validation or multi-record operation creates no partial business state.
5. Retried writes create one intended business event or an explicit conflict; they never silently duplicate or overwrite newer data.
6. Financial events use canonical references so cash flow, project results, debts, receivables, reports, and dashboards count each event once.
7. Empty, unavailable, incomplete, estimated, failed, queued, and conflicted states are explicit; zero is shown only when zero is a verified value.
8. Audit and operational evidence excludes passwords, tokens, full payment details, unmasked AI payloads, and unnecessary personal data.
9. Cancellation, archive, correction, and reversal preserve attributable history. Ordinary actions do not hard-delete linked financial or farming facts.
10. English, Shan, Myanmar, and Japanese localization readiness and accessible mobile interaction apply to every user-facing normal and recovery path.
11. Contributor submissions are Pending and affect no official dataset until Admin approval.
12. Contributor responses omit restricted totals; Advisor mutations are denied by the backend.

## 4. Use-case catalogue

| ID | Use case | Primary actor(s) | Earliest phase | Principal requirement coverage |
| --- | --- | --- | --- | --- |
| UC-IAM-001 | Bootstrap the first Admin and workspace | First-time operator | Phase 1 | FR-IAM-001, FR-WS-001, FR-AUTHZ-006 |
| UC-IAM-002 | Activate account, sign in, recover access, and select workspace | Pending or Active user | Phase 1 | FR-IAM-002, FR-IAM-005, FR-AUTHZ-001 |
| UC-IAM-003 | Manage Contributor and Advisor memberships | Admin | Phase 1 | FR-IAM-003, FR-IAM-004, FR-AUTHZ-004, FR-AUD-001 |
| UC-IAM-004 | Transfer workspace ownership atomically | Admin and target member | Phase 1 | FR-IAM-006, FR-AUTHZ-006 |
| UC-WS-001 | Maintain consequential workspace settings | Admin | Phase 1 | FR-WS-001, FR-WS-002 |
| UC-HH-001 | Superseded by UC-WS-001; no separate household tenant flow | Admin | Phase 1 | FR-HH-001, FR-HH-002 |
| UC-FIN-001 | Submit, approve, reject, and correct a workspace finance event | Admin, Contributor; Advisor review | Phase 2 | FR-FIN-001 to FR-FIN-010 |
| UC-FARM-001 | Start from an empty farming workspace and create an investment | Admin or permitted Contributor | Phase 3 | FR-FARM-001 to FR-FARM-005, FR-FARM-010 |
| UC-FARM-002 | Progress, cancel, archive, and restore an investment | Admin or permitted Contributor | Phase 3 | FR-FARM-006 to FR-FARM-009, FR-DATA-001 |
| UC-PROFIT-001 | Record costs, harvests, sales, and verified profitability | Authorised record contributor | Phase 4 | FR-COST-001 to FR-CALC-003 |
| UC-PLAN-001 | Compare history and create an investment-planning scenario | Admin; Advisor read when permitted | Phase 5 | FR-DQ-001 to FR-REC-001 |
| UC-FUNDS-001 | Record remittance, debt, receivable, and payments | Admin or permitted Contributor | Phase 6 | FR-REM-001 to FR-RECV-002 |
| UC-DASH-001 | Review a filtered Basic workspace dashboard | Admin or Advisor | Phase 7 | FR-DASH-001 to FR-DASH-004 |
| UC-RPT-001 | Generate, preview, and retrieve a secure report | Admin or permitted Advisor | Phase 8 | FR-RPT-001 to FR-RPT-006 |
| UC-AI-001 | Request a masked localized AI explanation | Admin or permitted Advisor | Phase 9 | FR-AI-001 to FR-AI-005 |
| UC-OFF-001 | Save, queue, synchronize, and resolve offline work | Admin or permitted Contributor | Phase 10 | FR-PWA-001, FR-OFF-001 to FR-OFF-003 |
| UC-SEC-001 | Deny unauthorized and cross-workspace access | Any unauthorized or over-privileged actor | Phase 1 onward | FR-AUTHZ-001 to FR-AUTHZ-006 |
| UC-AUD-001 | Review safe audit evidence | Admin; Advisor when explicitly permitted | Phase 1 onward | FR-AUD-001, FR-AUD-002 |

## 5. Identity and workspace use cases

### UC-IAM-001: Bootstrap the first Admin and workspace

**Actors:** First-time operator.

**Preconditions:** No bootstrap-complete record, user, workspace, or owner exists. The
deployment is connected to its authoritative PostgreSQL database.

**Trigger:** The operator opens the one-time setup flow.

**Normal flow:**

1. The operator enters name, normalized email, password, preferred language, and timezone.
2. The operator enters workspace name, type, base currency, timezone, language, and optional profile fields.
3. The backend obtains the single-winner bootstrap lock and rechecks eligibility.
4. The backend validates the password, workspace fields, type, modules, and currencies.
5. One transaction creates the account, workspace, Active Admin membership, ownership reference, bootstrap-complete evidence, and safe audit events.
6. The system establishes the authenticated session and selected workspace without exposing credentials in URLs or logs.

**Alternate and failure paths:**

- A concurrent attempt that loses the lock receives a safe already-configured response and creates nothing.
- Invalid input returns field-safe errors and creates no partial identity or workspace.
- Database failure rolls back the account, workspace, membership, ownership, and audit transaction.
- Once complete, ordinary bootstrap remains unavailable; public self-registration is not enabled.

**Postconditions and recovery:** Exactly one Active Admin owns the first workspace. Failure
leaves no partial user, ownerless workspace, second owner, or session.

**Audit and isolation:** Record bootstrap success or safe failure metadata without storing
the password, token, complete submitted profile, or unnecessary personal data.

**Traceability:** FR-IAM-001, FR-WS-001, FR-AUTHZ-006; US-ADMIN-001; NFR-SEC-001,
NFR-COR-004, NFR-REL-005.

### UC-IAM-002: Activate account, sign in, recover access, and select workspace

**Actors:** Pending or Active user; Admin as member-access initiator.

**Preconditions:** Bootstrap is complete. Activation requires a Pending membership with an
eligible challenge; sign-in or recovery uses a normalized email without exposing whether an
unrelated account exists.

**Trigger:** The user opens activation, sign-in, or recovery.

**Normal flow:**

1. Activation validates an expiring single-use challenge and establishes the user's password under policy.
2. Sign-in validates credentials under rate limits and creates opaque access and rotating refresh credentials.
3. Recovery returns the same public response for existing and non-existing accounts and consumes an eligible single-use challenge before password replacement.
4. The system lists only Active workspace memberships for selection.
5. The user selects one workspace and the backend revalidates account state, membership state, role, and capability on every protected request.
6. Navigation and response schemas contain only capabilities and data permitted in that workspace.

**Alternate and failure paths:** Invalid, expired, replaced, reused, revoked, or suspended
credentials fail safely. A user with no Active membership receives no protected data.
Password change or recovery revokes sessions according to policy. Logout revokes the current
session. Cancellation creates no new session.

**Postconditions and recovery:** A successful session identifies one selected workspace but
does not embed permanent role authority. A failed flow exposes no protected data or account-
existence signal.

**Audit and isolation:** Record activation, sign-in result, refresh rotation/reuse, logout,
password change, recovery completion, and workspace selection using safe metadata only.

**Traceability:** FR-IAM-002, FR-IAM-005, FR-AUTHZ-001, FR-AUTHZ-005; US-CONTRIB-001,
US-ADVISOR-001, US-NEG-005; NFR-SEC-001, NFR-SEC-004, NFR-REL-005.

### UC-IAM-003: Manage Contributor and Advisor memberships

**Actors:** Admin; affected Contributor or Advisor.

**Preconditions:** The Admin owns the selected workspace. The target is not the current
owner membership.

**Trigger:** The Admin creates access, changes Contributor/Advisor role, suspends,
reactivates, restarts activation, or revokes access.

**Normal flow:**

1. The system lists only memberships in the selected workspace and safe activity fields.
2. The Admin selects a permitted action and confirms consequential changes.
3. The backend validates target state, requested role, account privacy, and the sole-owner invariant.
4. Member creation produces a Pending membership and digest-stored single-use activation challenge.
5. Role and state changes apply atomically and revoke affected sessions as designed.
6. Historical actor references remain intact and safe notifications/audit events are created.

**Alternate and failure paths:** A Contributor or Advisor direct request is denied. Generic
membership changes cannot create an Admin. Restarting activation invalidates prior
challenges. Duplicate, cross-workspace, invalid-state, and failed operations create no
partial change or global-account disclosure.

**Postconditions and recovery:** Account state and membership state remain separate and the
target has one unambiguous membership state and role in this workspace.

**Audit and isolation:** Record create, activation restart, role change, suspension,
reactivation, revocation, and denials without credential material.

**Traceability:** FR-IAM-003, FR-IAM-004, FR-AUTHZ-002, FR-AUTHZ-004 to FR-AUTHZ-006;
US-ADMIN-003, US-NEG-002, US-NEG-003; NFR-SEC-001, NFR-COR-004, NFR-COR-006.

### UC-IAM-004: Transfer workspace ownership atomically

**Actors:** Current Admin/Workspace Owner; target Active Contributor or Advisor.

**Preconditions:** Exactly one Active Admin owns the workspace. Both accounts are eligible
and the target membership belongs to the same workspace.

**Trigger:** The current owner initiates ownership transfer.

**Normal flow:**

1. The owner selects the target and the former-owner destination role.
2. The backend requires recent reauthentication and the configured additional verification.
3. The backend creates an expiring, digest-stored, single-use transfer request and notifies the target.
4. The target confirms the request after authenticating.
5. One transaction locks the workspace and memberships, revalidates the invariant, promotes the target to Admin, moves ownership, and changes the former owner to Contributor or Advisor.
6. The system revokes security-relevant sessions, notifies both parties, and records safe audit events.

**Alternate and failure paths:** Expired, cancelled, replaced, reused, cross-workspace, or
unconfirmed requests fail. Any validation, lock, or commit failure preserves the original
owner. Generic membership endpoints cannot perform the transfer.

**Postconditions and recovery:** Success leaves exactly one Active Admin owner. Failure
leaves exactly the original owner. High-assurance owner recovery remains a separately
controlled operational path.

**Audit and isolation:** Initiation, confirmation, cancellation, expiry, denial, and
completion are audited; challenges and sensitive proof are never logged.

**Traceability:** FR-IAM-006, FR-AUTHZ-004, FR-AUTHZ-006; US-ADMIN-004, US-NEG-004;
NFR-SEC-001, NFR-COR-004, NFR-COR-006.

### UC-WS-001: Maintain consequential workspace settings

**Actors:** Admin.

**Preconditions:** The selected workspace is Active and its current type and module
configuration are available.

**Trigger:** The Admin edits name, type, base currency, timezone, language, optional profile
fields, or module configuration.

**Normal flow:**

1. The system loads the selected workspace's current versioned settings.
2. The Admin edits fields permitted by the workspace type and module policy.
3. The backend validates values, dependencies, historical impact, and Admin capability.
4. Consequential type, module, currency, timezone, or unit changes explain effects and require confirmation.
5. The system applies the update atomically without changing the stable workspace ID or silently rewriting historical facts.
6. Later displays and calculations use the new context only where approved rules allow.

**Alternate and failure paths:** Invalid values preserve safe input for correction and do
not partially update settings. Cancellation preserves the original version. Contributor,
Advisor, stale-version, and cross-workspace requests are denied safely.

**Postconditions and recovery:** Settings are versioned and audited. Disabled modules do not
expose or delete historical data. Rename preserves the stable workspace ID.

**Audit and isolation:** Record consequential safe before/after values or references without
unnecessary sensitive content.

**Traceability:** FR-WS-001, FR-WS-002, FR-AUTHZ-002, FR-AUD-001; US-ADMIN-002,
US-NEG-001; NFR-COR-005, NFR-I18N-001, NFR-OBS-003.

### UC-HH-001: Superseded household-settings flow

UC-HH-001 is retained as a stable historical identifier and superseded by UC-WS-001.
Household is a workspace type or enabled domain, not a separate tenant, membership, owner,
or authorization context.

## 6. Finance and farming use cases

### UC-FIN-001: Submit, approve, reject, and correct a workspace finance event

**Actors:** Admin; Contributor; Advisor as reviewer without mutation authority.

**Preconditions:** The selected workspace, allowed categories, currency, membership, and
actor capabilities are established.

**Trigger:** An Admin records an event or a Contributor submits income or expense,
optionally with a permitted receipt.

**Normal flow:**

1. The actor enters classification, exact decimal amount, currency, date, counterparty/source, payment method, and permitted optional data.
2. The backend validates capability, workspace scope, amount, currency, dates, field lengths, relationships, and attachment policy.
3. An Admin-created authorized event may be Approved under policy; a Contributor-created event is committed as Pending with audit evidence.
4. Pending values appear only in permitted submission/review views and affect no official total, report, export, forecast, or AI dataset.
5. The Admin reviews and atomically Approves or Rejects the submission; an Advisor may comment or flag but cannot decide.
6. Approved views and filters include the canonical event exactly once at documented precision.
7. A later correction, reversal, archive, or attachment change preserves the prior state and approval history.

**Alternate and failure paths:** Invalid values, unsafe files, cross-workspace references,
and missing fields fail without a partial event. Retry returns the original result or an
explicit conflict. An Advisor mutation or Contributor approval request is denied. A
Contributor totals/report request returns no restricted aggregate. Rejected records remain
attributable. Ordinary hard delete is unavailable.

**Postconditions and recovery:** Success creates one intended event in an explicit state.
Only Approved state affects official datasets; failure creates none.

**Audit and isolation:** Record submission, review, comment/flag, approval, rejection,
correction, reversal, archive, attachment change, and policy-defined denial using safe
workspace-scoped metadata.

**Traceability:** FR-FIN-001 to FR-FIN-010, FR-AUTHZ-002 to FR-AUTHZ-004, FR-DATA-001;
US-ADMIN-006, US-ADMIN-007, US-CONTRIB-002 to US-CONTRIB-004, US-ADVISOR-002,
US-ADVISOR-003, US-NEG-002, US-NEG-003, US-NEG-007; NFR-COR-001 to NFR-COR-006,
NFR-SEC-008.

### UC-FARM-001: Start from an empty farming workspace and create an investment

**Actors:** Admin or permitted Contributor; Advisor as read-only actor.

**Preconditions:** The user has selected a workspace with the Farming module; no investment is required to exist. Crop categories and locations may also be empty.

**Trigger:** The user opens Farming Investments and chooses `Add Farming Investment`.

**Normal flow:**

1. With no investments, the system shows explanatory empty-state text and the permitted Add action, with no fabricated project, KPI, chart, forecast, or recommendation.
2. The actor starts the explicit creation flow.
3. The actor selects an active crop category or enters the separate category-creation flow; creating or selecting a category alone creates no investment.
4. The actor supplies season, year, location, optional positive field size and compatible unit, valid planting dates, non-negative planned budget, explicit currency, initial Planned or Active status, and optional notes.
5. The backend validates permission, workspace ownership of referenced records, field compatibility, and request idempotency.
6. The system atomically creates one investment and records its audit event.
7. The detail state shows planned budget as entered, actual investment and revenue as verified zero with missing-record context, profit/loss and ROI as unavailable, recommendation as insufficient data, and no fabricated graph.

**Alternate and failure paths:**

- Empty categories or locations offer an explicit permitted creation path without silently creating an investment.
- Missing or contradictory data is identified; recoverable input is preserved for correction.
- Cancelling the form creates no category unless it was separately confirmed and creates no investment.
- Network uncertainty or repeated submission creates one investment or an explicit duplicate/conflict result.
- An Advisor can see permitted empty/read-only states but cannot create a project.

**Postconditions and recovery:** Success creates one workspace-scoped investment. Failure or cancellation creates no partial investment. No calculation is presented as available without its inputs.

**Audit and isolation:** Record category creation and investment creation as distinct actions. Cross-workspace category, location, or project identifiers follow UC-SEC-001.

**Traceability:** FR-FARM-001 to FR-FARM-005, FR-FARM-010, FR-UX-001; US-ADMIN-008, US-CONTRIB-005, US-ADVISOR-002; NFR-REL-006, NFR-A11Y-001 to NFR-A11Y-005.

### UC-FARM-002: Progress, cancel, archive, and restore an investment

**Actors:** Admin or permitted Contributor; Advisor as denied mutation actor.

**Preconditions:** A workspace-scoped investment exists in a known lifecycle state.

**Trigger:** The actor edits allowed facts or requests a lifecycle transition.

**Normal flow:**

1. The system displays editable source facts separately from read-only calculated outputs.
2. The backend validates the requested transition against Planned, Active, Harvesting, Completed, Cancelled, and Archived rules.
3. A valid ordinary transition records previous state, new state, actor, time, and required reason.
4. To cancel, the actor reviews the consequences, supplies a reason, and explicitly confirms.
5. The cancelled project and linked costs, harvests, sales, notes, and audit history remain preserved; analytics and forecast treatment is explicit.
6. To archive an eligible project, the actor confirms; the project leaves default active views but remains retrievable in authorised history and reports.
7. Restoration is a separate explicit, authorised, audited action that returns the record to the policy-defined state.

**Alternate and failure paths:**

- An invalid transition is rejected without changing state.
- Cancelling the confirmation leaves the project unchanged.
- A cancellation without a reason is rejected.
- An ordinary hard-delete request is denied.
- Concurrent or stale edits produce an explicit conflict rather than overwriting newer facts.
- Attempting to edit calculated outputs or mutate as an Advisor is denied by the backend.

**Postconditions and recovery:** Linked history remains intact in every terminal or archived state. A failed, cancelled, or conflicted transition preserves the previously committed state.

**Audit and isolation:** Record successful and policy-defined denied transitions, reasons, actor, workspace, timestamps, and correlation ID. Another workspace's project is not disclosed.

**Traceability:** FR-FARM-006 to FR-FARM-010, FR-DATA-001; US-ADMIN-008, US-CONTRIB-005, US-NEG-006, US-NEG-008; NFR-COR-004, NFR-REL-006.

### UC-PROFIT-001: Record costs, harvests, sales, and verified profitability

**Actors:** Admin or permitted Contributor; Advisor as authorized reader of Approved results.

**Preconditions:** An eligible farming investment exists; finance, numeric, unit, allocation, and calculation policies are approved.

**Trigger:** The actor records a direct/shared cost, harvest, crop sale, or sale payment.

**Normal flow:**

1. A direct cost is linked to exactly one project and one canonical finance event, or a shared cost records its approved allocation basis across authorised projects.
2. Percentage allocation is confirmed only when shares total 100 percent.
3. Harvest entry validates quantity, unit, quality, loss, usable quantity, storage, and date against the selected project.
4. Sale entry validates quantity/unit, decimal unit price, gross amount, buyer, dates, payment state, cash received, outstanding amount, selling costs, and project ownership.
5. The backend commits each business event atomically and recalculates affected projects through the single calculation service.
6. Recognised revenue, cash received, and outstanding receivable remain distinct; later payments reduce the balance and increase cash once.
7. The system presents investment, revenue, profit/loss, margin, ROI, recovery, break-even, unit cost, yield, and field-area results only when available, with period, unit, rounding, lifecycle, and data-quality context.

**Alternate and failure paths:**

- Allocation below or above 100 percent, negative/incompatible quantities, invalid payment relationships, and cross-workspace references are rejected without partial events.
- Zero denominators or missing costs/sales produce unavailable or incomplete reasons, not calculation errors or misleading zeros.
- An unpaid sale creates recognised revenue/receivable according to policy but not available cash.
- Overpayment, reversal, or correction follows an explicit audited path and never silently creates a negative balance.
- Cancelling entry before commit preserves the prior project and finance state.

**Postconditions and recovery:** Project, finance, sale, and receivable datasets reconcile at the smallest supported currency unit with no double counting.

**Audit and isolation:** Record source-event and allocation changes using safe references. Calculation output remains derived and cannot be edited directly.

**Traceability:** FR-COST-001 to FR-COST-003, FR-HARV-001, FR-HARV-002, FR-SALE-001, FR-SALE-002, FR-CALC-001 to FR-CALC-003; US-ADMIN-009, US-CONTRIB-005, US-ADVISOR-002; NFR-COR-001 to NFR-COR-004.

## 7. Analysis and funds use cases

### UC-PLAN-001: Compare history and create an investment-planning scenario

**Actors:** Admin; Advisor with permitted comparison access.

**Preconditions:** The selected workspace has authorized Approved historical data or the Admin can supply explicit planning assumptions.

**Trigger:** The actor opens crop comparison or investment planning.

**Normal flow:**

1. The actor selects authorised crop, season, year, location, field, and other comparison filters.
2. The system returns only eligible workspace investments with periods, units, profitability, unpaid sales, shared costs, losses, consistency, and data-quality context.
3. Rankings expose their inputs and reasons; revenue alone does not decide the result.
4. The actor creates a planning scenario with crop, field, production, price, cost change, reserve, investment limit, risk, notes, and explicit assumptions.
5. The deterministic backend produces Conservative, Expected, and Optimistic results with investment, revenue, profit/loss, ROI, break-even price, pre-harvest cash, funding gap, period, sources, assumptions, uncertainty, and estimate labels.
6. Recommendation status cites verified reasons and limitations, avoids profit guarantees, and leaves the decision with the family.
7. Saving a scenario creates no real investment or financial event.

**Alternate and failure paths:**

- With no eligible history, the system displays an honest empty/limited state and requests permitted assumptions.
- Incomplete or unreliable evidence blocks a confident ranking/recommendation or clearly limits it.
- Missing assumptions keep the scenario incomplete; the system never invents values.
- Repeating identical inputs and rules produces identical deterministic outputs.
- An Advisor may inspect permitted results but cannot save or mutate a scenario.

**Postconditions and recovery:** Historical facts, user assumptions, calculated estimates, and recommendation explanations remain distinguishable and workspace-scoped.

**Audit and isolation:** Scenario changes, forecasts, and recommendation requests are audited according to policy. Cross-workspace history never affects inputs, counts, or rankings.

**Traceability:** FR-DQ-001, FR-DQ-002, FR-ANL-001, FR-ANL-002, FR-PLAN-001 to FR-PLAN-004, FR-REC-001; US-ADMIN-009, US-ADVISOR-002; NFR-COR-002, NFR-RPT-001.

### UC-FUNDS-001: Record remittance, debt, receivable, and payments

**Actors:** Admin or Contributor with the required capability; Advisor with read-only permission.

**Preconditions:** Workspace currency, decimal, counterparty-reference, and canonical finance-event policies are available.

**Trigger:** The actor records external funds, an obligation, a receivable, or a related payment.

**Normal flow:**

1. A remittance records permitted sender/receiver references, source/destination amounts and currencies, exchange rate, fee, dates, method, purpose, and notes.
2. The actor allocates the permitted remittance amount among household, farm, education, debt, savings, or other uses; allocations reconcile before confirmation.
3. A debt records lender reference, original amount, currency, interest terms, dates, purpose, collateral notes, and status.
4. A debt repayment links to one debt and one canonical finance event and reduces its balance once.
5. A standalone or sale-linked receivable records its origin, amount, dates, debtor reference, status, and outstanding balance without losing the sale link.
6. A receivable payment reduces outstanding balance and contributes to cash received once.
7. Authorised summaries reconcile original amounts, allocations, payments, fees, cash flow, and balances.

**Alternate and failure paths:**

- Non-reconciling remittance allocations, invalid exchange/amount relationships, excessive repayment, silent overpayment, and negative outstanding balances are rejected.
- An unpaid crop sale remains receivable and recognised revenue according to policy but is not presented as cash received.
- Corrections and reversals are explicit and preserve the original event.
- Cancelling before confirmation creates no partial allocation, debt, receivable, or payment.
- An Advisor may see permitted masked summaries but cannot create payments.

**Postconditions and recovery:** Each real transfer or payment contributes once to its balance and cash-flow effect. Failed multi-record operations leave no partial finance event.

**Audit and isolation:** Audit permitted creates, allocations, payments, corrections, and denials without exposing prohibited payment details. Every linked resource belongs to the selected workspace.

**Traceability:** FR-REM-001, FR-REM-002, FR-DEBT-001, FR-DEBT-002, FR-RECV-001, FR-RECV-002, FR-FIN-005; US-ADMIN-010, US-CONTRIB-006, US-ADVISOR-003, US-NEG-006; NFR-PRIV-001, NFR-COR-003, NFR-COR-004.

## 8. Dashboard, report, and AI use cases

### UC-DASH-001: Review a filtered workspace dashboard

**Actors:** Admin or Advisor with permission to view the selected dashboard areas.

**Preconditions:** The actor has an Active membership in the selected workspace and at least one permitted dashboard capability.

**Trigger:** The actor opens the dashboard or changes period/module filters.

**Normal flow:**

1. The backend validates workspace context and permissions for every requested dashboard area.
2. The actor selects a period and permitted household-domain, cash-flow, farm, crop, remittance, debt, receivable, or planning filters.
3. The backend uses verified versioned datasets and the shared calculation service.
4. The dashboard labels period, currency, units, filter context, calculation availability, and data quality.
5. Only authorised values, counts, charts, and next actions render.

**Alternate and failure paths:**

- A new workspace or filter with no data receives explanatory empty states rather than fabricated KPIs or zero-filled charts.
- Incomplete or unreliable data produces visible limitations and does not appear confident.
- Failure of one optional panel does not corrupt already verified data; the panel shows a safe retry/error state with correlation ID where applicable.
- A filter or identifier targeting another workspace follows UC-SEC-001.
- A Contributor is denied dashboard totals even when that contributor created source records.

**Postconditions and recovery:** Dashboard viewing changes no source facts. Equivalent later report filters can reconcile to the same dataset version.

**Audit and isolation:** Sensitive dashboard access is audited only where policy requires; telemetry and logs contain no prohibited raw financial or personal data.

**Traceability:** FR-DASH-001, FR-DASH-002, FR-AUTHZ-003, FR-DQ-002; US-ADMIN-011, US-ADVISOR-004, US-NEG-007; NFR-PERF-003, NFR-RPT-001.

### UC-RPT-001: Generate, preview, and retrieve a secure report

**Actors:** Admin or Advisor with explicit report and format permission.

**Preconditions:** Report type, permitted format, filter policy, dataset version, storage, expiry, and download controls are configured.

**Trigger:** The actor requests a PDF, Excel, CSV, preview, or print result.

**Normal flow:**

1. The actor selects report type, period, workspace-scoped filters, and a permitted format.
2. Before generation, the backend authorises report type, fields, dataset, format, and selected workspace.
3. The reporting service consumes the same verified dataset and calculation outputs used by the equivalent dashboard.
4. The system generates the requested format with safe file naming and temporary storage.
5. PDF output includes required print context; Excel contains valid linked data/charts; CSV contains documented raw tabular columns only.
6. The actor previews, prints, or downloads through an authorised expiring reference.
7. Generation and retrieval are audited, and cleanup follows retention policy.

**Alternate and failure paths:**

- Unauthorised type, format, field, filter, or workspace requests fail before a file is generated.
- Empty datasets create an honest empty report or prevent generation according to the report design; they never inject sample data.
- Generation timeout/failure leaves no exposed partial file and offers safe retry status.
- Guessed, expired, traversed, cross-workspace, or already-cleaned download references fail consistently.
- Cancelling before generation creates no file; cancelling a running job follows the approved safe job policy.

**Postconditions and recovery:** A successful file is attributable to one actor, workspace, dataset version, filter set, and expiry. Equivalent formats reconcile at documented precision.

**Audit and isolation:** Audit generation and download metadata without embedding the report contents. File storage, names, links, logs, and cleanup cannot expose another workspace.

**Traceability:** FR-RPT-001 to FR-RPT-006, FR-AUTHZ-003; US-ADMIN-011, US-ADVISOR-005, US-NEG-007; NFR-SEC-008, NFR-RPT-001 to NFR-RPT-003.

### UC-AI-001: Request a masked Shan AI explanation

**Actors:** Admin or Advisor with permission for the selected verified dataset and AI purpose.

**Preconditions:** A permitted verified dataset exists; masking, output schema, language, timeout, retention, and fallback policies are approved.

**Trigger:** The actor asks for a Shan explanation of a permitted result, forecast, or limitation.

**Normal flow:**

1. The backend authorises actor, workspace, dataset, purpose, and data sufficiency before any external request.
2. The backend selects structured verified facts, estimates, periods, assumptions, uncertainty, and data-quality context.
3. It removes or replaces prohibited personal, contact, address, payment, authentication, secret, reference, and unnecessary free-text fields.
4. The system validates the masked outbound structure, then calls Gemini within bounded timeout and retry policy.
5. The response is structurally and safely validated and cannot replace authoritative backend calculations.
6. The user receives a Shan explanation that distinguishes fact from forecast, identifies missing information, states uncertainty, avoids guarantees, and leaves decisions with the family.
7. Safe metadata about request purpose, model, result, actor, workspace, and correlation is audited without retaining unmasked payloads.

**Alternate and failure paths:**

- Unauthorised, cross-workspace, unsupported-purpose, empty, insufficient, or unreliable-data requests are rejected before Gemini is called.
- If masking or outbound validation fails, nothing is transmitted.
- Timeout, rate limit, outage, malformed output, unsafe output, or incompatible schema returns a safe fallback and does not alter source data.
- The user may cancel before transmission; no external call occurs. Cancellation after transmission is reported according to the approved request state.
- AI output cannot create an investment, finance event, scenario decision, or report truth.

**Postconditions and recovery:** Verified source facts remain unchanged. The user can identify that the response is advisory and whether a fallback occurred.

**Audit and isolation:** Outbound payload tests prove prohibited fields are absent. Audit/log records store only safe metadata and remain workspace-scoped.

**Traceability:** FR-AI-001 to FR-AI-005, FR-DQ-002, FR-REC-001; US-ADMIN-012, US-ADVISOR-006, US-NEG-008; NFR-PRIV-002, NFR-PRIV-003, NFR-AI-001 to NFR-AI-003.

## 9. Offline, security, and audit use cases

### UC-OFF-001: Save, queue, synchronise, and resolve offline work

**Actors:** Admin or Contributor using a supported device; online backend during synchronisation.

**Preconditions:** The PWA shell was loaded successfully online; the operation and data fields are approved for offline use; the device has an eligible session/local-data state.

**Trigger:** Connectivity is absent, unstable, or lost during a supported write.

**Normal flow:**

1. The cached application shell reopens and clearly displays connection state.
2. The actor creates an approved local draft; the interface distinguishes draft from server-committed data.
3. On submission without connectivity, the system validates what it can locally, assigns duplicate-protection metadata, queues the operation, and shows `Queued`.
4. When connectivity returns, the client revalidates authentication and sends the operation using bounded retry and backoff.
5. The backend rechecks current actor, workspace, permission, referenced resources, validation, version, and idempotency.
6. A successful commit creates one intended event and the client marks it `Synchronised`.
7. A version conflict shows the affected record and safe choices; unsupported conflicts require online review.

**Alternate and failure paths:**

- Network loss before sending retains one local draft; loss during transfer or after server commit produces one queued/recoverable operation, never silent loss.
- Expired authentication pauses the queue and requires safe reauthentication; it does not loop indefinitely.
- Validation, permission, deactivation, missing-resource, permanent, or cross-workspace errors stop retry and show a safe failed state.
- A newer server version is never overwritten silently; the item becomes `Conflicted`.
- Duplicate replay returns the original result or explicit duplicate status.
- The actor may cancel an unsent local draft according to local retention policy; cancelling a committed event requires its normal domain correction path.

**Postconditions and recovery:** Every supported write is visibly local, queued, synchronising, synchronised, failed, or conflicted. The server contains zero or one intended committed mutation.

**Audit and isolation:** Only server-accepted operations create normal business audit evidence; policy may record safe denied sync attempts. Local sensitive-data scope, expiry, clearing, and logout follow approved privacy rules.

**Traceability:** FR-PWA-001, FR-OFF-001 to FR-OFF-003, FR-FARM-010; US-ADMIN-008, US-CONTRIB-005; NFR-OFF-001 to NFR-OFF-005, NFR-REL-006.

### UC-SEC-001: Deny unauthorised and cross-workspace access

**Actors:** Unauthenticated visitor; authenticated user without the requested capability; user manipulating another workspace's identifier; deactivated member.

**Preconditions:** A protected operation, record, filter, file, report, aggregate, audit query, or AI target is requested.

**Trigger:** Actor/session/workspace context is absent or the requested action/resource is outside the actor's current authority.

**Normal flow:**

1. The backend identifies the available actor/session context without trusting client-supplied role or hidden-control state.
2. It validates active membership, selected workspace, action permission, and workspace ownership of every direct and indirect resource.
3. The request is denied before protected data is returned, changed, aggregated, exported, logged unsafely, or sent to AI.
4. The response uses the approved safe status, stable error code, and correlation ID without confirming that an unauthorised resource exists.
5. A policy-defined safe audit event records the denial without prohibited content.

**Covered attack and error paths:**

- Change a URL or resource identifier to another workspace.
- Add another workspace to a list/search filter or pagination cursor.
- Submit create/update/archive/cancel/pay/allocate/invite/role-change requests without the required role and capability.
- Request another workspace's dashboard aggregate, report generation, generated file, audit record, forecast, or AI explanation.
- Request restricted totals or reports as a Contributor.
- Attempt to mutate calculated totals, report datasets, data-quality state, or AI-prepared verified values.
- Retry a previously permitted queued request after membership deactivation or workspace-context change.

**Postconditions and recovery:** No protected fact is disclosed or changed. Legitimate access requires an approved membership/capability change or correct workspace selection, not client manipulation.

**Audit and isolation:** Isolation tests use at least two workspaces and identifier substitution across every repository, endpoint, job, file, aggregate, and external-payload boundary.

**Traceability:** FR-AUTHZ-001 to FR-AUTHZ-006; US-NEG-001 to US-NEG-004; NFR-SEC-001, NFR-SEC-009, NFR-PRIV-002.

### UC-AUD-001: Review safe audit evidence

**Actors:** Admin; Advisor with an explicit audit capability; Contributor and other unauthorised actors as denied actors.

**Preconditions:** Policy-required authentication, membership, role, finance, farming, export, forecast, recommendation, or AI actions have occurred.

**Trigger:** An authorised actor investigates an operational, security, or data-correction question.

**Normal flow:**

1. The actor selects permitted time, action, result, actor, resource-type, and correlation filters.
2. The backend authorises the audit capability and scopes the query to the selected workspace.
3. Results show actor, workspace, action, resource reference, timestamp, correlation ID, result, and approved safe metadata.
4. The actor correlates an action with its business record or operational error without altering the audit evidence.
5. Empty results state that no authorised matching evidence exists and do not reveal another workspace's events.

**Alternate and failure paths:**

- Contributor and unpermitted-member audit requests are denied by the backend.
- Cross-workspace actor/resource filters return no disclosure and follow the safe denial contract.
- Passwords, tokens, authorisation headers, full payment details, unmasked AI data, and unnecessary raw values never render or appear in logs.
- Failure to load audit evidence changes no business record and returns a correlation ID for support.

**Postconditions and recovery:** Audit evidence remains immutable according to policy; review itself may be audited when required.

**Audit and isolation:** Audit access is itself workspace-scoped and capability-controlled. Retention and export, if later permitted, follow privacy and report policies.

**Traceability:** FR-AUD-001, FR-AUD-002, FR-AUTHZ-003; US-ADMIN-005, US-ADVISOR-001, US-NEG-005; NFR-COR-006, NFR-PRIV-002, NFR-OBS-001, NFR-OBS-002.

## 10. Acceptance and validation matrix

| Acceptance concern | Covered by | Required future validation |
| --- | --- | --- |
| Authentication and workspace context | UC-IAM-001 to UC-IAM-004 | Bootstrap, activation, recovery, session, membership, ownership-transfer, and multi-workspace tests |
| Unauthorised and cross-workspace paths | Every protected use case; UC-SEC-001 | Two-workspace positive/negative isolation matrix |
| Finance and canonical-event correctness | UC-FIN-001, UC-PROFIT-001, UC-FUNDS-001 | Decimal, rollback, idempotency, reconciliation, and reversal fixtures |
| True empty and incomplete-data states | UC-FARM-001, UC-PLAN-001, UC-DASH-001, UC-RPT-001, UC-AI-001 | Empty workspace and incomplete/unreliable dataset walkthroughs |
| Cancellation and archive | UC-IAM-001 to UC-IAM-004, UC-WS-001, UC-FIN-001, UC-FARM-001, UC-FARM-002, UC-RPT-001, UC-AI-001, UC-OFF-001 | Confirmation, rollback/no-partial-state, preservation, and retrieval checks |
| Reporting and secure file access | UC-RPT-001 | Cross-format reconciliation, render/workbook inspection, expiry, traversal, and cross-workspace tests |
| AI privacy and graceful failure | UC-AI-001 | Masking fixtures, outbound inspection, schema/safety validation, timeout, and fallback tests |
| Offline retry and conflict recovery | UC-OFF-001 | Disconnect-before/during/after-commit, replay, stale-version, deactivation, and queue-state tests |
| Audit event coverage and safe metadata | All use cases; UC-AUD-001 | Event-to-action matrix, correlation, prohibited-field, access, and retention tests |
| Accessibility and Shan-first mobile use | Every user-facing use case | Keyboard, screen-reader, touch, zoom/reflow, translation, and constrained-device checks |

Issue #5 remains satisfied by this baseline when every catalogued use case remains traceable, its exceptional paths are reviewable, audit and workspace-isolation expectations are explicit, and no endpoint contract, schema, wireframe, infrastructure, or application code is introduced.

## 11. Delivery constraint

These use cases are a behavioural specification, not a single implementation backlog. A later implementation issue must select a coherent use-case slice, cite the applicable functional and non-functional requirement IDs, define testable acceptance criteria for normal and negative paths, and remain within its active milestone.
