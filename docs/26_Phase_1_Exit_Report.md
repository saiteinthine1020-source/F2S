# Phase 1 Exit Report

## Decision scope

Issue #59 evaluates whether the Authentication and Workspace milestone is ready to hand off to
Phase 2 development. It does not approve production deployment. The decision applies only to
the exact commit whose local and CI commands complete successfully.

## Exit-gate evidence

| Gate | Evidence | Disposition |
| --- | --- | --- |
| Protected-path isolation | Canonical two-workspace fixture plus workspace, settings, member, ownership, audit, session, activation, and recovery repository/API suites | Required; pass only when PostgreSQL CI succeeds |
| Owner and lifecycle invariants | Database constraints, concurrent bootstrap, membership transitions, activation/recovery/session replay, and atomic ownership-transfer suites | Required; pass only when PostgreSQL CI succeeds |
| Role contracts | Backend capability table and direct-request denial; frontend Admin boundary and role-safe navigation | Required; automated evidence exists |
| Migrations | Clean upgrade/downgrade and incremental upgrade from the identity foundation | Required; PostgreSQL CI executes both |
| Frontend | Component, accessibility, localization, session lifecycle, browser keyboard/reflow and critical identity flows | Required; frontend CI executes all |
| Static and supply chain | Ruff, mypy, ESLint, TypeScript, locked installs, repository policy, container build, Markdown/links, full-history Gitleaks | Required; repository workflow executes all |
| Traceability | [Phase 1 Test Traceability](25_Phase_1_Traceability.md) | Required; reviewed with this report |
| High/Critical defects | No known unresolved Phase 1 High or Critical defect at report preparation | Recheck issue and scan results before merge |

## Reproduction commands

```powershell
# Repository root
./infrastructure/scripts/validate-repository.ps1
docker compose --env-file .env.example config --quiet

# backend/
uv sync --frozen --all-groups
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy app tests
uv run --frozen pytest

# frontend/
pnpm install --frozen-lockfile --strict-peer-dependencies
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm exec playwright install chromium
pnpm test:e2e
pnpm build
```

Local backend runs without `F2S_RUN_POSTGRES_TESTS=1` report PostgreSQL cases as `SKIPPED`, not
passed. The required GitHub backend job supplies PostgreSQL 18.4 and enables those cases.

## Explicit deferrals

- Phase 2 financial events, totals, approval records, and their isolation matrix.
- Later-phase farms, reports/files, background processing, AI preparation, caches, and offline
  synchronization, including the protected-path evidence for each when implemented.
- Production distributed abuse-control storage and durable notification delivery.
- Production proxy/TLS, dependency/container/dynamic scans, SBOM/provenance, monitoring/alerts,
  performance, backup, and restore evidence.
- Manual Shan linguistic, screen-reader, zoom, contrast, and device review.

These deferrals do not weaken an implemented Phase 1 control. A material Phase 1 defect found
by CI or review blocks milestone exit and receives a focused linked issue.

## Issue #59 local preparation evidence

The following evidence was collected on Windows before publication. CI remains authoritative
for the disposable PostgreSQL, locked clean-install, container, Markdown/link, and secret-scan
gates.

| Command | Result |
| --- | --- |
| Backend Ruff format and lint | `PASSED`; 111 files formatted, no lint errors |
| Backend mypy | `PASSED`; 107 source files checked |
| Backend pytest | `PASSED` for 127 tests; 37 PostgreSQL tests `SKIPPED` locally |
| Frontend ESLint and TypeScript | `PASSED` using the existing locked local modules |
| Frontend Vitest | `PASSED`; 12 files and 41 tests |
| Frontend Playwright | Seven Chromium scenarios executed, but the local runner did not terminate; result recorded as `ERROR`, not passed |
| Repository policy | `PASSED` through the checked-in PowerShell validator |
| Docker Compose | `NOT RUN`; Docker is unavailable in this shell |
| Locked frontend install/format | `BLOCKED`; bundled pnpm 11.16.0 does not satisfy the repository's exact pnpm 11.20.0 requirement |

The pull-request workflow must resolve every non-passed required row. No skipped, blocked,
errored, or unexecuted local row is counted as milestone evidence.

## Handoff rule

Phase 2 may begin only after the Issue #59 pull request has green required checks, this report
contains the final exact results, review confirms no unresolved High/Critical Phase 1 defect,
and the milestone/project records are closed as Done. Until then the decision is **pending**.
