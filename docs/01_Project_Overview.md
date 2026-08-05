# F2S Project Overview

## Product identity

- **Name:** F2S
- **Type:** Mobile-first finance and investment management platform
- **Initial audience:** households, farms, microbusinesses, and combined family operations
- **Initial interface languages:** English, Shan, Myanmar, and Japanese
- **Engineering and documentation language:** English

F2S helps households, farms, and small businesses understand and manage their money
without requiring spreadsheet or accounting expertise.

## Problem

Households, farms, and small businesses may manage unstable income, changing prices,
operating costs, family expenses, debt, receivables, remittances, and several connected
activities. Fragmented records make it difficult to answer basic questions:

- How much money came in and where was it spent?
- What was invested in each crop project?
- Which projects produced profit or loss after all relevant costs?
- How much sale revenue remains unpaid?
- How were remittances allocated?
- What debt remains and what cash is available for the next season?
- Which observations are facts, which are estimates, and what data is missing?

F2S brings these records into workspace-isolated modules and produces transparent
analysis. It supports decisions; it does not make financial decisions for the user.

## Product outcomes

F2S should enable a workspace to:

1. maintain understandable household, farming, and business cash-flow records;
2. track each crop, season, year, location, and planting cycle as a separate farming investment;
3. associate expenses, shared-cost allocations, harvests, sales, and receivables with the correct project;
4. calculate crop profitability and capital recovery using one deterministic backend service;
5. compare completed crop cycles without losing historical context;
6. create next-season scenarios with explicit assumptions and uncertainty;
7. download secure reports with the same verified figures shown in the application; and
8. receive cautious localized explanations after sensitive data is masked.

## Users and roles

The Phase 1 workspace membership model supports exactly these roles:

| Role | Intended capability |
| --- | --- |
| Admin | Sole MVP Workspace Owner; manages workspace settings, members, approvals, official totals, reports, and permitted analysis. |
| Contributor | Creates Pending submissions but cannot receive restricted totals, complete debt/profit data, reports, users, roles, or settings. |
| Advisor | Reads permitted official totals and reports and may comment or flag; cannot create, edit, delete, or approve records. |

Ownership is an invariant attached to exactly one active Admin membership, not a separate
general-purpose role. One account may hold different roles in different workspaces. Backend
authorization enforces workspace isolation and capability rules; frontend filtering is not
a security boundary. The detailed contract is [Workspace and Identity
Foundation](12_Workspace_Identity_Design.md).

## Core capability areas

- Authentication, authorization, workspaces, memberships, ownership, and audit logging
- Household income and expenses
- Crop catalogue and farming investments
- Direct farm costs and auditable shared-cost allocation
- Harvests, crop sales, payments, and linked receivables
- Remittances, allocations, debts, and repayments
- Deterministic financial calculations and data-quality assessment
- Multi-year crop analytics and next-season scenario planning
- Dashboards that handle empty and incomplete data honestly
- Secure PDF, Excel, and CSV reporting
- PWA installation and resilience to unstable connectivity
- Gemini-based explanation of verified, masked data

## Principles and constraints

### Accuracy before AI

AI cannot calculate or originate totals, balances, profit, loss, ROI, margins, break-even values, debt or receivable balances, remittance allocations, or forecasts. It may explain verified results, describe risks, identify missing data, and provide cautious suggestions.

### Honest data states

F2S never creates sample farming investments, fake balances, invented crop performance, misleading zero-filled charts, or recommendations without evidence. A missing result is labelled `Not available`, `Insufficient data`, or another specific state rather than displayed as a completed zero.

### Human responsibility

Forecasts and recommendations include the data period, calculations, assumptions, reasons, data-quality warnings, and uncertainty. The family reviews and makes the final decision. Recommendations never create investments or perform financial actions.

### Security and privacy

Workspace and financial data require least-privilege access, secure authentication, safe
exports, structured audit logging, protected backups, and sensitive-data masking before
Gemini processing. Contributors never receive restricted totals. Secrets remain backend-
only and outside version control.

### Mobile-first access

Primary workflows must be simple, touch-friendly, accessible, internationalisation-ready, and usable on unstable connections. Offline writes must not silently overwrite financial records.

### Incremental engineering

Architecture and product decisions are documented before large implementation changes. Work is delivered one coherent GitHub Issue at a time, with relevant tests and documentation.

## Architecture direction

F2S will use a monorepo and an initial modular-monolith backend. The deployment path is:

```text
React PWA -> HTTPS/Nginx -> FastAPI modular monolith -> PostgreSQL
```

The backend will separate API routes, schemas, domain logic, persistence, repositories, services, calculations, reports, exports, AI, security, and audit responsibilities. The frontend must not maintain a competing implementation of financial formulas.

## Delivery phases

F2S has 12 milestones from Phase 0 through Phase 11. The ordered roadmap is maintained in [GitHub Milestones](project_management/GitHub_Milestones.md).

Phase 0 creates the documentation and repository foundation only. Application functionality begins only after a focused issue is selected and its prerequisite design is ready.

## Success measures

F2S is successful when households, farms, and small businesses can enter their own data,
understand their permitted financial position, see honest warnings for missing or unreliable
data, obtain consistent reports, and use a localized mobile interface under unstable
connectivity. Security, backups, monitoring, auditable approvals, and verified AI
explanations are part of the definition of done, not optional additions.
