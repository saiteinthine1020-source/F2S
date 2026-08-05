# ADR-015: Use Controlled Bootstrap, Activation, and Recovery Lifecycles

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1

## Context

F2S needs a safe first-Admin flow without enabling unrestricted public registration. Admins
must then create Contributor and Advisor access, and users need activation and recovery
without exposing account existence or credentials.

## Decision

A one-time atomic bootstrap creates the first user, workspace, active Admin membership,
ownership reference, and audit evidence. A serialized database guard permits one winner and
permanently disables ordinary bootstrap after success.

Phase 1 uses normalized email login. Admin-created access starts as a Pending membership and
uses an expiring, random, single-use activation link or code stored only as a digest.
Activation restart invalidates prior credentials. Existing-account handling proves control
without disclosing global identity information.

Recovery uses concealed responses, rate limits, single-use digest-stored credentials,
session revocation, and audit events. Owner recovery requires a separately documented high-
assurance procedure before public launch. Admin-selected passwords are prohibited.

## Consequences

Initial installation and normal member onboarding have explicit, testable boundaries.
Production requires a trusted delivery provider and operational recovery policy. Local
development may use a non-production outbox.

## Rejected alternatives

- Permanent public bootstrap/registration endpoint: enables unauthorized workspace owners.
- Admin-chosen temporary passwords: creates avoidable credential disclosure and reuse risk.
- Revealing whether an email already exists: enables account enumeration.
