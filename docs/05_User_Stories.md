# F2S User Stories

## 1. Purpose

These stories express F2S outcomes for the current Admin, Contributor, and Advisor
workspace roles. They trace to the [Functional Requirements](03_Functional_Requirements.md),
the [Workspace and Identity Foundation](12_Workspace_Identity_Design.md), and the delivery
milestones. They do not authorize implementation outside an active issue for the named
milestone.

## 2. Story convention and superseded identifiers

Story identifiers use `US-<ROLE>-<NUMBER>` and remain stable after publication. Each story
includes the user outcome, mapped requirements, earliest delivery milestone, and observable
acceptance outcomes including denial behavior.

Current role prefixes are:

- `ADMIN` — sole MVP Workspace Owner and workspace manager;
- `CONTRIB` — submission creator with restricted financial visibility; and
- `ADVISOR` — read-only reviewer with comment and flag capabilities.

The former `US-OWN-*`, `US-ADM-*`, `US-MEM-*`, and `US-VIEW-*` series are retired by
Issue 41 and are not reused. Those identifiers represented the superseded Owner, Administrator,
Family Member, and Viewer model; they are not current Phase 1 roles.

## 3. Admin stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-ADMIN-001 | As the first Admin, I want to create my account and first workspace in one setup so the workspace starts with a valid owner. | FR-IAM-001, FR-WS-001 | Phase 1 | One concurrent bootstrap wins; user, workspace, Active Admin membership, ownership, and audit evidence commit atomically. |
| US-ADMIN-002 | As an Admin, I want to configure workspace name, type, currency, timezone, language, profile, and modules so the product fits the real operation. | FR-WS-001, FR-WS-002 | Phase 1 | Valid changes retain the stable workspace ID, are audited, and do not rewrite historical facts or expose disabled data. |
| US-ADMIN-003 | As an Admin, I want to create and manage Contributor and Advisor access so membership follows current responsibilities. | FR-IAM-003, FR-IAM-004 | Phase 1 | Create, activation restart, role change, suspension, reactivation, and revocation are authorized and audited; historical attribution remains. |
| US-ADMIN-004 | As an Admin, I want to transfer ownership securely so the workspace never has zero or two owners. | FR-IAM-006 | Phase 1 | Reauthentication and target confirmation are required; success is atomic and failure preserves the original owner. |
| US-ADMIN-005 | As an Admin, I want every protected action isolated to my selected workspace so no other workspace's information is mixed or exposed. | FR-AUTHZ-001 to FR-AUTHZ-006 | Phase 1 | Identifier substitution, lists, aggregates, files, reports, jobs, audit, and AI-preparation attacks are concealed and denied. |
| US-ADMIN-006 | As an Admin, I want to approve or reject Contributor submissions so only reviewed records affect official results. | FR-FIN-007, FR-FIN-008 | Phase 2 | Pending records affect no official dataset; decisions are atomic and audited; rejected history remains. |
| US-ADMIN-007 | As an Admin, I want household, farm, and business financial events to reconcile once so official balances are understandable. | FR-FIN-001 to FR-FIN-010 | Phase 2 | Approved canonical events count once; invalid values fail; corrections and reversals preserve history. |
| US-ADMIN-008 | As an Admin, I want to create and manage farming investments without fabricated data so each real crop cycle has honest results. | FR-FARM-001 to FR-FARM-010 | Phase 3 | Empty states are honest, category creation creates no project, and permitted lifecycle changes preserve history. |
| US-ADMIN-009 | As an Admin, I want verified costs, harvests, sales, profitability, comparisons, and scenarios so decisions expose evidence and uncertainty. | FR-COST-001 to FR-REC-001 | Phases 4-5 | Calculations reconcile, unavailable states are explicit, and scenarios remain estimates that perform no transaction. |
| US-ADMIN-010 | As an Admin, I want remittances, debts, repayments, and receivables to reconcile with cash flow so obligations remain current. | FR-REM-001 to FR-RECV-002 | Phase 6 | Linked events count once, balances cannot become invalid silently, and sensitive data remains workspace-scoped. |
| US-ADMIN-011 | As an Admin, I want Basic dashboards and secure reports to use the same Approved datasets so screen and export values agree. | FR-DASH-001 to FR-DASH-004, FR-RPT-001 to FR-RPT-006 | Phases 7-8 | Equivalent filters reconcile; empty states are honest; generated files are authorized, audited, and expire. |
| US-ADMIN-012 | As an Admin, I want localized AI explanations of verified masked information so I can understand results without exposing unnecessary data. | FR-AI-001 to FR-AI-005, FR-I18N-001 | Phase 9 | Prohibited fields never leave the backend; facts and forecasts are distinct; AI cannot mutate data. |

## 4. Contributor stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-CONTRIB-001 | As a Contributor, I want to activate my account, sign in, and select only my authorized workspaces so I can contribute safely. | FR-IAM-002, FR-IAM-005, FR-AUTHZ-001 | Phase 1 | Activation credentials are single-use; only Active memberships appear; privileges do not carry between workspaces. |
| US-CONTRIB-002 | As a Contributor, I want to submit income and expenses for review so daily activity can be captured without changing official totals immediately. | FR-FIN-001, FR-FIN-002, FR-FIN-007 | Phase 2 | A valid submission is Pending, attributed, and absent from official balances until approved. |
| US-CONTRIB-003 | As a Contributor, I want to edit my eligible Pending submission and see its status so I can correct it before review. | FR-FIN-007, FR-FIN-008 | Phase 2 | Only permitted Pending source fields change; Approved or Rejected facts cannot be silently rewritten. |
| US-CONTRIB-004 | As a Contributor, I want restricted totals and reports omitted so the interface does not reveal information beyond my role. | FR-AUTHZ-003, FR-FIN-009, FR-DASH-004 | Phase 1 onward | Responses, metadata, counts, errors, files, notifications, and caches contain no restricted aggregate. |
| US-CONTRIB-005 | As a Contributor, I want to add permitted farming, harvest, sale, remittance, repayment, or receivable submissions to the correct workspace records. | FR-FARM-001 to FR-FARM-010, FR-COST-001 to FR-RECV-002 | Phases 3-6 | References remain within one workspace, compatible values validate, and approval rules apply where required. |
| US-CONTRIB-006 | As a Contributor, I want localized, accessible mobile forms and explicit connection/submission states so I can work reliably on a phone. | FR-UX-001, FR-I18N-001, FR-OFF-001 to FR-OFF-003 | Incremental | Labels, focus, touch targets, Pending state, local drafts, retry, failure, and conflicts are understandable. |

## 5. Advisor stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-ADVISOR-001 | As an Advisor, I want to activate my account and see only workspaces where I have an Active Advisor membership. | FR-IAM-002, FR-IAM-005, FR-AUTHZ-001 | Phase 1 | Workspace selection is isolated and no membership or privilege is inferred from another workspace. |
| US-ADVISOR-002 | As an Advisor, I want to view permitted Approved transactions, totals, debt, profitability, and quality context so my review uses official evidence. | FR-FIN-010, FR-DQ-001, FR-DQ-002 | Phases 2-5 | Pending and restricted fields are handled by policy; source period, units, availability, and quality are visible. |
| US-ADVISOR-003 | As an Advisor, I want to comment or flag information for review so I can raise concerns without changing source facts. | FR-FIN-010 | Phase 2 | Comments and flags are attributed and audited; they do not approve, reject, or mutate a financial record. |
| US-ADVISOR-004 | As an Advisor, I want to inspect permitted remittance, debt, receivable, dashboard, and report information without changing balances. | FR-REM-001 to FR-RPT-006 | Phases 6-8 | Reads are workspace-scoped; create, payment, approval, member, settings, and ownership actions are denied. |
| US-ADVISOR-005 | As an Advisor, I want honest Basic dashboards and reports so missing data is not presented as a verified zero or fabricated chart. | FR-DASH-001 to FR-DASH-004, FR-RPT-001 to FR-RPT-006 | Phases 7-8 | Permitted Approved datasets reconcile and unavailable states remain explicit. |
| US-ADVISOR-006 | As an Advisor, I want localized masked AI explanations with uncertainty so I can review verified results cautiously. | FR-AI-001 to FR-AI-005, FR-I18N-001 | Phase 9 | Authorization and masking precede the request; AI cannot guarantee outcomes or perform actions. |

## 6. Negative-authorization stories

These stories are mandatory inputs to use cases and isolation tests.

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-NEG-001 | As any authenticated user, I must not access another workspace by changing a URL, identifier, filter, file, report request, job, audit query, or AI target. | FR-AUTHZ-001 to FR-AUTHZ-006 | Phase 1 | Every path is denied consistently without confirming that the target exists. |
| US-NEG-002 | As a Contributor, I must not receive official totals, reports, complete debt/profit data, member administration, roles, settings, or ownership controls. | FR-AUTHZ-003, FR-FIN-009 | Phase 1 onward | Backend contracts omit restricted fields even when a client fabricates a direct request. |
| US-NEG-003 | As an Advisor, I must not create, edit, delete, pay, approve, reject, invite, change roles, or change settings. | FR-AUTHZ-004, FR-FIN-010 | Phase 1 onward | Backend denial occurs independently of client visibility and is audited where policy requires. |
| US-NEG-004 | As an Admin, I must not create a second Admin or remove the sole owner through a generic membership change. | FR-IAM-004, FR-IAM-006 | Phase 1 | Only the dedicated transfer flow can move ownership and exactly one owner remains. |
| US-NEG-005 | As any user, I must not reuse expired, consumed, revoked, or replaced activation, recovery, refresh, or transfer credentials. | FR-IAM-001, FR-IAM-002, FR-IAM-006 | Phase 1 | Replay fails safely, affected sessions are revoked as designed, and secrets are not logged. |
| US-NEG-006 | As any user, I must not edit calculated totals, report datasets, quality states, or AI-prepared verified values directly. | FR-CALC-001, FR-RPT-002, FR-AI-003 | Phases 4-9 | Direct mutation is unavailable; values change only through authorized source facts and deterministic rules. |
| US-NEG-007 | As any user, I must not make a Pending or Rejected record affect an official dataset. | FR-FIN-007, FR-FIN-008 | Phase 2 onward | Reconciliation tests exclude non-Approved records from every official consumer. |
| US-NEG-008 | As any user, I must not permanently delete linked financial or farming history through an ordinary action. | FR-FIN-006, FR-DATA-001 | Phase 2 onward | Only approved archive, cancel, correction, or reversal behavior is available and audited. |

## 7. Capability coverage

| Capability | Covered stories |
| --- | --- |
| Bootstrap, activation, sessions, and workspace selection | US-ADMIN-001, US-CONTRIB-001, US-ADVISOR-001, US-NEG-005 |
| Workspace settings, membership, and ownership | US-ADMIN-002 to US-ADMIN-005, US-NEG-004 |
| Contributor approval and restricted totals | US-ADMIN-006, US-CONTRIB-002 to US-CONTRIB-004, US-NEG-002, US-NEG-007 |
| Advisor read, comment, flag, and mutation denial | US-ADVISOR-002 to US-ADVISOR-004, US-NEG-003 |
| Finance, farming, and funds | US-ADMIN-007 to US-ADMIN-010, US-CONTRIB-005, US-ADVISOR-002 to US-ADVISOR-004 |
| Dashboard, reports, and AI | US-ADMIN-011, US-ADMIN-012, US-ADVISOR-005, US-ADVISOR-006 |
| Isolation and immutable derived values | US-ADMIN-005, US-NEG-001, US-NEG-006, US-NEG-008 |
| Mobile, localization, and connectivity | US-CONTRIB-006, US-ADMIN-012, US-ADVISOR-006 |

## 8. Delivery constraint

These stories define intended outcomes only. They add no account, workspace, membership,
financial record, endpoint, interface, AI integration, PWA behavior, or production resource.
