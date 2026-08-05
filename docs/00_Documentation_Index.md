# F2S Documentation Index

## Purpose

This index identifies the authoritative F2S documentation, its delivery phase, and its status. Documentation and engineering content are maintained in English. The initial user interface will be Shan and will use internationalisation from the beginning.

## Status vocabulary

- **Approved:** an accepted decision that guides implementation.
- **Baseline:** the current agreed Phase 0 specification; future issues may refine it.
- **Planned:** required before or during the named phase.

## Authoritative Phase 0 documents

| Document | Purpose | Status |
| --- | --- | --- |
| [Project Overview](01_Project_Overview.md) | Defines the problem, users, scope, principles, architecture direction, and success measures. | Baseline |
| [Product Requirements](02_Product_Requirements.md) | Defines product, functional, data, security, reporting, AI, and delivery requirements. | Baseline |
| [Functional Requirements](03_Functional_Requirements.md) | Defines traceable behaviours, priorities, dependencies, phases, and acceptance outcomes. | Baseline |
| [Non-Functional Requirements](04_Non_Functional_Requirements.md) | Defines measurable quality, security, resilience, accessibility, and operational targets. | Baseline |
| [User Stories](05_User_Stories.md) | Defines role-centred outcomes and negative-authorisation expectations. | Baseline |
| [End-to-End Use Cases](06_Use_Cases.md) | Defines critical normal, alternate, failure, recovery, audit, and isolation workflows. | Baseline |
| [System Architecture](07_System_Architecture.md) | Defines context, containers, module ownership, contracts, dependencies, transactions, and trust boundaries. | Baseline |
| [Database Design](08_Database_Design.md) | Defines the conceptual relational model, ownership, relationships, constraints, indexes, lifecycle, and isolation rules. | Baseline |
| [REST API Design](09_API_Design.md) | Defines versioned resources, methods, formats, authorisation, pagination, idempotency, errors, and compatibility. | Baseline |
| [UI/UX Design](10_UI_UX_Design.md) | Defines Shan-first mobile layouts, navigation, internationalisation, accessibility, forms, and honest interface states. | Baseline |
| [Farming Investment Design](11_Farming_Investment_Design.md) | Defines the core farming-investment concept, empty states, creation flow, calculation states, and lifecycle. | Baseline |
| [AI Design](14_AI_Design.md) | Defines verified-data input, minimisation, masking, provider isolation, response validation, Shan fallback, and safe audit. | Baseline |
| [Security Design](15_Security_Design.md) | Defines assets, trust boundaries, threats, controls, security baselines, privacy limits, and verification. | Baseline |
| [Report and Export Design](16_Report_Export_Design.md) | Defines shared verified datasets, PDF/Excel/CSV behavior, accessible charts, protected artifacts, and cleanup. | Baseline |
| [Test Strategy](17_Test_Strategy.md) | Defines test levels, synthetic fixtures, critical suites, traceability, honest results, milestone gates, and CI policy. | Baseline |
| [Deployment Design](18_Deployment_Design.md) | Defines reproducible local and Hetzner production topology, networks, TLS, PostgreSQL isolation, storage, secrets, health, and recovery boundaries. | Baseline |
| [Operations Runbook](19_Operations_Runbook.md) | Defines monitoring, alert ownership, safe diagnostics, incidents, maintenance, rollback, communication, and tabletop response. | Baseline |
| [Backup and Recovery Design](20_Backup_Recovery.md) | Defines recovery objectives, backup copies/schedules/retention, encryption, restore, reconciliation, drills, and expiry. | Baseline |
| [Data Dictionary](21_Data_Dictionary.md) | Defines canonical business terms, entity and field meanings, states, classifications, currencies, units, and ownership. | Baseline |
| [ADR-001: Use a Modular Monolith](adr/ADR-001-modular-monolith.md) | Records the first architecture decision. | Approved |
| [ADR-002: Use PostgreSQL](adr/ADR-002-use-postgresql.md) | Selects the primary relational database and defines ownership, transaction, privilege, backup, and fitness rules. | Approved |
| [ADR-003: Use FastAPI](adr/ADR-003-use-fastapi.md) | Selects FastAPI for the typed HTTP boundary while preserving framework-independent domain modules. | Approved |
| [ADR-008: Use Decimal-Safe Financial Numeric Storage](adr/ADR-008-safe-financial-numeric-storage.md) | Defines exact numeric types, currency, precision, scale, rounding, allocation, exchange-rate, and zero-denominator rules. | Approved |
| [GitHub Milestones](project_management/GitHub_Milestones.md) | Defines all 12 delivery milestones. | Baseline |
| [First 20 GitHub Issues](project_management/First_20_GitHub_Issues.md) | Proposes the first ordered, independently reviewable issues. | Baseline |
| [Repository Initialisation](project_management/Repository_Initialisation.md) | Provides exact commands for local Git and GitHub initialisation. | Baseline |
| [Repository Governance](project_management/Repository_Governance.md) | Defines issue, label, project, branch, review, merge, and branch-protection rules. | Approved |
| [Continuous Integration](project_management/Continuous_Integration.md) | Defines Phase 0 CI checks, local equivalents, immutable dependencies, failure handling, and branch-protection prerequisites. | Baseline |

## Repository policies

| Policy | Purpose | Status |
| --- | --- | --- |
| [MIT License](../LICENSE) | Grants explicit MIT rights under the existing 2026 copyright notice. | Approved; future changes require owner review |
| [Security Policy](../SECURITY.md) | Defines private vulnerability reporting, coordinated disclosure, response targets, and testing boundaries. | Baseline |
| [Contributing Guide](../CONTRIBUTING.md) | Defines issue-first workflow, privacy, architecture, validation, pull-request, AI-assistance, and licensing expectations. | Baseline |
| [Changelog](../CHANGELOG.md) | Records notable unreleased and future versioned changes without claiming planned features are implemented. | Baseline |
| [Code of Conduct](../CODE_OF_CONDUCT.md) | Defines participation standards, private conduct reporting, enforcement, and appeals. | Baseline |

## Required document roadmap

| Path | Subject | Target |
| --- | --- | --- |
| `docs/12_Crop_Analytics_Design.md` | Historical comparisons and transparent indicators | Phase 5 |
| `docs/13_Forecasting_Design.md` | Deterministic scenarios, assumptions, and uncertainty | Phase 5 |

## ADR roadmap

The following decisions require separate ADRs before their corresponding implementation:

1. ADR-004 Use React and TypeScript
2. ADR-005 Use Hetzner Cloud
3. ADR-006 Use Gemini API
4. ADR-007 Use Backend-Generated Reports
5. ADR-009 Use a PWA for Unstable Connectivity
6. ADR-010 Use XlsxWriter for Excel Reporting
7. ADR-011 Use Deterministic Crop Forecasting
8. ADR-012 Use Household-Level Data Isolation

## Documentation governance

- A document change and its related behaviour change belong in the same issue or pull request.
- Each ADR is immutable after acceptance except for metadata or typo fixes; a new ADR supersedes a decision.
- Requirements use stable identifiers so tests and later designs can trace back to them.
- Examples must never be presented as real household data.
- Empty-state designs must not rely on fabricated totals, investments, or charts.
- Financial formulas must have one backend source of truth and documented rounding rules.
