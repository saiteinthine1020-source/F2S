# ADR-003: Use FastAPI for the Backend HTTP Boundary

- **Status:** Accepted
- **Date:** 2026-08-05
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1 - Authentication and Household

## Context

F2S needs a typed Python HTTP boundary for its modular monolith. The boundary must support explicit request and response contracts, dependency injection, asynchronous adapters where useful, generated development documentation when deliberately enabled, and straightforward automated testing. It must preserve the rule from [ADR-001](ADR-001-modular-monolith.md) that domain modules do not depend on transport or framework details.

## Decision

F2S will use **FastAPI** as the backend HTTP framework. FastAPI is restricted to the application and HTTP boundary; domain models, domain services, calculations, and module contracts must remain independent of FastAPI.

Pydantic will validate transport schemas and application settings. Pydantic schemas are not domain entities or persistence models. The application will be created through a factory so tests and later deployment wiring can supply validated settings explicitly.

The initial skeleton exposes only an operational liveness endpoint. Interactive API documentation is disabled by default and must remain disabled in production. Authentication, household access, persistence, database readiness, business endpoints, and background processing require their own issues and tests.

## Boundary rules

1. Route handlers translate HTTP input into application commands or queries and translate results into documented responses.
2. Domain and module-contract code must not import FastAPI, route modules, or HTTP-specific exceptions.
3. Cross-module calls use public contracts defined by the owning module, not another module's routes or internals.
4. Settings are validated at startup, use safe defaults, reject unsupported values, and never expose secrets through health responses or logs.
5. Health endpoints report only the capability they actually test. Liveness must not imply database or provider readiness.
6. OpenAPI and interactive documentation are development aids, not substitutes for the approved REST API design or authorisation tests.

## Version and dependency policy

- FastAPI, Pydantic, the ASGI server, test tools, and static-analysis tools are exact direct dependencies in the backend lockfile.
- Python and the dependency installer are pinned for reproducible local and CI execution.
- Dependency upgrades require the format, lint, strict type, configuration, architecture, and health suites to pass.
- Security and compatibility updates follow normal dependency review; this ADR does not permanently freeze a specific release.

## Consequences

### Positive

- Type annotations and Pydantic provide one explicit validation path at the HTTP boundary.
- FastAPI integrates with the approved Python stack and supports isolated application-factory tests.
- Automatic OpenAPI generation can help development while remaining opt-in and disabled in production.
- The small framework surface allows domain modules to stay framework-independent.

### Negative

- Careless use of framework types can couple domain logic to HTTP concerns.
- Generated schemas can appear authoritative even when application and authorisation behavior is incomplete.
- The team must track compatibility across FastAPI, Starlette, Pydantic, the ASGI server, and test clients.
- Async support can add complexity if introduced without an actual I/O or concurrency need.

## Alternatives considered

### Flask

Flask is mature and flexible, but would require more project-specific assembly for typed validation, OpenAPI generation, and dependency wiring without a demonstrated F2S benefit.

### Django and Django REST Framework

They provide a broad application platform, but their ORM- and framework-centred defaults are more extensive than the boundary needed for the approved modular-monolith design.

### Starlette directly

Starlette offers a smaller ASGI layer, but FastAPI adds the approved typed request, response, dependency, and OpenAPI behavior while retaining Starlette's testing and runtime foundation.

## Revisit conditions

Revisit this decision if measured security, maintainability, performance, compatibility, or operational evidence shows that FastAPI cannot meet an approved requirement. A replacement requires a superseding ADR and a migration plan that preserves API contracts and domain independence.

## Scope note

This ADR approves the HTTP framework and boundary rules. It does not approve or implement authentication, household behavior, financial logic, persistence, schemas, migrations, deployment, or any later-phase feature.
