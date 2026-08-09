# F2S

F2S is a mobile-first financial management and farm-investment platform for households, farms, microbusinesses, and small businesses. It helps workspace members record reliable financial data, understand crop performance, plan future seasons, and receive cautious AI-assisted explanations without allowing AI to become the source of truth for financial calculations.

Phase 0 foundation work is complete. Phase 1 implementation has begun with the Identity and Workspace Access database foundation. Authentication workflows and finance, farming, reporting, AI, and offline features remain unimplemented.

## Product goals

F2S will help authorised workspace members:

- record household income, expenses, remittances, debts, and receivables;
- create distinct farming investments for specific crops, seasons, years, locations, and planting cycles;
- track direct and shared farm costs, harvests, crop sales, cash received, and outstanding receivables;
- calculate profit, loss, ROI, break-even values, and other financial indicators deterministically;
- compare crop performance across seasons and years;
- prepare conservative, expected, and optimistic next-season scenarios;
- generate secure PDF, Excel, and CSV reports; and
- receive Shan-language AI explanations based only on verified, masked backend data.

Workspace members retain responsibility for every farming and financial decision.

## Product principles

- **Accuracy before AI:** backend calculation services are the only source of truth for financial values.
- **No fake information:** empty states never contain sample investments, invented totals, misleading charts, or automatic recommendations.
- **Workspace isolation:** the backend must enforce access to workspace data across every service, repository, job, file, report, cache, audit query, and AI-preparation path.
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

## Local Docker foundation

The local Compose foundation contains PostgreSQL and the minimal FastAPI skeleton. The API is not connected to PostgreSQL yet and contains no database schema, migration, authentication flow, business feature or sample data.

Prerequisites:

- a maintained Docker Desktop or Docker Engine release; and
- Docker Compose v5.1 or a compatible newer release using the current Compose Specification.

Create the ignored local environment file in PowerShell, then replace the placeholder password with a long, local-only value:

```powershell
Copy-Item .env.example .env
```

Validate and start the service:

```powershell
docker compose config --quiet
docker compose up -d postgres api
docker compose ps
```

`postgres` is healthy when `docker compose ps` reports `healthy`. Run these smoke checks without printing the password:

```powershell
docker compose exec postgres pg_isready --username=f2s_local_owner --dbname=f2s_local
docker compose exec postgres psql --username=f2s_local_owner --dbname=f2s_local --command="SELECT current_database();"
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

If `F2S_POSTGRES_USER` or `F2S_POSTGRES_DB` was changed in `.env`, use those values in the smoke commands. Stop the service while retaining its local data:

```powershell
docker compose down
```

To reset only this Compose project's local PostgreSQL volume, use the following deliberately destructive command. It permanently removes the local database contents:

```powershell
docker compose down --volumes
```

The database and API ports are published only on IPv4 loopback (`127.0.0.1`) for local tools. Both containers join the private `data` network, and the API receives its database settings through separate typed variables rather than a raw connection URL. Production must not publish PostgreSQL on any host interface; see the [Deployment Design](docs/18_Deployment_Design.md) and [Backend README](backend/README.md).

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
- [End-to-End Use Cases](docs/06_Use_Cases.md)
- [System Architecture](docs/07_System_Architecture.md)
- [Database Design](docs/08_Database_Design.md)
- [REST API Design](docs/09_API_Design.md)
- [UI/UX Design](docs/10_UI_UX_Design.md)
- [Farming Investment Design](docs/11_Farming_Investment_Design.md)
- [Workspace and Identity Foundation](docs/12_Workspace_Identity_Design.md)
- [AI Design](docs/14_AI_Design.md)
- [Security Design](docs/15_Security_Design.md)
- [Report and Export Design](docs/16_Report_Export_Design.md)
- [Test Strategy](docs/17_Test_Strategy.md)
- [Deployment Design](docs/18_Deployment_Design.md)
- [Operations Runbook](docs/19_Operations_Runbook.md)
- [Backup and Recovery Design](docs/20_Backup_Recovery.md)
- [Data Dictionary](docs/21_Data_Dictionary.md)
- [ADR-001: Use a Modular Monolith](docs/adr/ADR-001-modular-monolith.md)
- [ADR-002: Use PostgreSQL](docs/adr/ADR-002-use-postgresql.md)
- [ADR-003: Use FastAPI](docs/adr/ADR-003-use-fastapi.md)
- [ADR-008: Use Decimal-Safe Financial Numeric Storage](docs/adr/ADR-008-safe-financial-numeric-storage.md)
- [ADR-012: Use Workspace-Level Data Isolation](docs/adr/ADR-012-workspace-level-data-isolation.md)
- [ADR-013: Separate Workspace Ownership from Membership Roles](docs/adr/ADR-013-workspace-ownership-and-membership.md)
- [ADR-014: Use Opaque Rotating Server-Side Sessions](docs/adr/ADR-014-opaque-server-side-sessions.md)
- [ADR-015: Use Controlled Bootstrap, Activation, and Recovery Lifecycles](docs/adr/ADR-015-bootstrap-activation-and-recovery.md)
- [ADR-016: Model Workspace Type Separately from Enabled Modules](docs/adr/ADR-016-workspace-types-and-modules.md)
- [GitHub Milestones](docs/project_management/GitHub_Milestones.md)
- [First 20 GitHub Issues](docs/project_management/First_20_GitHub_Issues.md)
- [Repository Initialisation](docs/project_management/Repository_Initialisation.md)
- [Repository Governance](docs/project_management/Repository_Governance.md)
- [Continuous Integration](docs/project_management/Continuous_Integration.md)
- [Backend Setup and Boundaries](backend/README.md)

## Repository policies

- [MIT License](LICENSE)
- [Security Policy](SECURITY.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

Security vulnerabilities must not be disclosed in public issues or pull requests. Follow the private reporting process in [SECURITY.md](SECURITY.md).

## Current status and delivery rule

Phase 0 repository and documentation foundations are complete. Issue #41 is the active
documentation gate for Phase 1 workspace and identity work. Application implementation must
not begin until its workspace, role, ownership, bootstrap, session, and module decisions are
consistent across the authoritative documents.

No real workspace, financial, or farming data, secrets, production credentials, or generated dependencies may be committed.
