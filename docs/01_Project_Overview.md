# F2S Project Overview

## Product identity

- **Name:** F2S
- **Type:** AI-powered family finance and farm investment management platform
- **Initial audience:** one farming family
- **Initial interface language:** Shan
- **Engineering and documentation language:** English

## Problem

A farming family may receive unstable farm income while managing changing crop prices, rising fertiliser and labour costs, transport disruption, household and education expenses, debt, receivables, and remittances sent from Japan. Financial events are connected, but fragmented records make it difficult to answer basic questions:

- How much money came in and where was it spent?
- What was invested in each crop project?
- Which projects produced profit or loss after all relevant costs?
- How much sale revenue remains unpaid?
- How were remittances allocated?
- What debt remains and what cash is available for the next season?
- Which observations are facts, which are estimates, and what data is missing?

F2S will bring these records into a household-isolated system and produce transparent analysis. It will support decisions; it will not make decisions for the family.

## Product outcomes

F2S should enable the family to:

1. maintain an understandable record of household and farming cash flows;
2. track each crop, season, year, location, and planting cycle as a separate farming investment;
3. associate expenses, shared-cost allocations, harvests, sales, and receivables with the correct project;
4. calculate crop profitability and capital recovery using one deterministic backend service;
5. compare completed crop cycles without losing historical context;
6. create next-season scenarios with explicit assumptions and uncertainty;
7. download secure reports with the same verified figures shown in the application; and
8. receive cautious Shan-language explanations after sensitive data is masked.

## Users and roles

The initial authorisation model supports:

| Role | Intended capability |
| --- | --- |
| Owner | Manage the household, users, roles, settings, all records, reports, and permitted AI analysis. |
| Administrator | Manage most household records and members, generate reports, and view audit information according to policy. |
| Family Member | Create permitted financial and farming records and view authorised household information. |
| Viewer | View permitted records, dashboards, and reports without modifying financial records. |

The model must be capable of later supporting multiple households, farming groups, cooperatives, or organisations. Backend authorisation must enforce household isolation; frontend filtering is not a security boundary.

## Core capability areas

- Authentication, authorisation, households, users, and audit logging
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

Household and financial data require least-privilege access, secure authentication, safe exports, structured audit logging, protected backups, and sensitive-data masking before Gemini processing. Secrets remain backend-only and outside version control.

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

F2S is successful when the family can enter its own data, understand the status and profitability of distinct farming investments, see honest warnings for missing or unreliable data, obtain consistent downloadable reports, and use the Shan interface on mobile under unstable connectivity. Security, backups, monitoring, auditable decisions, and verified AI explanations are part of the definition of done, not optional additions.
