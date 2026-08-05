# ADR-016: Model Workspace Type Separately from Enabled Modules

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1

## Context

F2S serves households, farms, microbusinesses, small businesses, and combined operations.
A single rigid type cannot safely represent combined use or later module evolution.

## Decision

Each workspace stores one type: `HOUSEHOLD`, `FARM`, `MICROBUSINESS`, `SMALL_BUSINESS`,
`COMBINED`, or `CUSTOM`. The type selects onboarding and default module recommendations.
Enabled modules are stored as explicit validated configuration and remain the authoritative
capability input.

Phase 1 persists metadata and configuration only; it does not implement financial modules.
Changing type or module configuration is Admin-only and audited. It cannot delete,
reclassify, or expose historical data silently.

## Consequences

Combined and custom workspaces do not require a growing cross-product of type values.
Configuration validation and migrations must handle module dependencies. Future commercial
entitlements, if any, remain separate from user-selected module configuration.

## Rejected alternatives

- Type alone controls all behavior: too rigid for combined workspaces.
- Arbitrary unvalidated feature flags: unsafe and difficult to migrate.
- Separate tenant models per product type: duplicates identity and isolation logic.
