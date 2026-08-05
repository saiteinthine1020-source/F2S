# ADR-014: Use Opaque Rotating Server-Side Sessions

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1

## Context

F2S must revoke access after password, account, membership, and ownership security events.
Embedding long-lived authorization facts in self-contained client tokens would complicate
rapid revocation and role changes.

## Decision

F2S uses short-lived opaque access credentials and rotating opaque refresh credentials
backed by server-side session records. Credential digests, not raw values, are persisted.
Refresh rotation detects reuse and revokes the affected session family.

The refresh credential is delivered only in a `Secure`, `HttpOnly`, `SameSite=Strict`,
`Path=/` `__Host-` cookie. State-changing cookie-authenticated requests require the approved
CSRF token and Origin validation. Access credentials are never placed in URLs or logs.

Initial lifetime and Argon2id parameters remain governed by the security design and are
validated against deployment performance before release.

## Consequences

Role and membership changes take effect predictably and sessions can be listed and revoked.
The database and cleanup jobs store additional session state. Availability planning must
account for authentication-state access.

## Rejected alternatives

- Long-lived JWT authorization: stale claims and revocation complexity.
- Browser local storage for refresh credentials: excessive script-exposure risk.
- Non-rotating refresh tokens: weaker replay detection.
