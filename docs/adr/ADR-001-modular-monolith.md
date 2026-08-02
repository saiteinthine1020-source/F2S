# ADR-001: Use a Modular Monolith

- **Status:** Accepted
- **Date:** 2026-07-27
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 0 - Foundation and Documentation

## Context

F2S will manage household finances, farming investments, harvests, crop sales, profitability, forecasts, reports, and AI-assisted explanations. These capabilities have distinct business rules, but they share important consistency and security requirements:

- every protected record belongs to an authorised household;
- financial calculations must use one deterministic source of truth;
- transactions may cross related finance and farming records;
- reports and AI explanations must consume the same verified datasets; and
- the initial product will be operated by a small team for one farming household.

Deploying each capability as a separate service would add network failure modes, distributed transactions, duplicated operational tooling, and a larger security surface before those costs are justified. An unstructured single application would be simpler initially but would allow domain rules and dependencies to become tightly coupled.

## Decision

F2S will begin as a **modular monolith**: one backend deployable unit containing explicit domain modules with controlled dependencies.

The backend will keep the following concerns separate even though they run in one process:

- authentication and users;
- households and membership;
- household finance;
- farming investments;
- harvests and crop sales;
- crop analytics and forecasting;
- remittances, debts, and receivables;
- reporting and exports;
- audit and security support; and
- AI integration.

Each domain module will own its application rules and persistence-facing abstractions. API routes, domain services, calculation services, persistence, reporting, and external integrations will not be mixed into one undifferentiated layer.

## Dependency rules

- Requests enter through versioned API routes and call application or domain services.
- Domain logic does not depend on HTTP, UI, report-rendering, or Gemini client code.
- Financial calculations live in backend calculation services and are reused by APIs, dashboards, reports, forecasts, and AI-data preparation.
- Household authorisation is enforced at backend boundaries and in data-access paths; frontend filtering is never treated as an access control.
- Reporting and AI modules consume verified application outputs instead of querying or recalculating business data independently.
- External services are accessed through explicit adapters so failures do not corrupt core records.
- Cross-module access uses documented service contracts rather than imports from another module's internal implementation.
- Circular module dependencies are prohibited.

## Data and transaction boundary

The modular monolith will use one PostgreSQL database initially. Tables remain logically owned by their domain modules. A single application transaction may preserve consistency across related modules where a business operation requires it.

Database choice, numeric precision, household-isolation constraints, and detailed schema design require their own ADRs and design documents before implementation. This decision does not approve a schema or application scaffold.

## Deployment boundary

The backend is built and deployed as one service. The frontend, PostgreSQL database, reverse proxy, background processing if later required, and external providers remain separate runtime concerns. Internal module boundaries must not be presented as independently deployable microservices.

## Consequences

### Positive

- Core financial operations can use ordinary database transactions.
- Local development, testing, deployment, backup, and monitoring remain manageable for a small team.
- Shared security and observability controls can be applied consistently.
- Explicit modules preserve a path to future extraction if scale or ownership boundaries justify it.

### Negative

- Poorly enforced boundaries could degrade into a tightly coupled monolith.
- One backend deployment can affect all backend modules.
- Modules share process and database capacity, so resource-heavy reporting or AI preparation must be isolated carefully.
- Independent module deployment is not available initially.

## Boundary enforcement

Before backend implementation begins, the system architecture and test strategy must define how module boundaries are checked. Reviews must reject direct access to another module's internal persistence or domain implementation. Any proposed exception requires an explicit architecture decision.

## Alternatives considered

### Microservices from the beginning

Rejected for the initial product because operational complexity, distributed consistency, service authentication, observability, and deployment overhead exceed the present scale and team needs.

### Unlayered monolith

Rejected because it would not protect household isolation, calculation ownership, reporting consistency, or future maintainability adequately.

### Serverless functions as the primary backend

Rejected as the initial architecture because fragmented execution and platform-specific coordination would complicate transactional workflows, report generation, and consistent domain boundaries.

## Revisit conditions

This decision should be reviewed if measured evidence shows that a module needs independent scaling, deployment, availability, data ownership, or team ownership. Extraction requires a new ADR and must preserve household isolation, auditability, calculation consistency, and reliable data migration.

## Scope note

This ADR records an architecture direction only. It adds no frontend or backend application code.
