# F2S GitHub Milestones

## Milestone policy

Use one GitHub milestone per delivery phase. Issues may be moved only when their dependencies and acceptance criteria align with the destination phase. Completing a milestone requires its documentation, tests, and security work, not only visible UI functionality.

## Phase 0 - Foundation and Documentation

**Goal:** establish the repository, decision record, designs, and local/CI foundation needed for safe implementation.

Scope:

- repository and documentation structure;
- project and product requirements;
- functional and non-functional requirements;
- system, database, API, UI/UX, security, reporting, AI, test, and deployment designs;
- initial ADRs;
- local Docker foundation; and
- CI foundation.

Exit condition: implementation issues have traceable requirements and decisions, the local foundation is reproducible, and CI can validate the repository.

## Phase 1 - Authentication and Workspace

**Goal:** establish secure identity, workspace ownership and membership, roles, sessions, recovery, and isolation.

Scope:

- backend authentication;
- frontend login;
- opaque access credentials and rotating server-side refresh sessions;
- password and account lifecycle;
- Admin, Contributor, and Advisor capability policy;
- workspace settings, types, modules, ownership, and member lifecycle;
- one-time bootstrap, activation, recovery, and ownership transfer;
- workspace isolation; and
- audit foundation.

Exit condition: authorised members can access only permitted workspace capabilities, exactly one Active Admin owns each workspace, and automated tests prove authentication, lifecycle, role, restricted-total, approval, and two-workspace isolation behaviour.

## Phase 2 - Household Finance

**Goal:** record and summarise household and farm cash flows accurately.

Scope:

- income and expense records;
- categories;
- household/farm classification;
- filters and date ranges;
- monthly summaries; and
- linked-event rules that prevent double counting.

Exit condition: users can enter and reconcile household finance data with decimal-safe totals and audit history.

## Phase 3 - Farming Investment Foundation

**Goal:** let users explicitly create and manage distinct crop projects.

Scope:

- crop catalogue;
- initially blank Farming Investments page;
- persistent Add Farming Investment action;
- project creation and detail;
- project statuses;
- farming locations; and
- farm-expense linking.

Exit condition: no project is created automatically, initial calculation states are honest, and archive/cancellation preserve history.

## Phase 4 - Harvests, Sales, and Profitability

**Goal:** calculate project profitability from traceable costs, harvests, sales, and payments.

Scope:

- harvest records;
- crop sales;
- payment tracking;
- shared-cost allocation;
- deterministic calculation service;
- profit and loss;
- ROI; and
- break-even calculations.

Exit condition: verified, tested calculations handle missing data, zero denominators, partial payments, and decimal precision.

## Phase 5 - Crop Analytics and Investment Planning

**Goal:** compare historical projects and prepare transparent next-season scenarios.

Scope:

- multi-year comparisons;
- crop performance indicators;
- data-quality rules;
- Conservative, Expected, and Optimistic scenarios;
- recommendation rules;
- next-season investment planning; and
- crop-analysis APIs.

Exit condition: every forecast and recommendation exposes inputs, assumptions, quality, reasons, and uncertainty.

## Phase 6 - Remittances, Debts, and Receivables

**Goal:** make external funds and obligations understandable without double counting.

Scope:

- remittance and allocation tracking;
- debt management;
- repayment tracking; and
- crop-sale and household receivables.

Exit condition: balances and allocations reconcile to their underlying events and remain workspace-isolated.

## Phase 7 - Dashboard

**Goal:** present verified financial and farming information clearly to non-technical users.

Scope:

- KPI cards;
- household financial graphs;
- farming-investment graphs;
- crop comparison graphs;
- forecast graphs; and
- filters.

Exit condition: dashboard values share backend sources with reports and show honest empty/data-quality states.

## Phase 8 - Reports and Exports

**Goal:** provide secure, printable, downloadable records and analysis.

Scope:

- PDF reports and high-resolution graphs;
- Excel workbook with native charts;
- CSV exports;
- previews;
- print layouts; and
- download history.

Exit condition: exports are authorised, auditable, safe, consistent with verified datasets, and usable in the intended formats.

## Phase 9 - AI Adviser

**Goal:** explain verified workspace financial and farming analysis cautiously in Shan.

Scope:

- verified summary service;
- sensitive-data masking;
- backend-only Gemini integration;
- structured request/response validation;
- Shan-language explanations;
- AI chat; and
- optional AI report summaries.

Exit condition: AI receives only necessary masked data, never originates calculations, exposes uncertainty, and is safely audited.

## Phase 10 - PWA and Offline Support

**Goal:** improve usability under unstable or unavailable connectivity.

Scope:

- PWA installation;
- service worker and cached application shell;
- offline drafts;
- queued entries;
- synchronisation;
- connection and retry states; and
- documented conflict handling.

Exit condition: offline work cannot silently overwrite financial data or create duplicate submissions.

## Phase 11 - Production Deployment

**Goal:** operate F2S securely and reliably in production.

Scope:

- Hetzner VPS;
- production Docker Compose;
- Nginx and HTTPS;
- protected database backups;
- monitoring and structured logs;
- security hardening; and
- operations and recovery runbooks.

Exit condition: deployment, restore, monitoring, security, and incident procedures are verified, and the application does not rely on inactivity-sleep hosting.
