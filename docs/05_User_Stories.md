# F2S User Stories

## 1. Purpose

These stories express the intended F2S outcomes for Owner, Administrator, Family Member, and Viewer roles. They trace to [Functional Requirements](03_Functional_Requirements.md) and the delivery milestones. They do not authorise implementation outside an active GitHub Issue for the named milestone.

## 2. Story convention

Story identifiers use `US-<ROLE>-<NUMBER>` and remain stable after publication.

Each story includes:

- the user outcome;
- mapped functional requirements;
- the earliest delivery milestone; and
- observable acceptance outcomes, including denial behaviour where relevant.

The role labels are:

- `OWN` - Owner;
- `ADM` - Administrator;
- `MEM` - Family Member; and
- `VIEW` - Viewer.

Permission details remain subject to the later security design. “When granted” always means backend-enforced permission within an authorised household.

## 3. Owner stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-OWN-001 | As an Owner, I want to configure my household's identity, currency, timezone, language, units, financial year, and farming locations so records use the family's real context. | FR-HH-001, FR-HH-002 | Phase 1 | Valid settings persist and are audited; consequential changes do not rewrite historical facts; another household cannot view or change them. |
| US-OWN-002 | As an Owner, I want to invite, activate, deactivate, and assign roles to household members so access follows family responsibilities. | FR-IAM-001, FR-IAM-003, FR-IAM-004 | Phase 1 | Only authorised actions succeed; deactivation removes access without deleting history; ownership cannot be transferred accidentally. |
| US-OWN-003 | As an Owner, I want all protected views and actions isolated to my selected household so no family's information is mixed or exposed. | FR-AUTHZ-001 to FR-AUTHZ-006 | Phase 1 | Identifier substitution, list, aggregate, export, and AI-preparation attempts against another household are denied without information leakage. |
| US-OWN-004 | As an Owner, I want to record and reconcile income and expenses so I can understand household and farm cash flow without double counting. | FR-FIN-001 to FR-FIN-006 | Phase 2 | Valid events appear once in filtered totals; invalid negative amounts are rejected; corrections preserve audit history. |
| US-OWN-005 | As an Owner, I want to create crop categories and explicitly create separate farming investments so each crop cycle has an honest history. | FR-FARM-001 to FR-FARM-006 | Phase 3 | Creating a category creates no project; the blank state contains no fake data; one valid submission creates one household-scoped project. |
| US-OWN-006 | As an Owner, I want to control project lifecycle, cancellation, and archive actions so inactive work is organised without erasing linked history. | FR-FARM-007 to FR-FARM-010, FR-DATA-001 | Phase 3 | Valid transitions are audited; cancellation requires a reason; archive preserves retrieval; retries do not duplicate projects. |
| US-OWN-007 | As an Owner, I want project costs, harvests, sales, payments, and profitability calculated from traceable events so I can judge completed crop cycles. | FR-COST-001 to FR-CALC-003 | Phase 4 | Shared allocations reconcile; unpaid revenue is not cash; verified calculations handle precision, units, missing data, and zero denominators. |
| US-OWN-008 | As an Owner, I want to compare crop history and prepare conservative, expected, and optimistic scenarios so next-season decisions show assumptions and uncertainty. | FR-DQ-001 to FR-REC-001 | Phase 5 | Rankings expose reasons and quality; scenarios are deterministic; insufficient history requests assumptions; recommendations perform no transaction. |
| US-OWN-009 | As an Owner, I want to track remittances, debts, repayments, and receivables so external funds and obligations reconcile with cash flow. | FR-REM-001 to FR-RECV-002 | Phase 6 | Allocations and balances reconcile to canonical events; payments count once; sensitive and cross-household records remain protected. |
| US-OWN-010 | As an Owner, I want dashboards and secure reports to use the same verified datasets so on-screen and exported figures agree. | FR-DASH-001, FR-DASH-002, FR-RPT-001 to FR-RPT-006 | Phases 7-8 | Equivalent filters reconcile; empty states are honest; files are authorised, auditable, safely named, and expire according to policy. |
| US-OWN-011 | As an Owner, I want cautious Shan-language AI explanations of verified masked information so I can understand results without exposing unnecessary personal data or surrendering decisions. | FR-AI-001 to FR-AI-005 | Phase 9 | Prohibited fields never leave the backend; facts and forecasts are distinguished; uncertainty is stated; AI cannot originate authoritative totals or execute actions. |
| US-OWN-012 | As an Owner, I want safe access under unstable connectivity so interrupted work does not duplicate or overwrite financial records. | FR-PWA-001, FR-OFF-001 to FR-OFF-003 | Phase 10 | Local, queued, synced, failed, and conflicted states are visible; replay creates one intended change or an explicit conflict. |

## 4. Administrator stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-ADM-001 | As an Administrator, I want to manage members and delegated settings so I can support household operations without taking ownership authority. | FR-IAM-001, FR-IAM-003, FR-IAM-004, FR-HH-001 | Phase 1 | Permitted membership/settings actions succeed and are audited; ownership transfer and above-authority role grants are denied. |
| US-ADM-002 | As an Administrator, I want to record, search, correct, and reconcile authorised household finance events so records remain complete. | FR-FIN-001 to FR-FIN-006 | Phase 2 | Backend permissions govern every action; filters and totals are correct; linked events are not counted twice. |
| US-ADM-003 | As an Administrator, I want to maintain crop categories, projects, locations, and permitted lifecycle states so farming records follow real work. | FR-FARM-001 to FR-FARM-010 | Phase 3 | Actions remain within the household and delegated role; deletion cannot erase linked history; calculations are not manually editable. |
| US-ADM-004 | As an Administrator, I want to record costs, allocations, harvests, sales, and payments so project profitability has complete source data. | FR-COST-001 to FR-CALC-003 | Phase 4 | Invalid allocation, unit, amount, and payment relationships are rejected; affected project totals recalculate from one service. |
| US-ADM-005 | As an Administrator, I want to review data quality, comparisons, scenarios, and recommendation reasons so I can identify missing evidence before family decisions. | FR-DQ-001 to FR-REC-001 | Phase 5 | Quality limitations remain visible; assumptions are explicit; the administrator cannot present estimates as guaranteed facts. |
| US-ADM-006 | As an Administrator, I want to maintain authorised remittances, allocations, debts, repayments, and receivables so balances remain current and auditable. | FR-REM-001 to FR-RECV-002 | Phase 6 | Events reconcile to household finance and do not expose another household or create negative balances silently. |
| US-ADM-007 | As an Administrator, I want to generate authorised dashboards and reports so the household can review and share permitted information safely. | FR-DASH-001 to FR-RPT-006 | Phases 7-8 | Results use verified shared datasets; downloads enforce authorisation, safe paths, audit, and expiry. |
| US-ADM-008 | As an Administrator, I want to view permitted audit evidence so I can investigate operational errors without seeing prohibited secrets. | FR-AUD-001, FR-AUD-002 | Phase 1 onward | Required actions correlate to safe events; passwords, tokens, full payment data, and unmasked AI payloads are absent. |
| US-ADM-009 | As an Administrator, I want to request permitted masked AI explanations so I can communicate verified results while protecting family data. | FR-AI-001 to FR-AI-005 | Phase 9 | The request is authorised and masked; invalid output falls back safely; no AI response mutates records. |

## 5. Family Member stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-MEM-001 | As a Family Member, I want to sign in and see only households and actions granted to me so I can contribute without administrative access. | FR-IAM-002, FR-IAM-005, FR-AUTHZ-001 to FR-AUTHZ-005 | Phase 1 | The member selects only authorised contexts; membership, role, and settings administration is denied unless separately granted. |
| US-MEM-002 | As a Family Member, I want to enter permitted income and expenses with clear validation so daily records are captured accurately. | FR-FIN-001 to FR-FIN-003 | Phase 2 | Valid records are household-scoped and audited; invalid amounts fail without partial data; restricted correction actions are denied. |
| US-MEM-003 | As a Family Member, I want to add permitted farming investments explicitly so a real crop project can be tracked from the field. | FR-FARM-001 to FR-FARM-005, FR-FARM-010 | Phase 3 | A visible Add action starts the flow; category creation alone creates nothing; retries do not duplicate a project. |
| US-MEM-004 | As a Family Member, I want to add permitted expenses, harvests, and crop sales to the correct project so source records reflect field activity. | FR-COST-001, FR-HARV-001, FR-SALE-001, FR-SALE-002 | Phase 4 | Every record checks household/project ownership and compatible units; unpaid sales remain distinct from cash. |
| US-MEM-005 | As a Family Member, I want to see calculation availability and data-quality reasons so I know what information is incomplete. | FR-CALC-003, FR-DQ-001, FR-DQ-002 | Phases 4-5 | Missing and unreliable inputs display specific limits; no zero or graph implies completed analysis falsely. |
| US-MEM-006 | As a Family Member, I want to contribute permitted remittance, repayment, and receivable payments so balances reflect real events. | FR-REM-001, FR-REM-002, FR-DEBT-002, FR-RECV-002 | Phase 6 | The action is denied when permission is absent; permitted events reconcile once and retain attribution. |
| US-MEM-007 | As a Family Member, I want to view permitted dashboards, reports, and explanations so I can understand household and farm progress. | FR-DASH-001, FR-DASH-002, FR-RPT-001, FR-AI-001, FR-AI-004 | Phases 7-9 | Only authorised data appears; empty states remain honest; report/AI access follows separate permissions. |
| US-MEM-008 | As a Family Member, I want drafts and queued entries to show their connection state so I do not repeat an action during poor connectivity. | FR-OFF-001 to FR-OFF-003 | Phase 10 | The interface distinguishes unsent, queued, failed, synced, and conflicted work and never hides a conflict. |
| US-MEM-009 | As a Family Member, I want all primary actions in Shan-first accessible layouts so I can complete field and household tasks on a phone. | FR-UX-001, FR-I18N-001 | Incremental | Labels, focus, touch targets, validation, and translated states are understandable on supported mobile layouts. |

## 6. Viewer stories

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-VIEW-001 | As a Viewer, I want to sign in and view only records explicitly granted to me so I can stay informed without changing household data. | FR-IAM-002, FR-IAM-005, FR-AUTHZ-001 to FR-AUTHZ-005 | Phase 1 | Authorised read requests succeed; create, edit, archive, cancel, membership, and settings actions are denied by the backend. |
| US-VIEW-002 | As a Viewer, I want to read permitted household finance and farming records so I can understand activity without editing source facts. | FR-FIN-004, FR-FARM-005, FR-FARM-006 | Phases 2-3 | Views are household-scoped and read-only; fabricated data and editable calculated outputs are absent. |
| US-VIEW-003 | As a Viewer, I want to see permitted profitability, quality, and comparison results with their periods and limitations so I do not mistake incomplete analysis for fact. | FR-CALC-003, FR-DQ-001, FR-DQ-002, FR-ANL-001 | Phases 4-5 | Results show source period, units, availability, and quality; restricted planning mutations are denied. |
| US-VIEW-004 | As a Viewer, I want to view permitted remittance, debt, and receivable summaries so I can understand obligations without altering balances. | FR-REM-001, FR-DEBT-001, FR-RECV-001 | Phase 6 | Sensitive fields follow masking policy; create and payment operations are denied unless the role changes. |
| US-VIEW-005 | As a Viewer, I want accessible dashboards with honest empty states so I can understand verified household and farm trends. | FR-DASH-001, FR-DASH-002, FR-UX-001 | Phase 7 | Filters remain within granted data; absent data produces explanations rather than fake charts. |
| US-VIEW-006 | As a Viewer, I want to preview or download only reports granted to me so I can use authorised information without accessing another household's files. | FR-RPT-001 to FR-RPT-006 | Phase 8 | Format and filter permissions are enforced; guessed, expired, or cross-household download identifiers fail safely. |
| US-VIEW-007 | As a Viewer, I want to read a permitted Shan AI explanation with uncertainty and data-quality context so I can understand verified results cautiously. | FR-AI-001 to FR-AI-005 | Phase 9 | Access and masking occur before the request; the explanation cannot create data, guarantee outcomes, or expose unmasked details. |

## 7. Negative-authorisation stories

These stories apply to every role and must be included in later use cases and isolation tests.

| ID | User story | Requirement references | Earliest milestone | Acceptance outcomes |
| --- | --- | --- | --- | --- |
| US-NEG-001 | As any authenticated user, I must not access a different household by changing a URL, identifier, filter, export request, or AI target. | FR-AUTHZ-002, FR-AUTHZ-003, FR-AUTHZ-005 | Phase 1 | Every path is denied consistently without confirming that the target exists. |
| US-NEG-002 | As a Viewer, I must not create, update, archive, cancel, allocate, pay, invite, or change roles through a direct request. | FR-AUTHZ-004, role baseline | Phase 1 onward | Backend denial occurs even if a client exposes or fabricates the request. |
| US-NEG-003 | As a Family Member or Administrator, I must not grant permissions above my delegated authority or transfer household ownership. | FR-IAM-004 | Phase 1 | The operation is denied and safely audited. |
| US-NEG-004 | As any user, I must not edit backend-calculated totals, report datasets, data-quality states, or AI-prepared verified values directly. | FR-FARM-006, FR-CALC-001, FR-RPT-002, FR-AI-003 | Phases 3-9 | Direct mutation is unavailable or rejected; values change only from authorised source events and deterministic rules. |
| US-NEG-005 | As any user, I must not permanently delete linked financial or farming history through an ordinary action. | FR-FIN-006, FR-FARM-008, FR-FARM-009, FR-DATA-001 | Phase 2 onward | Only documented archive, cancel, correction, or reversal behaviour is available and audited. |

## 8. Capability coverage

| Capability | Covered stories |
| --- | --- |
| Identity, roles, households, and isolation | US-OWN-001 to US-OWN-003, US-ADM-001, US-MEM-001, US-VIEW-001, US-NEG-001 to US-NEG-003 |
| Household finance | US-OWN-004, US-ADM-002, US-MEM-002, US-VIEW-002 |
| Farming investment foundation | US-OWN-005 to US-OWN-006, US-ADM-003, US-MEM-003, US-VIEW-002 |
| Costs, harvests, sales, and profitability | US-OWN-007, US-ADM-004, US-MEM-004 to US-MEM-005, US-VIEW-003 |
| Analytics and planning | US-OWN-008, US-ADM-005, US-VIEW-003 |
| Remittances, debts, and receivables | US-OWN-009, US-ADM-006, US-MEM-006, US-VIEW-004 |
| Dashboard | US-OWN-010, US-ADM-007, US-MEM-007, US-VIEW-005 |
| Reports and exports | US-OWN-010, US-ADM-007, US-MEM-007, US-VIEW-006 |
| AI adviser | US-OWN-011, US-ADM-009, US-MEM-007, US-VIEW-007 |
| PWA, offline, accessibility, and language | US-OWN-012, US-MEM-008 to US-MEM-009 |
| Audit and historical preservation | US-ADM-008, US-NEG-004 to US-NEG-005 |

## 9. Delivery constraint

These stories define outcomes, not implementation tasks. A story may be implemented only when:

1. its earliest milestone is active;
2. prerequisite designs and ADRs are approved;
3. an issue selects a coherent subset with testable acceptance criteria;
4. household authorisation and negative paths are included; and
5. the pull request traces the behaviour to both story and functional-requirement IDs.

No API schema, database model, UI component, or application code is created by this document.
