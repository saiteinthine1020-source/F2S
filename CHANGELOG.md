# Changelog

All notable changes to F2S will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioned application releases will follow [Semantic Versioning](https://semver.org/) when the project reaches a releasable implementation. F2S currently has no application release or version tag.

## [Unreleased]

### Added

- Phase 0 product, functional, architecture, database, API, UI/UX, farming, security, reporting, testing, AI, deployment, operations and recovery documentation.
- Repository milestones, issue plan, governance and initialisation guidance.
- Repository security, contribution, conduct and changelog policies.
- Least-privilege Phase 0 repository validation for Markdown, links, Compose configuration, secret hygiene and prohibited generated files.
- ADR-003 and an initial typed FastAPI modular-monolith skeleton with safe settings, liveness behavior, locked tooling, tests, CI and a non-root local container.
- Phase 1 workspace and identity authority, repository instructions, and ADR-012 through
  ADR-016 covering isolation, ownership, sessions, onboarding, recovery, and module types.

### Security

- Private vulnerability-reporting instructions that prohibit public disclosure of vulnerability details, secrets and workspace data.

### Changed

- Aligned the roadmap, root guidance, secondary designs, and operational documentation with Workspace as the canonical tenant boundary and Admin, Contributor, and Advisor as the Phase 1 roles.

### Licensing

- Confirmed the existing MIT License remains the repository's explicit license pending repository-owner review of any future change.

Unreleased entries describe repository changes only. They must not imply that planned application features, security controls, deployments, backups or tests are implemented.
