# First 20 F2S GitHub Issues

## Ordering rule

These issues are proposed in dependency order. Each issue is a coherent, reviewable unit and must use the named milestone. Creating the issue does not authorise starting it before its prerequisites are complete.

## 1. `docs: establish the F2S Phase 0 foundation`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** Replace the repository entry point with the authoritative F2S overview, product baseline, Farming Investment design, milestones, issue plan, setup commands, and ADR-001.
- **Acceptance criteria:** all Section 43 documents exist and link correctly; all 12 milestones and 20 issues are defined; no application code is added.
- **Out of scope:** frontend/backend scaffolding and application implementation.

## 2. `docs: define detailed functional requirements and traceability`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** define detailed, uniquely identified functional requirements and map them to product goals, use cases, delivery phases, and verification evidence.
- **Acceptance criteria:** requirements cover all product modules, use stable IDs, identify dependencies and sources, and include a maintained traceability matrix with no unexplained gaps.
- **Out of scope:** API schemas, application implementation, and automated tests.

## 3. `docs: define role-based user stories and acceptance outcomes`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** create role-based user stories and observable acceptance outcomes linked to the functional-requirement identifiers.
- **Acceptance criteria:** stories cover all user roles and product modules, reference applicable requirement IDs, identify dependencies, and map to delivery phases.
- **Out of scope:** API schemas and implementation.

## 4. `docs: define non-functional requirements and quality targets`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** quantify security, performance, availability, accessibility, connectivity, backup, and maintainability expectations.
- **Acceptance criteria:** measurable targets and verification methods are documented; conflicts and assumptions are identified.
- **Out of scope:** infrastructure provisioning.

## 5. `docs: document end-to-end use cases`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** define normal, alternate, error, unauthorised, incomplete-data, and offline paths for critical workflows.
- **Acceptance criteria:** actors, preconditions, steps, postconditions, and failure states are present and traceable.
- **Out of scope:** UI implementation.

## 6. `architecture: document system boundaries and module contracts`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** turn ADR-001 into a component, dependency, transaction, and deployment design.
- **Acceptance criteria:** context/container views, backend module responsibilities, dependency rules, verified-data flows, and failure boundaries are documented.
- **Out of scope:** creating backend packages.

## 7. `architecture: decide PostgreSQL and financial numeric storage`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** record ADR-002 and ADR-008, including money precision, scale, currency handling, and rounding.
- **Acceptance criteria:** alternatives, decision, constraints, migration implications, and formula boundaries are documented.
- **Out of scope:** schema migration files.

## 8. `docs: design the relational data model and dictionary`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** define entities, ownership, relationships, units, timestamps, status fields, archival, and constraints.
- **Acceptance criteria:** every core entity has a workspace-isolation rule; duplicate-event and historical-preservation rules are explicit.
- **Out of scope:** SQLAlchemy models and Alembic migrations.

## 9. `architecture: define REST API conventions and error contract`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** document `/api/v1`, resources, authorisation, pagination, filtering, idempotency, errors, and correlation IDs.
- **Acceptance criteria:** consistent request/response and error examples exist; workspace checks and validation responsibilities are clear.
- **Out of scope:** route implementation.

## 10. `design: define Shan-first mobile UI and accessibility system`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** document navigation, responsive patterns, translation rules, forms, empty/loading/error states, and accessible components.
- **Acceptance criteria:** mobile and desktop flows cover critical modules; no user-facing string is intended to be hardcoded.
- **Out of scope:** React components or visual styling code.

## 11. `security: create threat model and security design`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** model assets, actors, trust boundaries, threats, and layered controls.
- **Acceptance criteria:** authentication, opaque sessions, CSRF/CORS, workspace isolation, roles, ownership, uploads, exports, logging, backups, AI data, headers, and abuse controls are covered.
- **Out of scope:** security-control implementation.

## 12. `testing: define test strategy and quality gates`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** establish test levels, fixtures, isolation tests, calculation matrices, report validation, frontend flows, and CI gates.
- **Acceptance criteria:** required suites map to requirements; test-data privacy and deterministic execution are addressed.
- **Out of scope:** product tests before their features exist.

## 13. `reports: design verified datasets and secure exports`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** define shared report datasets, A4 PDFs, Matplotlib graphs, Excel sheets/native charts, CSV, previews, filenames, and download security.
- **Acceptance criteria:** report/dashboard consistency, authorisation, temporary storage, audit, failure fallback, and accessibility are documented.
- **Out of scope:** report-generation code.

## 14. `ai: document verified-data and sensitive-masking design`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** define the backend calculation-to-masking-to-Gemini-to-validation flow.
- **Acceptance criteria:** allowed/prohibited AI roles, masking fields, structured contracts, uncertainty, Shan output, audit safety, and failure handling are documented.
- **Out of scope:** Gemini API calls.

## 15. `devops: define local and production deployment design`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** document local Docker and production Hetzner/Nginx/PostgreSQL topology, secrets, health checks, logs, SSL, and environments.
- **Acceptance criteria:** developer and production boundaries, ports, persistent data, least privilege, and operational assumptions are explicit.
- **Out of scope:** provisioning the production VPS.

## 16. `devops: define backup, recovery, and operations runbooks`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** establish backup scope, encryption/protection, retention, restore tests, recovery objectives, monitoring, alerts, and incident response.
- **Acceptance criteria:** recovery verification and ownership are documented; no untested backup is described as complete.
- **Out of scope:** production scheduling before infrastructure exists.

## 17. `repo: add community, security, and contribution files`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** add `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, and `CODE_OF_CONDUCT.md`, and confirm that the existing `LICENSE` remains appropriate.
- **Acceptance criteria:** reporting, contribution, release, conduct, and existing licensing expectations are internally consistent and linked.
- **Out of scope:** application features.

## 18. `devops: create the local Docker foundation`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** add minimal local service definitions only after deployment and security designs are approved.
- **Acceptance criteria:** configuration validates, secrets use environment placeholders, PostgreSQL is not publicly exposed, and startup/health instructions are documented.
- **Out of scope:** authentication or business modules.

## 19. `ci: add documentation and repository validation`

- **Milestone:** Phase 0 - Foundation and Documentation
- **Goal:** validate Markdown, links, configuration, secret hygiene, and the current repository foundation in GitHub Actions.
- **Acceptance criteria:** CI is reproducible locally where practical, has least permissions, and fails on defined quality violations.
- **Out of scope:** application test jobs before application scaffolds exist.

## 20. `backend: initialise FastAPI modular-monolith skeleton`

- **Milestone:** Phase 1 - Authentication and Workspace
- **Prerequisites:** Issues 3-19 as applicable, especially architecture, API, security, test, and local Docker designs.
- **Goal:** create the smallest typed FastAPI skeleton that demonstrates approved boundaries, settings validation, health behaviour, and test execution.
- **Acceptance criteria:** no business feature is implemented; package boundaries match ADR-001; tests and documented commands pass; no secret is committed.
- **Out of scope:** users, login, workspace records, farming investments, or future-phase functionality.

## Standard issue body

Every issue should include:

- Goal
- Background
- Scope
- Acceptance Criteria
- Out of Scope
- Dependencies
- Security and privacy impact
- Database and API impact
- Required tests
- Documentation impact
