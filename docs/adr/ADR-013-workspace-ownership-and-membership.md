# ADR-013: Separate Workspace Ownership from Membership Roles

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1

## Context

The previous model used Owner and Administrator as roles. The revised product requires
exactly the roles Admin, Contributor, and Advisor while also requiring exactly one primary
Admin who owns each workspace.

## Decision

Membership role values are `ADMIN`, `CONTRIBUTOR`, and `ADVISOR`. Ownership is an explicit
workspace reference to one membership, not a fourth role. In the MVP, the owner membership
is Active, belongs to the same workspace, and has role `ADMIN`; no other membership may have
role `ADMIN`.

Membership states are `PENDING`, `ACTIVE`, `SUSPENDED`, and `REVOKED`. Account states are
separate. The detailed schema uses a same-workspace ownership foreign key and transaction-
level assertions backed by the strongest practical PostgreSQL uniqueness/check constraints.

Ownership transfer uses a dedicated request and confirmation workflow. It locks the
workspace and affected memberships and atomically moves the owner reference and Admin role.
A generic membership PATCH cannot create, remove, or transfer Admin ownership.

## Consequences

Authorization uses capabilities mapped from a workspace membership. Ownership remains
unambiguous, transfer can be audited, and a future ADR may permit delegated Admins without
changing the meaning of owner. Creation and transfer transactions require careful locking
and invariant tests.

## Rejected alternatives

- Keeping Owner as a fourth role: conflicts with the mandatory role vocabulary.
- Storing only `role = ADMIN`: cannot distinguish ownership if delegated Admins are added.
- Application checks without database constraints: unsafe under concurrency.
