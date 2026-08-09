# Continuous Integration

## 1. Purpose and scope

Issue #19 established the repository validation baseline, Issue #20 added the backend gates,
and Issue #55 adds the locked frontend gate. CI does not simulate deployment or unimplemented
application behavior.

The executable workflow is `.github/workflows/repository-validation.yml`. It runs for every pull request, every push to `main`, and manual dispatch. Workflow-level `contents: read` is the only `GITHUB_TOKEN` permission.

## 2. Stable checks

| Required check | Responsibility | Failure result |
| --- | --- | --- |
| `Markdown and links` | Lint all tracked Markdown and validate reachable links and fragments | Malformed Markdown or a broken link fails the check |
| `Configuration and repository policy` | Run controlled negative self-tests, reject prohibited tracked artifacts and floating Action tags, prove `.env` is ignored, validate Compose interpolation, and build the backend image | Any policy, Compose, dependency-lock or container-build violation fails the check |
| `Secret scan` | Scan complete Git history with Gitleaks without PR comments or uploaded findings | A detected credential pattern fails the check; findings must be handled privately |
| `Backend static` | Synchronise the lock, check Ruff formatting/lint, and run strict mypy | Formatting, lint, dependency-lock or type violations fail the check |
| `Backend tests` | Run configuration, factory, liveness and architecture tests | Any baseline backend test failure fails the check |
| `Frontend validation` | Install the pnpm lock, check formatting/lint/types, run unit/accessibility tests, and build the production bundle | Any lock, static, test, runtime-config, accessibility-smoke, or build violation fails the check |

Action dependencies are pinned to full commit SHAs. A dependency update must review the upstream release and diff, update the version comment and SHA together, and pass all three checks. Floating major, version or branch references are prohibited.

## 3. Local equivalents

Run from the repository root. A command is `PASS` only when it exits successfully.

```powershell
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File infrastructure/scripts/validate-repository.ps1
npx.cmd --yes markdownlint-cli2@0.22.1 "**/*.md"
lychee --root-dir . --include-fragments --include-mail=false --max-retries 2 --timeout 20 --no-progress "**/*.md"
$env:F2S_POSTGRES_PASSWORD = 'local-ci-validation-not-a-secret'
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example build api
gitleaks git --redact --no-banner
Set-Location backend
uv sync --frozen --all-groups
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy app tests
uv run --frozen pytest
Set-Location ../frontend
pnpm install --frozen-lockfile --strict-peer-dependencies
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
$env:VITE_API_BASE_URL = 'https://api.example.invalid/api/v1'
pnpm build
```

The workflow-pinned `markdownlint-cli2-action` v24.2.0 packages the Markdown tool and `lychee-action` v2.9.0 packages Lychee v0.24.2. Local installations must use equivalent reviewed versions. Never paste a real secret into a negative test, terminal argument, workflow, issue, pull request or log.

On PowerShell 7 or non-Windows systems, use `pwsh -NoProfile -File infrastructure/scripts/validate-repository.ps1` and `npx` instead of the Windows-specific command names.

The repository-policy script always runs controlled in-memory/temporary negative cases. It proves that representative generated paths, `.env`, and a floating Action tag are rejected without adding those artifacts to Git history. Compose's required-password failure can be checked safely by running `docker compose config --quiet` with no `.env` and no `F2S_POSTGRES_PASSWORD`; do not weaken the requirement to make that command pass.

## 4. Branch-protection prerequisites

After the workflow completes successfully on its first pull request:

1. Open the repository ruleset or branch-protection settings for `main`.
2. Require a pull request before merging and block force pushes and deletion.
3. Require the exact checks `Markdown and links`, `Configuration and repository policy`,
   `Secret scan`, `Backend static`, `Backend tests`, and `Frontend validation`.
4. Require the branch to be current with `main` when that policy is operationally acceptable.
5. Do not permit an administrator bypass as the normal merge path; emergency use requires documented review.

A skipped, missing, stale, timed-out or cancelled required check is not a passing result. GitHub configuration remains an owner action and must be verified after merge; this repository change cannot prove that the hosted ruleset is enabled.

## 5. Failure handling

- Fix the source violation; do not disable a rule, add a broad exclusion or regenerate output merely to turn CI green.
- Treat a secret finding as a potential incident. Do not copy the value into an issue or pull request. Follow `SECURITY.md`, revoke/rotate when applicable, and clean history only through a separately reviewed procedure.
- External link failures may be retried by the configured checker. A persistent failure requires repairing or replacing the authoritative link; exclusions require narrow documented justification.
- If a pinned external Action is unavailable or compromised, fail closed and review a replacement. Do not switch to a floating tag.
- Unimplemented feature checks remain `NOT APPLICABLE/NOT RUN` until their owning issues create
  real scaffolds and commands.
