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
| [User Stories](05_User_Stories.md) | Defines role-centred outcomes and negative-authorisation expectations. | Baseline |
| [Farming Investment Design](11_Farming_Investment_Design.md) | Defines the core farming-investment concept, empty states, creation flow, calculation states, and lifecycle. | Baseline |
| [ADR-001: Use a Modular Monolith](adr/ADR-001-modular-monolith.md) | Records the first architecture decision. | Approved |
| [GitHub Milestones](project_management/GitHub_Milestones.md) | Defines all 12 delivery milestones. | Baseline |
| [First 20 GitHub Issues](project_management/First_20_GitHub_Issues.md) | Proposes the first ordered, independently reviewable issues. | Baseline |
| [Repository Initialisation](project_management/Repository_Initialisation.md) | Provides exact commands for local Git and GitHub initialisation. | Baseline |
| [Repository Governance](project_management/Repository_Governance.md) | Defines issue, label, project, branch, review, merge, and branch-protection rules. | Approved |

## Required document roadmap

| Path | Subject | Target |
| --- | --- | --- |
| `docs/04_Non_Functional_Requirements.md` | Quality, security, accessibility, resilience, and operations requirements | Phase 0 |
| `docs/06_Use_Cases.md` | End-to-end use cases and exception paths | Phase 0 |
| `docs/07_System_Architecture.md` | Component boundaries, data flows, and deployment context | Phase 0 |
| `docs/08_Database_Design.md` | Relational model, isolation rules, constraints, units, and money storage | Phase 0 |
| `docs/09_API_Design.md` | REST conventions, versioning, errors, pagination, and authorisation | Phase 0 |
| `docs/10_UI_UX_Design.md` | Shan-first mobile UX, accessibility, and responsive states | Phase 0 |
| `docs/12_Crop_Analytics_Design.md` | Historical comparisons and transparent indicators | Phase 5 |
| `docs/13_Forecasting_Design.md` | Deterministic scenarios, assumptions, and uncertainty | Phase 5 |
| `docs/14_AI_Design.md` | Verified-data flow, masking, validation, and Shan explanations | Phase 9 |
| `docs/15_Security_Design.md` | Threat model, controls, household isolation, and security testing | Phase 0 |
| `docs/16_Report_Export_Design.md` | PDF, Excel, CSV, print, datasets, and secure download design | Phase 0 |
| `docs/17_Test_Strategy.md` | Test levels, critical suites, fixtures, and quality gates | Phase 0 |
| `docs/18_Deployment_Design.md` | Docker, Nginx, Hetzner, SSL, and delivery topology | Phase 0/11 |
| `docs/19_Operations_Runbook.md` | Production operation and incident procedures | Phase 11 |
| `docs/20_Backup_Recovery.md` | Backup protection, restore, and recovery verification | Phase 11 |
| `docs/21_Data_Dictionary.md` | Canonical business terms, fields, states, units, and formula inputs | Incremental |

## ADR roadmap

The following decisions require separate ADRs before their corresponding implementation:

1. ADR-002 Use PostgreSQL
2. ADR-003 Use FastAPI
3. ADR-004 Use React and TypeScript
4. ADR-005 Use Hetzner Cloud
5. ADR-006 Use Gemini API
6. ADR-007 Use Backend-Generated Reports
7. ADR-008 Use Safe Numeric Financial Storage
8. ADR-009 Use a PWA for Unstable Connectivity
9. ADR-010 Use XlsxWriter for Excel Reporting
10. ADR-011 Use Deterministic Crop Forecasting
11. ADR-012 Use Household-Level Data Isolation

## Documentation governance

- A document change and its related behaviour change belong in the same issue or pull request.
- Each ADR is immutable after acceptance except for metadata or typo fixes; a new ADR supersedes a decision.
- Requirements use stable identifiers so tests and later designs can trace back to them.
- Examples must never be presented as real household data.
- Empty-state designs must not rely on fabricated totals, investments, or charts.
- Financial formulas must have one backend source of truth and documented rounding rules.
