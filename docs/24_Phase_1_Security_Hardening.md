# Phase 1 Security Hardening Evidence

## Purpose

This record maps the Phase 1 browser, API, authentication, configuration, and supply-chain
hardening delivered by Issue #58 to its operational requirements and verification evidence.
It supplements the authoritative [Security Design](15_Security_Design.md); it does not weaken
or replace that design.

## Implemented boundary controls

| Boundary | Implemented control | Verification |
| --- | --- | --- |
| Browser mutations | Bootstrap, member provisioning, activation, session, password, recovery, ownership, member-lifecycle, and workspace-setting mutations require the exact configured `Origin` and `application/json`. Cookie-authorised refresh/logout additionally require the session-bound CSRF value. | API tests cover hostile/missing Origin, form content, missing CSRF, and safe no-side-effect rejection. |
| CORS | One exact frontend origin, credentials enabled, bounded methods/headers, and a 600-second preflight cache. Wildcard origin configuration is rejected. | Configuration and session CORS tests. |
| Refresh cookie | `__Host-f2s_refresh`, `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, and no `Domain`; credential material never appears in a URL or JSON response. | Session API cookie and concealment tests. |
| Host boundary | Requests accept only configured exact API hostnames. Wildcards, schemes, paths, and port-bearing values are rejected. Production rejects local and placeholder hosts. | Configuration and hostile-Host tests. |
| Response protection | API and health responses use `no-store`, deny-by-default API CSP, anti-framing, MIME sniff prevention, no referrer, restricted browser capabilities, and same-origin resource policy. Production adds one-year HSTS. | Liveness, error, and production-configuration tests. |
| Errors | Validation, domain, browser, authentication, authorisation, and unexpected exceptions return bounded structured errors and correlation identifiers without exception text. | Synthetic exception-canary and existing error-contract tests. |
| Abuse control | Login uses progressive keyed account delay and a keyed network window; recovery uses keyed recipient/network windows; activation uses five keyed challenge attempts and 20 network attempts per hour; refresh uses 30 keyed server-side session-family attempts and 120 keyed network attempts per five minutes. | Deterministic unit/API rate-limit tests with safe `429` and `Retry-After`. |
| Runtime identity | The container remains non-root/read-only compatible. Uvicorn server identity and raw access logging are disabled in the production image command. | Dockerfile and Compose configuration review. |

## Production fail-closed configuration

Production startup requires all of the following:

- debug and API documentation disabled;
- PostgreSQL `verify-full` TLS mode;
- one explicit HTTPS frontend origin using a non-local, non-placeholder hostname;
- one through 16 exact non-local API hostnames through `F2S_API_ALLOWED_HOSTS`;
- non-placeholder database and identity-digest secrets; and
- a reviewed distributed abuse-control adapter before login, activation, refresh, or recovery
  can proceed.

`F2S_API_ALLOWED_HOSTS` is a JSON array when supplied as an environment variable, for example
`["api.f2s.example"]`. The reverse proxy must preserve an allowed canonical Host value. Proxy
trust remains disabled by default: do not enable forwarded-header trust until the deployment
defines exact proxy addresses and proves that direct clients cannot spoof them.

## Logging and prohibited-data review

The container command disables Uvicorn access logs because an unreviewed access logger can
copy attacker-controlled URL/query material. Application request and response bodies, raw
paths/queries, cookies, `Authorization`, CSRF headers, passwords, and credential/challenge
values are not logged. Safe structured application logging remains a production-observability
deliverable and may include only the allowlisted fields in Security Design Section 21.

Health output remains exactly `{"status":"ok"}`. Error responses contain a bounded code,
message, and correlation identifier; synthetic exception canaries prove that exception text is
not returned. Audit persistence continues to accept only bounded catalogue fields and digest or
internal identifiers where its contract permits them.

## Verification commands and release evidence

Run these commands from the named directory before merge:

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
```

CI additionally runs Markdown/link validation, complete PostgreSQL tests, the frontend suite,
container build, and full-history Gitleaks scanning. Before a production release, attach results
for dependency/SCA, container, configuration, dynamic browser/API, SBOM, and provenance gates.
Critical or High findings block release unless the security owner records an approved,
time-bounded risk acceptance.

## Detection and alerts

Production monitoring must alert on distributed-counter rejection/unavailability, sustained
`RATE_LIMITED` outcomes, refresh reuse, unexpected 5xx rate, invalid Host/Origin anomalies,
startup configuration rejection, and failed secret/dependency/container scans. Alerts contain
safe correlation and bounded event codes only; they must never copy request data or credentials.

## Residual risks and deferred production gates

- Distributed abuse-control storage is not implemented. Production authentication-related
  endpoints deliberately reject instead of falling back to process-local counters.
- Durable activation, recovery, and ownership notifications remain unavailable in production.
- Exact reverse-proxy trust, edge TLS/header verification, safe structured logging transport,
  dynamic scanning, container scanning, SBOM/provenance, and alert routing require deployment
  evidence before production exposure.
- The final measured rate limits, frontend CSP hashes/nonces, MFA/passkeys, and penetration test
  remain the deferred decisions listed in the Security Design.

These are explicit release blockers or accepted deferrals, not claims of completed production
readiness.
