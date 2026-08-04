# F2S End-to-End Use Cases

## 1. Purpose

This document defines the critical F2S workflows from a user's trigger to an observable outcome. It translates the [Functional Requirements](03_Functional_Requirements.md), [Non-Functional Requirements](04_Non_Functional_Requirements.md), and [User Stories](05_User_Stories.md) into normal, alternate, failure, recovery, authorisation, audit, and household-isolation paths.

The use cases describe intended product behaviour across all delivery phases. They do not authorise implementation before the corresponding milestone and prerequisite design issues are active.

## 2. Use-case convention

Each use case has a stable identifier in the form `UC-<AREA>-<NUMBER>` and records:

- actors and permissions;
- preconditions and trigger;
- normal flow;
- alternate, incomplete-data, empty, cancellation, archive, and failure paths where applicable;
- postconditions and recovery guarantees;
- required audit evidence and household-isolation checks; and
- traceability to functional requirements and user stories.

References to an `authorised user` always mean an authenticated actor whose active membership, household context, and backend permission permit the specific action. A hidden or disabled client control is not an authorisation control.

## 3. Cross-cutting rules

These rules apply to every use case unless a stricter referenced requirement applies:

1. The backend establishes the actor, active household, membership state, and role before protected data is read or changed.
2. Record identifiers, filters, aggregates, generated files, AI inputs, audit searches, and queued operations remain scoped to the active household.
3. A denial uses a safe, consistent response that does not confirm whether another household's resource exists.
4. A failed validation or multi-record operation creates no partial business state.
5. Retried writes create one intended business event or an explicit conflict; they never silently duplicate or overwrite newer data.
6. Financial events use canonical references so cash flow, project results, debts, receivables, reports, and dashboards count each event once.
7. Empty, unavailable, incomplete, estimated, failed, queued, and conflicted states are explicit; zero is shown only when zero is a verified value.
8. Audit and operational evidence excludes passwords, tokens, full payment details, unmasked AI payloads, and unnecessary personal data.
9. Cancellation, archive, correction, and reversal preserve attributable history. Ordinary actions do not hard-delete linked financial or farming facts.
10. Shan-first mobile and accessible interaction requirements apply to every user-facing normal and recovery path.

## 4. Use-case catalogue

| ID | Use case | Primary actor(s) | Earliest phase | Principal requirement coverage |
| --- | --- | --- | --- | --- |
| UC-IAM-001 | Activate account, sign in, and select household | Invited user | Phase 1 | FR-IAM-001 to FR-IAM-005, FR-AUTHZ-001 |
| UC-IAM-002 | Manage membership and delegated role | Owner, Administrator | Phase 1 | FR-IAM-003, FR-IAM-004, FR-AUTHZ-004, FR-AUD-001 |
| UC-HH-001 | Maintain consequential household settings | Owner, authorised Administrator | Phase 1 | FR-HH-001, FR-HH-002 |
| UC-FIN-001 | Record and correct a household finance event | Authorised Owner, Administrator, Family Member | Phase 2 | FR-FIN-001 to FR-FIN-006 |
| UC-FARM-001 | Start from an empty farming workspace and create an investment | Authorised Owner, Administrator, Family Member | Phase 3 | FR-FARM-001 to FR-FARM-005, FR-FARM-010 |
| UC-FARM-002 | Progress, cancel, archive, and restore an investment | Authorised Owner or delegated actor | Phase 3 | FR-FARM-006 to FR-FARM-009, FR-DATA-001 |
| UC-PROFIT-001 | Record costs, harvests, sales, and verified profitability | Authorised record contributor | Phase 4 | FR-COST-001 to FR-CALC-003 |
| UC-PLAN-001 | Compare history and create an investment-planning scenario | Authorised Owner, Administrator, Family Member | Phase 5 | FR-DQ-001 to FR-REC-001 |
| UC-FUNDS-001 | Record remittance, debt, receivable, and payments | Authorised Owner, Administrator, Family Member | Phase 6 | FR-REM-001 to FR-RECV-002 |
| UC-DASH-001 | Review a filtered household dashboard | Authorised viewer | Phase 7 | FR-DASH-001, FR-DASH-002 |
| UC-RPT-001 | Generate, preview, and retrieve a secure report | Authorised report user | Phase 8 | FR-RPT-001 to FR-RPT-006 |
| UC-AI-001 | Request a masked Shan AI explanation | Authorised AI user | Phase 9 | FR-AI-001 to FR-AI-005 |
| UC-OFF-001 | Save, queue, synchronise, and resolve offline work | Authorised record contributor | Phase 10 | FR-PWA-001, FR-OFF-001 to FR-OFF-003 |
| UC-SEC-001 | Deny unauthorised and cross-household access | Any unauthorised or over-privileged actor | Phase 1 onward | FR-AUTHZ-001 to FR-AUTHZ-006 |
| UC-AUD-001 | Review safe audit evidence | Owner, authorised Administrator | Phase 1 onward | FR-AUD-001, FR-AUD-002 |

## 5. Identity and household use cases

### UC-IAM-001: Activate account, sign in, and select household

**Actors:** Invited user; authorised Owner or Administrator as invitation initiator.

**Preconditions:**

- Public self-registration is unavailable.
- An eligible invitation or provisioned account exists.
- The user has at least one active household membership for protected access.

**Trigger:** The invited user opens the approved activation or sign-in flow.

**Normal flow:**

1. The user submits the eligible activation evidence and creates credentials under the approved password policy.
2. The system validates the invitation, activates the account, and records the outcome without exposing credential material.
3. The user authenticates and receives the approved rotating session credentials.
4. If the user has one eligible membership, the system establishes that household context; if more than one exists, the user explicitly selects one.
5. The backend revalidates actor, membership, role, and household on the first protected request.
6. The system presents only navigation and data permitted for the selected household and role.

**Alternate and failure paths:**

- An invalid, expired, already-used, or ineligible invitation is rejected safely and creates no active membership.
- Invalid credentials, an expired or reused refresh token, or a deactivated account is rejected without revealing whether an unrelated account exists.
- A user with no active membership receives no protected household data and is directed to an approved support path.
- Cancelling activation or sign-in before success creates no session.
- Logout revokes or expires the session according to policy; a later protected request is rejected.
- A password change invalidates sessions according to the approved security design and preserves account history.

**Postconditions and recovery:** A successful session has one explicit active household context. A failed or cancelled flow leaves no partial session or protected-data disclosure.

**Audit and isolation:** Record invitation, activation, sign-in result, refresh, logout, password change, and household-context selection when policy requires. Never log secrets. Attempting to select an unowned household follows UC-SEC-001.

**Traceability:** FR-AUTHZ-001, FR-AUTHZ-005, FR-AUTHZ-006, FR-IAM-001 to FR-IAM-005; US-OWN-001 to US-OWN-003, US-MEM-001, US-VIEW-001; NFR-SEC-001, NFR-SEC-004, NFR-REL-005.

### UC-IAM-002: Manage membership and delegated role

**Actors:** Owner; Administrator within delegated policy; affected household member.

**Preconditions:** The actor has an active household context and membership-management permission.

**Trigger:** The actor invites, activates, deactivates, or changes the role of a member.

**Normal flow:**

1. The system shows only memberships belonging to the active household.
2. The actor selects an allowed action and supplies required invitation or role information.
3. The backend validates the actor's current authority, target membership, requested role, and ownership restrictions.
4. The actor confirms consequential changes.
5. The system applies the change atomically and records prior state, new state, actor, time, and result.
6. Deactivation prevents new access without deleting historical actor references.

**Alternate and failure paths:**

- An Administrator cannot transfer ownership or grant authority above delegated policy.
- A Viewer or unpermitted Family Member receives a backend denial even through a fabricated direct request.
- Deactivating an already inactive member produces an idempotent result or safe validation response.
- If applying the change fails, neither membership nor role is partially updated.
- Cancelling at confirmation preserves the original state and records no successful change.

**Postconditions and recovery:** The final membership state is unambiguous; sessions affected by deactivation or role reduction are handled according to security policy.

**Audit and isolation:** Successful and denied consequential actions are auditable. A target from another household is neither exposed nor modified.

**Traceability:** FR-AUTHZ-002, FR-AUTHZ-004 to FR-AUTHZ-006, FR-IAM-003, FR-IAM-004; US-ADM-001, US-NEG-002, US-NEG-003; NFR-SEC-001, NFR-COR-004, NFR-COR-006.

### UC-HH-001: Maintain consequential household settings

**Actors:** Owner; authorised Administrator within delegated settings.

**Preconditions:** An active household and permitted settings exist.

**Trigger:** The actor edits profile, base currency, timezone, language, financial-year preference, units, notes, or farming locations.

**Normal flow:**

1. The system loads the active household's current settings.
2. The actor edits permitted fields and submits them.
3. The backend validates values, compatibility, and permission for each changed field.
4. Consequential currency, timezone, unit, or similar changes show their effects and require confirmation.
5. The system saves the new settings without silently rewriting historical facts.
6. Later displays and calculations use the new context only where the approved rules allow.

**Alternate and failure paths:** Invalid values retain safe user input for correction and do not partially update settings. Cancellation preserves all original values. An unauthorised or cross-household request follows UC-SEC-001.

**Postconditions and recovery:** Current settings are versioned or auditable as designed; historical records retain original currency, unit, and timestamps unless a separately approved migration or correction occurs.

**Audit and isolation:** Record consequential old/new safe values or references according to policy, excluding sensitive raw content.

**Traceability:** FR-HH-001, FR-HH-002, FR-AUTHZ-002, FR-AUD-001; US-OWN-003, US-ADM-001; NFR-COR-005, NFR-I18N-001, NFR-OBS-003.

## 6. Finance and farming use cases

### UC-FIN-001: Record and correct a household finance event

**Actors:** Authorised Owner, Administrator, or Family Member; Viewer as denied mutation actor.

**Preconditions:** The active household, allowed categories, currency, and actor permission are established.

**Trigger:** The actor records income or expense, optionally including a permitted receipt.

**Normal flow:**

1. The actor chooses income or expense and enters the required classification, decimal amount, currency, date, counterparty/source, payment method, and optional reference, notes, or receipt.
2. The backend validates permission, household scope, positive/allowed amount, currency, dates, field lengths, and attachment policy.
3. The system commits one household-scoped canonical finance event and its required audit evidence atomically.
4. Authorised transaction views and matching filters show the event once.
5. Totals and downstream datasets include the event once at documented precision.
6. A later permitted correction, reversal, archive, or attachment change preserves the prior history.

**Alternate and failure paths:**

- Negative ordinary amounts, invalid currency/date relationships, unsafe files, and missing required fields are rejected without a partial event.
- The actor may cancel before confirmation; no event or receipt reference is committed.
- A retry after an uncertain response returns the original successful result or an explicit duplicate/conflict result.
- A linked sale, remittance, debt, receivable, or farming cost reuses or references the canonical event rather than creating duplicate income or expense.
- A Viewer or unpermitted member receives a backend denial.
- An ordinary delete request is unavailable or rejected; the approved correction, reversal, or archive path is offered where permitted.

**Postconditions and recovery:** Exactly one intended event exists after success; a failed flow creates none. Current and prior states remain attributable.

**Audit and isolation:** Record create, correction, reversal, archive, attachment change, and policy-defined denial using safe metadata. Filters, file access, and totals remain household-scoped.

**Traceability:** FR-FIN-001 to FR-FIN-006, FR-AUTHZ-002, FR-DATA-001; US-OWN-004, US-ADM-002, US-MEM-002, US-NEG-005; NFR-COR-001 to NFR-COR-006, NFR-SEC-008.

### UC-FARM-001: Start from an empty farming workspace and create an investment

**Actors:** Authorised Owner, Administrator, or Family Member; Viewer as read-only actor.

**Preconditions:** The user has selected a household; no investment is required to exist. Crop categories and locations may also be empty.

**Trigger:** The user opens Farming Investments and chooses `Add Farming Investment`.

**Normal flow:**

1. With no investments, the system shows explanatory empty-state text and the permitted Add action, with no fabricated project, KPI, chart, forecast, or recommendation.
2. The actor starts the explicit creation flow.
3. The actor selects an active crop category or enters the separate category-creation flow; creating or selecting a category alone creates no investment.
4. The actor supplies season, year, location, optional positive field size and compatible unit, valid planting dates, non-negative planned budget, explicit currency, initial Planned or Active status, and optional notes.
5. The backend validates permission, household ownership of referenced records, field compatibility, and request idempotency.
6. The system atomically creates one investment and records its audit event.
7. The detail state shows planned budget as entered, actual investment and revenue as verified zero with missing-record context, profit/loss and ROI as unavailable, recommendation as insufficient data, and no fabricated graph.

**Alternate and failure paths:**

- Empty categories or locations offer an explicit permitted creation path without silently creating an investment.
- Missing or contradictory data is identified; recoverable input is preserved for correction.
- Cancelling the form creates no category unless it was separately confirmed and creates no investment.
- Network uncertainty or repeated submission creates one investment or an explicit duplicate/conflict result.
- A Viewer can see permitted empty/read-only states but cannot create a project.

**Postconditions and recovery:** Success creates one household-scoped investment. Failure or cancellation creates no partial investment. No calculation is presented as available without its inputs.

**Audit and isolation:** Record category creation and investment creation as distinct actions. Cross-household category, location, or project identifiers follow UC-SEC-001.

**Traceability:** FR-FARM-001 to FR-FARM-005, FR-FARM-010, FR-UX-001; US-OWN-005, US-OWN-006, US-MEM-003, US-VIEW-002; NFR-REL-006, NFR-A11Y-001 to NFR-A11Y-005.

### UC-FARM-002: Progress, cancel, archive, and restore an investment

**Actors:** Authorised Owner or delegated Administrator/Family Member; Viewer as denied mutation actor.

**Preconditions:** A household-scoped investment exists in a known lifecycle state.

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
- Attempting to edit calculated outputs or mutate as a Viewer is denied by the backend.

**Postconditions and recovery:** Linked history remains intact in every terminal or archived state. A failed, cancelled, or conflicted transition preserves the previously committed state.

**Audit and isolation:** Record successful and policy-defined denied transitions, reasons, actor, household, timestamps, and correlation ID. Another household's project is not disclosed.

**Traceability:** FR-FARM-006 to FR-FARM-010, FR-DATA-001; US-OWN-006, US-ADM-003, US-NEG-004, US-NEG-005; NFR-COR-004, NFR-REL-006.

### UC-PROFIT-001: Record costs, harvests, sales, and verified profitability

**Actors:** Authorised record contributor; authorised Viewer of results.

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

- Allocation below or above 100 percent, negative/incompatible quantities, invalid payment relationships, and cross-household references are rejected without partial events.
- Zero denominators or missing costs/sales produce unavailable or incomplete reasons, not calculation errors or misleading zeros.
- An unpaid sale creates recognised revenue/receivable according to policy but not available cash.
- Overpayment, reversal, or correction follows an explicit audited path and never silently creates a negative balance.
- Cancelling entry before commit preserves the prior project and finance state.

**Postconditions and recovery:** Project, finance, sale, and receivable datasets reconcile at the smallest supported currency unit with no double counting.

**Audit and isolation:** Record source-event and allocation changes using safe references. Calculation output remains derived and cannot be edited directly.

**Traceability:** FR-COST-001 to FR-COST-003, FR-HARV-001, FR-HARV-002, FR-SALE-001, FR-SALE-002, FR-CALC-001 to FR-CALC-003; US-OWN-007, US-ADM-004, US-MEM-004, US-MEM-005; NFR-COR-001 to NFR-COR-004.

## 7. Analysis and funds use cases

### UC-PLAN-001: Compare history and create an investment-planning scenario

**Actors:** Authorised Owner, Administrator, or Family Member; Viewer with permitted comparison access.

**Preconditions:** The active household has authorised historical data or the user can supply explicit planning assumptions.

**Trigger:** The actor opens crop comparison or investment planning.

**Normal flow:**

1. The actor selects authorised crop, season, year, location, field, and other comparison filters.
2. The system returns only eligible household investments with periods, units, profitability, unpaid sales, shared costs, losses, consistency, and data-quality context.
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
- A Viewer may inspect permitted results but cannot save or mutate a scenario unless separately granted.

**Postconditions and recovery:** Historical facts, user assumptions, calculated estimates, and recommendation explanations remain distinguishable and household-scoped.

**Audit and isolation:** Scenario changes, forecasts, and recommendation requests are audited according to policy. Cross-household history never affects inputs, counts, or rankings.

**Traceability:** FR-DQ-001, FR-DQ-002, FR-ANL-001, FR-ANL-002, FR-PLAN-001 to FR-PLAN-004, FR-REC-001; US-OWN-008, US-ADM-005, US-VIEW-003; NFR-COR-002, NFR-RPT-001.

### UC-FUNDS-001: Record remittance, debt, receivable, and payments

**Actors:** Authorised Owner, Administrator, or Family Member; Viewer with read-only permission.

**Preconditions:** Household currency, decimal, counterparty-reference, and canonical finance-event policies are available.

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
- A Viewer may see permitted masked summaries but cannot create payments.

**Postconditions and recovery:** Each real transfer or payment contributes once to its balance and cash-flow effect. Failed multi-record operations leave no partial finance event.

**Audit and isolation:** Audit permitted creates, allocations, payments, corrections, and denials without exposing prohibited payment details. Every linked resource belongs to the active household.

**Traceability:** FR-REM-001, FR-REM-002, FR-DEBT-001, FR-DEBT-002, FR-RECV-001, FR-RECV-002, FR-FIN-005; US-OWN-009, US-ADM-006, US-MEM-006, US-VIEW-004; NFR-PRIV-001, NFR-COR-003, NFR-COR-004.

## 8. Dashboard, report, and AI use cases

### UC-DASH-001: Review a filtered household dashboard

**Actors:** Any user with permission to view the selected dashboard areas.

**Preconditions:** The actor has an active household and at least one permitted dashboard capability.

**Trigger:** The actor opens the dashboard or changes period/module filters.

**Normal flow:**

1. The backend validates household context and permissions for every requested dashboard area.
2. The actor selects a period and permitted household, cash-flow, farm, crop, remittance, debt, receivable, or planning filters.
3. The backend uses verified versioned datasets and the shared calculation service.
4. The dashboard labels period, currency, units, filter context, calculation availability, and data quality.
5. Only authorised values, counts, charts, and next actions render.

**Alternate and failure paths:**

- A new household or filter with no data receives explanatory empty states rather than fabricated KPIs or zero-filled charts.
- Incomplete or unreliable data produces visible limitations and does not appear confident.
- Failure of one optional panel does not corrupt already verified data; the panel shows a safe retry/error state with correlation ID where applicable.
- A filter or identifier targeting another household follows UC-SEC-001.

**Postconditions and recovery:** Dashboard viewing changes no source facts. Equivalent later report filters can reconcile to the same dataset version.

**Audit and isolation:** Sensitive dashboard access is audited only where policy requires; telemetry and logs contain no prohibited raw financial or personal data.

**Traceability:** FR-DASH-001, FR-DASH-002, FR-AUTHZ-003, FR-DQ-002; US-OWN-010, US-MEM-007, US-VIEW-005; NFR-PERF-003, NFR-RPT-001.

### UC-RPT-001: Generate, preview, and retrieve a secure report

**Actors:** Owner, Administrator, Family Member, or Viewer with explicit report and format permission.

**Preconditions:** Report type, permitted format, filter policy, dataset version, storage, expiry, and download controls are configured.

**Trigger:** The actor requests a PDF, Excel, CSV, preview, or print result.

**Normal flow:**

1. The actor selects report type, period, household-scoped filters, and a permitted format.
2. Before generation, the backend authorises report type, fields, dataset, format, and active household.
3. The reporting service consumes the same verified dataset and calculation outputs used by the equivalent dashboard.
4. The system generates the requested format with safe file naming and temporary storage.
5. PDF output includes required print context; Excel contains valid linked data/charts; CSV contains documented raw tabular columns only.
6. The actor previews, prints, or downloads through an authorised expiring reference.
7. Generation and retrieval are audited, and cleanup follows retention policy.

**Alternate and failure paths:**

- Unauthorised type, format, field, filter, or household requests fail before a file is generated.
- Empty datasets create an honest empty report or prevent generation according to the report design; they never inject sample data.
- Generation timeout/failure leaves no exposed partial file and offers safe retry status.
- Guessed, expired, traversed, cross-household, or already-cleaned download references fail consistently.
- Cancelling before generation creates no file; cancelling a running job follows the approved safe job policy.

**Postconditions and recovery:** A successful file is attributable to one actor, household, dataset version, filter set, and expiry. Equivalent formats reconcile at documented precision.

**Audit and isolation:** Audit generation and download metadata without embedding the report contents. File storage, names, links, logs, and cleanup cannot expose another household.

**Traceability:** FR-RPT-001 to FR-RPT-006, FR-AUTHZ-003; US-OWN-010, US-ADM-007, US-VIEW-006; NFR-SEC-008, NFR-RPT-001 to NFR-RPT-003.

### UC-AI-001: Request a masked Shan AI explanation

**Actors:** User with permission for the selected verified dataset and AI purpose.

**Preconditions:** A permitted verified dataset exists; masking, output schema, language, timeout, retention, and fallback policies are approved.

**Trigger:** The actor asks for a Shan explanation of a permitted result, forecast, or limitation.

**Normal flow:**

1. The backend authorises actor, household, dataset, purpose, and data sufficiency before any external request.
2. The backend selects structured verified facts, estimates, periods, assumptions, uncertainty, and data-quality context.
3. It removes or replaces prohibited personal, contact, address, payment, authentication, secret, reference, and unnecessary free-text fields.
4. The system validates the masked outbound structure, then calls Gemini within bounded timeout and retry policy.
5. The response is structurally and safely validated and cannot replace authoritative backend calculations.
6. The user receives a Shan explanation that distinguishes fact from forecast, identifies missing information, states uncertainty, avoids guarantees, and leaves decisions with the family.
7. Safe metadata about request purpose, model, result, actor, household, and correlation is audited without retaining unmasked payloads.

**Alternate and failure paths:**

- Unauthorised, cross-household, unsupported-purpose, empty, insufficient, or unreliable-data requests are rejected before Gemini is called.
- If masking or outbound validation fails, nothing is transmitted.
- Timeout, rate limit, outage, malformed output, unsafe output, or incompatible schema returns a safe fallback and does not alter source data.
- The user may cancel before transmission; no external call occurs. Cancellation after transmission is reported according to the approved request state.
- AI output cannot create an investment, finance event, scenario decision, or report truth.

**Postconditions and recovery:** Verified source facts remain unchanged. The user can identify that the response is advisory and whether a fallback occurred.

**Audit and isolation:** Outbound payload tests prove prohibited fields are absent. Audit/log records store only safe metadata and remain household-scoped.

**Traceability:** FR-AI-001 to FR-AI-005, FR-DQ-002, FR-REC-001; US-OWN-011, US-ADM-009, US-VIEW-007; NFR-PRIV-002, NFR-PRIV-003, NFR-AI-001 to NFR-AI-003.

## 9. Offline, security, and audit use cases

### UC-OFF-001: Save, queue, synchronise, and resolve offline work

**Actors:** Authorised contributor using a supported device; online backend during synchronisation.

**Preconditions:** The PWA shell was loaded successfully online; the operation and data fields are approved for offline use; the device has an eligible session/local-data state.

**Trigger:** Connectivity is absent, unstable, or lost during a supported write.

**Normal flow:**

1. The cached application shell reopens and clearly displays connection state.
2. The actor creates an approved local draft; the interface distinguishes draft from server-committed data.
3. On submission without connectivity, the system validates what it can locally, assigns duplicate-protection metadata, queues the operation, and shows `Queued`.
4. When connectivity returns, the client revalidates authentication and sends the operation using bounded retry and backoff.
5. The backend rechecks current actor, household, permission, referenced resources, validation, version, and idempotency.
6. A successful commit creates one intended event and the client marks it `Synchronised`.
7. A version conflict shows the affected record and safe choices; unsupported conflicts require online review.

**Alternate and failure paths:**

- Network loss before sending retains one local draft; loss during transfer or after server commit produces one queued/recoverable operation, never silent loss.
- Expired authentication pauses the queue and requires safe reauthentication; it does not loop indefinitely.
- Validation, permission, deactivation, missing-resource, permanent, or cross-household errors stop retry and show a safe failed state.
- A newer server version is never overwritten silently; the item becomes `Conflicted`.
- Duplicate replay returns the original result or explicit duplicate status.
- The actor may cancel an unsent local draft according to local retention policy; cancelling a committed event requires its normal domain correction path.

**Postconditions and recovery:** Every supported write is visibly local, queued, synchronising, synchronised, failed, or conflicted. The server contains zero or one intended committed mutation.

**Audit and isolation:** Only server-accepted operations create normal business audit evidence; policy may record safe denied sync attempts. Local sensitive-data scope, expiry, clearing, and logout follow approved privacy rules.

**Traceability:** FR-PWA-001, FR-OFF-001 to FR-OFF-003, FR-FARM-010; US-OWN-012, US-MEM-008; NFR-OFF-001 to NFR-OFF-005, NFR-REL-006.

### UC-SEC-001: Deny unauthorised and cross-household access

**Actors:** Unauthenticated visitor; authenticated user without the requested permission; user manipulating another household's identifier; deactivated member.

**Preconditions:** A protected operation, record, filter, file, report, aggregate, audit query, or AI target is requested.

**Trigger:** Actor/session/household context is absent or the requested action/resource is outside the actor's current authority.

**Normal flow:**

1. The backend identifies the available actor/session context without trusting client-supplied role or hidden-control state.
2. It validates active membership, selected household, action permission, and ownership of every direct and indirect resource.
3. The request is denied before protected data is returned, changed, aggregated, exported, logged unsafely, or sent to AI.
4. The response uses the approved safe status, stable error code, and correlation ID without confirming that an unauthorised resource exists.
5. A policy-defined safe audit event records the denial without prohibited content.

**Covered attack and error paths:**

- Change a URL or resource identifier to another household.
- Add another household to a list/search filter or pagination cursor.
- Submit create/update/archive/cancel/pay/allocate/invite/role-change requests as a Viewer or over-privileged delegated actor.
- Request another household's dashboard aggregate, report generation, generated file, audit record, forecast, or AI explanation.
- Attempt to mutate calculated totals, report datasets, data-quality state, or AI-prepared verified values.
- Retry a previously permitted queued request after membership deactivation or household-context change.

**Postconditions and recovery:** No protected fact is disclosed or changed. Legitimate access requires an approved membership/permission change or correct household selection, not client manipulation.

**Audit and isolation:** Isolation tests use at least two households and identifier substitution across every repository, endpoint, job, file, aggregate, and external-payload boundary.

**Traceability:** FR-AUTHZ-001 to FR-AUTHZ-006; US-NEG-001 to US-NEG-004; NFR-SEC-001, NFR-SEC-009, NFR-PRIV-002.

### UC-AUD-001: Review safe audit evidence

**Actors:** Owner; Administrator with delegated audit permission; unauthorised roles as denied actors.

**Preconditions:** Policy-required authentication, membership, role, finance, farming, export, forecast, recommendation, or AI actions have occurred.

**Trigger:** An authorised actor investigates an operational, security, or data-correction question.

**Normal flow:**

1. The actor selects permitted time, action, result, actor, resource-type, and correlation filters.
2. The backend authorises the audit capability and scopes the query to the active household.
3. Results show actor, household, action, resource reference, timestamp, correlation ID, result, and approved safe metadata.
4. The actor correlates an action with its business record or operational error without altering the audit evidence.
5. Empty results state that no authorised matching evidence exists and do not reveal another household's events.

**Alternate and failure paths:**

- Viewer and unpermitted-member audit requests are denied by the backend.
- Cross-household actor/resource filters return no disclosure and follow the safe denial contract.
- Passwords, tokens, authorisation headers, full payment details, unmasked AI data, and unnecessary raw values never render or appear in logs.
- Failure to load audit evidence changes no business record and returns a correlation ID for support.

**Postconditions and recovery:** Audit evidence remains immutable according to policy; review itself may be audited when required.

**Audit and isolation:** Audit access is itself household-scoped and permission-controlled. Retention and export, if later permitted, follow privacy and report policies.

**Traceability:** FR-AUD-001, FR-AUD-002, FR-AUTHZ-003; US-ADM-008; NFR-COR-006, NFR-PRIV-002, NFR-OBS-001, NFR-OBS-002.

## 10. Acceptance and validation matrix

| Acceptance concern | Covered by | Required future validation |
| --- | --- | --- |
| Authentication and household context | UC-IAM-001 | Lifecycle, token rotation, deactivation, and multi-household tests |
| Unauthorised and cross-household paths | Every protected use case; UC-SEC-001 | Two-household positive/negative isolation matrix |
| Finance and canonical-event correctness | UC-FIN-001, UC-PROFIT-001, UC-FUNDS-001 | Decimal, rollback, idempotency, reconciliation, and reversal fixtures |
| True empty and incomplete-data states | UC-FARM-001, UC-PLAN-001, UC-DASH-001, UC-RPT-001, UC-AI-001 | Empty household and incomplete/unreliable dataset walkthroughs |
| Cancellation and archive | UC-IAM-001, UC-IAM-002, UC-HH-001, UC-FIN-001, UC-FARM-001, UC-FARM-002, UC-RPT-001, UC-AI-001, UC-OFF-001 | Confirmation, rollback/no-partial-state, preservation, and retrieval checks |
| Reporting and secure file access | UC-RPT-001 | Cross-format reconciliation, render/workbook inspection, expiry, traversal, and cross-household tests |
| AI privacy and graceful failure | UC-AI-001 | Masking fixtures, outbound inspection, schema/safety validation, timeout, and fallback tests |
| Offline retry and conflict recovery | UC-OFF-001 | Disconnect-before/during/after-commit, replay, stale-version, deactivation, and queue-state tests |
| Audit event coverage and safe metadata | All use cases; UC-AUD-001 | Event-to-action matrix, correlation, prohibited-field, access, and retention tests |
| Accessibility and Shan-first mobile use | Every user-facing use case | Keyboard, screen-reader, touch, zoom/reflow, translation, and constrained-device checks |

Issue #5 is satisfied by this baseline when every catalogued use case remains traceable, its exceptional paths are reviewable, audit and household-isolation expectations are explicit, and no endpoint contract, schema, wireframe, infrastructure, or application code is introduced.

## 11. Delivery constraint

These use cases are a behavioural specification, not a single implementation backlog. A later implementation issue must select a coherent use-case slice, cite the applicable functional and non-functional requirement IDs, define testable acceptance criteria for normal and negative paths, and remain within its active milestone.
