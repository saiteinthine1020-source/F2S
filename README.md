F2S

F2S is a mobile-first family finance and farm investment management platform for a farming household. It is intended to help a family record reliable financial data, understand crop performance, plan future seasons, and receive cautious AI-assisted explanations without allowing AI to become the source of truth for financial calculations.

This repository is currently in **Phase 0 - Foundation and Documentation**. No frontend or backend application features have been implemented.

## Product goals

F2S will help an authorised household:

- record household income, expenses, remittances, debts, and receivables;
- create distinct farming investments for specific crops, seasons, years, locations, and planting cycles;
- track direct and shared farm costs, harvests, crop sales, cash received, and outstanding receivables;
- calculate profit, loss, ROI, break-even values, and other financial indicators deterministically;
- compare crop performance across seasons and years;
- prepare conservative, expected, and optimistic next-season scenarios;
- generate secure PDF, Excel, and CSV reports; and
- receive Shan-language AI explanations based only on verified, masked backend data.

The family retains responsibility for every farming and financial decision.

## Product principles

- **Accuracy before AI:** backend calculation services are the only source of truth for financial values.
- **No fake information:** empty states never contain sample investments, invented totals, misleading charts, or automatic recommendations.
- **Household isolation:** the backend must enforce access to household data.
- **Security by design:** secrets, financial data, exported files, and AI payloads require protection from the beginning.
- **Mobile-first and resilient:** the Shan-first interface must work well on phones and tolerate unstable connectivity.
- **Evidence over certainty:** forecasts and recommendations must state their period, calculations, assumptions, data quality, reasons, and uncertainty.
- **Incremental delivery:** work proceeds through one coherent GitHub Issue at a time.

## Planned technology

The default stack is:

- React, TypeScript, Vite, Tailwind CSS, TanStack Query, i18next, and PWA support;
- Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic, and pytest;
- PostgreSQL with decimal-safe financial storage;
- Docker, Docker Compose, Nginx, GitHub Actions, and Hetzner Cloud;
- WeasyPrint and Matplotlib for PDF reporting, XlsxWriter for Excel, and the Python CSV library; and
- Google Gemini through a backend-only, masked, structured integration.

Any material change to this stack requires an Architecture Decision Record (ADR).

## Proposed final monorepo structure

The directories below describe the intended end state. Phase 0 does not create application code or placeholder configuration for later phases.

```text
F2S/
|-- .github/
|   |-- ISSUE_TEMPLATE/
|   |-- workflows/
|   `-- pull_request_template.md
|-- backend/
|   |-- app/
|   |-- migrations/
|   |-- tests/
|   |-- Dockerfile
|   |-- pyproject.toml
|   `-- README.md
|-- frontend/
|   |-- public/
|   |-- src/
|   |-- tests/
|   |-- Dockerfile
|   |-- package.json
|   `-- README.md
|-- infrastructure/
|   |-- nginx/
|   |-- scripts/
|   |-- backup/
|   `-- monitoring/
|-- docs/
|   |-- adr/
|   |-- project_management/
|   |-- 00_Documentation_Index.md
|   |-- 01_Project_Overview.md
|   |-- 02_Product_Requirements.md
|   `-- 11_Farming_Investment_Design.md
|-- .env.example
|-- .gitignore
|-- CHANGELOG.md
|-- CODE_OF_CONDUCT.md
|-- CONTRIBUTING.md
|-- docker-compose.yml
|-- LICENSE
|-- README.md
`-- SECURITY.md
```

The backend will start as a modular monolith. Domain logic, calculations, persistence, API routes, reporting, security, audit, and AI integration will remain separated inside that deployable unit.

## Documentation

Start with the [Documentation Index](docs/00_Documentation_Index.md). The Phase 0 source-of-truth set is:

- [Project Overview](docs/01_Project_Overview.md)
- [Product Requirements](docs/02_Product_Requirements.md)
- [Functional Requirements](docs/03_Functional_Requirements.md)
- [Non-Functional Requirements](docs/04_Non_Functional_Requirements.md)
- [User Stories](docs/05_User_Stories.md)
- [Farming Investment Design](docs/11_Farming_Investment_Design.md)
- [ADR-001: Use a Modular Monolith](docs/adr/ADR-001-modular-monolith.md)
- [GitHub Milestones](docs/project_management/GitHub_Milestones.md)
- [First 20 GitHub Issues](docs/project_management/First_20_GitHub_Issues.md)
- [Repository Initialisation](docs/project_management/Repository_Initialisation.md)
- [Repository Governance](docs/project_management/Repository_Governance.md)

## Current status and delivery rule

Phase 0 documentation foundation is the only active scope. The next implementation task must be selected from a GitHub Issue, must preserve the documented architecture, and must not implement a future phase prematurely.

No real household or farming data, secrets, production credentials, or generated dependencies may be committed.
