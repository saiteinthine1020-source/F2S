# F2S Product Requirements

## 1. Purpose and scope

This document defines the product-level baseline for F2S. It covers the intended complete product while preserving phased delivery. It does not authorise implementation outside the active GitHub Issue.

Priority terms are:

- **Must:** required for the relevant milestone to be complete.
- **Should:** expected unless a documented constraint justifies deferral.
- **May:** optional or future-extensible behaviour.

## 2. Product principles

| ID | Requirement | Priority |
| --- | --- | --- |
| PR-001 | Financial calculations must be deterministic and performed by backend services. | Must |
| PR-002 | AI must not originate financial totals, forecasts, or recommendations without verified inputs. | Must |
| PR-003 | The product must not display fabricated household data, sample investments, misleading charts, or placeholder financial results. | Must |
| PR-004 | Recommendations and forecasts must state period, calculations, assumptions, reasons, data quality, and uncertainty. | Must |
| PR-005 | The family must retain final control over farming and financial decisions. | Must |
| PR-006 | The product must be mobile-first, touch-friendly, accessible, and usable with unstable connectivity. | Must |
| PR-007 | Security, workspace isolation, auditability, and privacy must be designed from the start. | Must |
| PR-008 | Only Approved financial records may affect official balances, dashboards, reports, exports, forecasts, or AI datasets. | Must |

## 3. Identity, access, and workspace requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| IAM-001 | One controlled bootstrap must atomically create the first user, first workspace, active Admin membership, sole ownership link, and audit evidence; public self-registration after bootstrap is unavailable in Phase 1. | Must |
| IAM-002 | The system must support activation, login, logout, password change, concealed recovery, account suspension, short-lived access credentials, and refresh-session rotation and revocation. | Must |
| IAM-003 | Passwords must be hashed with Argon2id and follow the approved password and compromised-password policy. | Must |
| IAM-004 | Admin, Contributor, and Advisor must be the only Phase 1 membership roles and their capabilities must be enforced by the backend. | Must |
| IAM-005 | Every protected record and operation must be scoped to an authorised Workspace. | Must |
| IAM-006 | Tests must prove that one workspace cannot access another workspace's records, aggregates, files, reports, jobs, audit results, or AI-preparation data. | Must |
| IAM-007 | Every workspace must have exactly one active Admin who is the Workspace Owner; ownership transfer must be confirmed, audited, and atomic. | Must |
| IAM-008 | Account state and membership state must be separate, and a user may hold different roles in multiple workspaces. | Must |
| IAM-009 | An Admin must be able to create, activate, suspend, reactivate, change Contributor/Advisor roles, restart activation, revoke access, and review safe member activity. | Must |
| IAM-010 | Activation, recovery, and transfer credentials must be random, expiring, single-use, digest-stored, rate-limited, and protected from account enumeration. | Must |
| WS-001 | A workspace must have a stable ID, editable name, type, base currency, timezone, preferred language, members, module configuration, and auditable settings changes. | Must |
| WS-002 | Workspace types must support Household, Farm, Microbusiness, Small Business, Combined, and Custom without changing the isolation boundary. | Must |
| WS-003 | Required creation fields are name, type, base currency, timezone, and preferred language; description, logo, address, business category, and farm type are optional. | Must |
| HH-001 | Superseded by WS-001 and WS-003; household-specific settings remain valid only inside a Household-capable workspace. | Must |
| HH-002 | Superseded by WS-001; base currency remains configurable and initially supports MMK and JPY. | Must |

## 4. Household finance requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FIN-001 | Users must be able to record categorised household and farm income with amount, currency, date, source, payment method, references, and audit metadata. | Must |
| FIN-002 | Users must be able to record categorised household and farm expenses with amount, currency, date, payee, payment method, references, receipt, and audit metadata. | Must |
| FIN-003 | Negative transaction values must be rejected unless a documented adjustment or reversal mechanism applies. | Must |
| FIN-004 | The model must avoid manually duplicating a single financial event across modules. | Must |
| FIN-005 | Money must use a documented decimal-safe storage and rounding strategy; `FLOAT` and `REAL` are prohibited. | Must |
| FIN-006 | Contributor-created financial records must begin Pending and must not affect official calculations before Admin approval. | Must |
| FIN-007 | An Admin must be able to Approve or Reject a Pending submission; rejection must preserve audit history and an Approved record must use a correction or reversal workflow. | Must |
| FIN-008 | A Contributor must not receive official totals, reports, complete debt/profit data, or equivalent restricted aggregates through direct or indirect API responses. | Must |
| FIN-009 | An Advisor may read permitted Approved data and comment or flag for review but must not create, edit, delete, or approve financial records. | Must |

## 5. Farming investment requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FARM-001 | Crop categories and farming investments must be separate concepts. | Must |
| FARM-002 | Users must be able to create, edit, archive, search, and reuse crop categories. | Must |
| FARM-003 | Creating a crop category must never automatically create a farming investment. | Must |
| FARM-004 | A farming investment must represent a distinct crop project for a crop, season, year, location, and planting cycle. | Must |
| FARM-005 | A new household's Farming Investments page must initially be blank and present a clear `Add Farming Investment` action. | Must |
| FARM-006 | The initial creation flow must capture crop category, season, year, location, field size and unit, planting dates, planned budget and currency, status, and notes. | Must |
| FARM-007 | Immediately after creation, actual investment and revenue may be zero, while profit/loss and ROI remain `Not available` and recommendation remains `Insufficient data`. | Must |
| FARM-008 | The system must distinguish planned, active, harvesting, completed, cancelled, and archived states. | Must |
| FARM-009 | Records with linked financial history must not be permanently deleted through a simple user action. | Must |

Detailed behaviour is defined in [Farming Investment Design](11_Farming_Investment_Design.md).

## 6. Costs, harvests, and sales

| ID | Requirement | Priority |
| --- | --- | --- |
| COST-001 | Direct costs must be linked to one farming investment. | Must |
| COST-002 | Shared costs must support documented allocation methods, store the allocation basis, and remain auditable. | Must |
| COST-003 | Percentage allocations must total 100 percent and recalculate affected project totals. | Must |
| HARV-001 | Harvest records must capture quantity, compatible unit, quality, loss, usable quantity, storage, notes, and audit metadata. | Must |
| HARV-002 | The system must calculate total and usable harvest, loss, loss percentage, and yield per field-area unit. | Must |
| SALE-001 | Crop sales must capture quantity, unit price, gross amount, buyer, dates, payment status, cash received, outstanding amount, selling costs, and notes. | Must |
| SALE-002 | Recognised revenue, cash received, and outstanding receivable must remain distinct. | Must |
| SALE-003 | Unpaid sale revenue must not be represented as available cash. | Must |

## 7. Calculation and analysis requirements

The backend calculation service is the single source of truth for:

```text
Total Investment = Direct Crop Costs + Allocated Shared Costs

Net Revenue = Gross Sales Revenue
              - Sales Commission
              - Transportation Costs
              - Packaging Costs
              - Other Selling Costs

Gross Profit = Gross Sales Revenue - Direct Crop Costs
Net Profit = Net Revenue - Total Investment
Profit Margin = Net Profit / Net Revenue * 100
ROI = Net Profit / Total Investment * 100
Capital Recovery Rate = Cash Received / Total Investment * 100
Cost per Production Unit = Total Investment / Usable Production Quantity
Profit per Field-Area Unit = Net Profit / Field Size
```

| ID | Requirement | Priority |
| --- | --- | --- |
| CALC-001 | Calculations must use decimal-safe arithmetic, defined rounding, and safe zero-denominator handling. | Must |
| CALC-002 | Financial formulas must not be duplicated in frontend, route handlers, reports, or AI prompts. | Must |
| CALC-003 | Every formula must have strong unit and boundary test coverage. | Must |
| ANALYTICS-001 | Historical farming investments must support comparison by season, year, location, field size, crop, production, cost, price, profit, and ROI. | Must |
| ANALYTICS-002 | Crop ranking must consider investment, net profit, unpaid sales, shared costs, losses, consistency, and data completeness rather than revenue alone. | Must |
| ANALYTICS-003 | Performance indicators must use transparent, configurable, documented, and tested rules. | Must |
| DQ-001 | Investments must expose a data-quality state: Complete, Mostly complete, Incomplete, or Unreliable. | Must |
| DQ-002 | Poor data quality must visibly limit forecasts and recommendations. | Must |

## 8. Planning and recommendation requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| PLAN-001 | Users must be able to enter budget, crop, field, production, price, cost-change, reserve, investment-limit, risk, note, and assumption inputs for a future season. | Must |
| PLAN-002 | The deterministic backend must produce Conservative, Expected, and Optimistic scenarios. | Must |
| PLAN-003 | Each scenario must expose investment, revenue, profit/loss, ROI, break-even price, pre-harvest cash, funding gap, and assumptions. | Must |
| PLAN-004 | Forecasts must be labelled as estimates and store their assumptions. | Must |
| PLAN-005 | When history is insufficient, the product must request assumptions and communicate the limitation. | Must |
| REC-001 | Recommendation statuses must be based on transparent verified inputs and include reasons. | Must |
| REC-002 | Recommendations must never create investments, execute transactions, guarantee profit, or bypass human review. | Must |

## 9. Remittance, debt, and receivable requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REM-001 | Remittances must record sender/receiver, source and destination amounts/currencies, exchange rate, fee, dates, method, reference, purpose, and notes. | Must |
| REM-002 | Remittance allocation must distinguish household, farm, education, debt, savings, and other uses without double-counting income. | Must |
| DEBT-001 | Debts and repayments must support balances, interest, due dates, purpose, collateral notes, status, and progress. | Must |
| RECV-001 | Receivables and payments must support original/outstanding amounts, dates, status, and links to crop sales where relevant. | Must |

## 10. Dashboard and reporting requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| DASH-001 | The Basic dashboard must present understandable permitted household, business, cash-flow, farm, crop, remittance, debt, receivable, and planning KPIs from Approved data. | Must |
| DASH-002 | When relevant data does not exist, the dashboard must show an explicit empty state and no misleading zero-filled chart. | Must |
| DASH-003 | Basic is the only MVP dashboard level; Standard and Advanced are named future levels and must not be implied by Phase 1. | Must |
| DASH-004 | Contributor experiences must omit restricted totals and reports; Advisor and Admin dashboard access must follow backend capabilities. | Must |
| RPT-001 | Authenticated and authorised users must be able to preview, print, and download filtered PDF, Excel, and CSV reports. | Must |
| RPT-002 | Dashboard and export values must originate from the same verified calculation and report datasets. | Must |
| RPT-003 | PDF output must be A4, print-friendly, grayscale-readable, accessible, backend-generated, and include period, KPIs, tables, graphs, assumptions, warnings, timestamp, and page numbers where relevant. | Must |
| RPT-004 | Excel output must include detailed sheets, summaries, a dashboard, native charts linked to worksheet data, totals, formatting, and useful filters. | Must |
| RPT-005 | CSV output must contain raw tabular data only and use an Excel-compatible UTF-8 encoding where necessary. | Must |
| RPT-006 | Exports must enforce workspace authorization, safe temporary storage, filename sanitization, path-traversal protection, logging, and deletion after use. | Must |

## 11. AI requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| AI-001 | Gemini integration must be backend-only and receive structured data after authentication, authorisation, calculation, data-quality validation, and masking. | Must |
| AI-002 | Personal names, contact details, addresses, bank/payment details, transaction references, authentication data, secrets, and unnecessary descriptions must be removed or replaced before an AI request. | Must |
| AI-003 | AI responses must be structurally validated and distinguish facts from forecasts. | Must |
| AI-004 | AI must state period, assumptions, uncertainty, and missing information and must avoid fabricated values or guaranteed outcomes. | Must |
| AI-005 | The initial AI explanation language must be Shan. | Must |
| AI-006 | AI requests must be safely audited without logging unmasked sensitive payloads. | Must |

## 12. UX, offline, and language requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| UX-001 | Primary flows must have clear titles, visible actions, simple forms, large touch targets, accessible labels, validation, loading, error, empty, and confirmation states. | Must |
| I18N-001 | User-facing text must be externalised from components and localization-ready for English, Shan, Myanmar, and Japanese from the first frontend implementation. | Must |
| OFF-001 | The frontend must be installable as a PWA and cache the application shell. | Must |
| OFF-002 | Recent-data access, offline drafts, queued entry, retry, connection status, and conflict detection should be supported where practical. | Should |
| OFF-003 | Synchronisation must not silently overwrite financial records or create duplicate submissions. | Must |
| OFF-004 | Advanced offline-write conflict resolution must be documented before implementation. | Must |
| MOBILE-001 | Capacitor is the recommended first native wrapper and `com.saiteinthine.f2s` is reserved as the stable application identifier before store release. | Should |
| MOBILE-002 | Mobile clients must send a documented client version and remain compatible with the supported `/api/v1` contract. | Must |

## 13. Security, audit, and data requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| SEC-001 | Production traffic must use HTTPS, restricted CORS, appropriate CSRF protection, secure cookies, rate limits, input validation, output encoding, and secure headers. | Must |
| SEC-002 | The system must prevent SQL injection, XSS, path traversal, unsafe file upload, secret exposure, and public PostgreSQL access. | Must |
| SEC-003 | Logs must exclude passwords, tokens, authorisation headers, API keys, full bank details, and unmasked AI payloads. | Must |
| AUD-001 | Important authentication, user, role, financial, farming, export, forecast, recommendation, and AI actions must create structured audit records. | Must |
| AUD-002 | Audit records must contain actor, workspace, action, resource, timestamp, correlation ID, result, and safe metadata without unnecessary raw financial values. | Must |
| DATA-001 | Core relational data must use UUIDs, foreign keys, constraints, indexes, timezone-aware timestamps, and Alembic migrations. | Must |
| DATA-002 | Historical financial records must not be hard-deleted without documented justification. | Must |

## 14. Testing and delivery requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| TEST-001 | Backend work must include appropriate unit, service, repository, API, authentication, authorisation, isolation, calculation, reporting, AI, and audit tests. | Must |
| TEST-002 | Frontend work must use Vitest, React Testing Library, and Playwright for critical flows. | Must |
| TEST-003 | Test results may be reported as passed only when the commands executed successfully. | Must |
| DEL-001 | Work must address one coherent GitHub Issue and avoid unrelated or premature implementation. | Must |
| DEL-002 | Schema changes must include migrations, models, schemas, tests, and relevant documentation. | Must |
| DEL-003 | Behaviour changes must include validation, error handling, relevant tests, and documentation updates. | Must |

## 15. Phase transition acceptance

The original Phase 0 foundation was complete when:

- the proposed monorepo and Phase 0 status are visible from the root README;
- the required root-level F2S documents and ADR exist;
- all 12 milestones and the first 20 issues are defined;
- exact repository-initialisation commands are documented;
- the Farming Investment design covers all mandatory empty-state and lifecycle rules; and
- no application behavior beyond the separately authorized repository foundation was
  included.

Phase 1 identity and workspace implementation may begin only after the Workspace and
Identity Foundation, ADR-012 through ADR-016, and the existing authoritative documents are
mutually consistent. This document change does not authorize application implementation.
