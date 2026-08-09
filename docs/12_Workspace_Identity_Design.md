# F2S Workspace and Identity Foundation

## 1. Purpose and authority

This document is the authoritative Phase 1 contract for accounts, workspaces, ownership,
memberships, roles, activation, sessions, recovery, and workspace-scoped authorization.
Where an older document uses Household as the tenant boundary or names Owner,
Administrator, Family Member, or Viewer as current roles, this document supersedes that
wording.

Phase 1 establishes identity and access foundations. It does not implement household,
farming, or business financial records.

## 2. Product and workspace model

F2S helps households, farms, and small businesses understand and manage their money
without requiring spreadsheet or accounting expertise.

A Workspace is the stable security, ownership, membership, configuration, and data-
isolation boundary. Supported workspace types are:

- Household
- Farm
- Microbusiness
- Small Business
- Combined
- Custom

MVP experiences prioritize Household, Farm, Microbusiness, Household plus Farm, and
Household plus Business. A type supplies defaults; explicit module flags describe enabled
capabilities. Changing a name or display type never changes the stable workspace ID or
silently reclassifies historical records.

Required creation fields are name, type, base currency, timezone, and preferred language.
Optional fields are description, logo, address, business category, and farm type. Workspace
renames are audited.

## 3. Account and first-workspace bootstrap

The first person creates an account and the first workspace in one atomic bootstrap flow.
The account collects name, one normalized login identifier, password, preferred language,
and timezone. The workspace collects the required creation fields above.

The bootstrap operation must:

1. be available only while no bootstrap-complete record exists;
2. serialize concurrent attempts with a database lock or equivalent single-winner guard;
3. create the user, workspace, active Admin membership, ownership link, and audit events in
   one transaction;
4. leave no partial user, ownerless workspace, or second owner on failure; and
5. become permanently unavailable after success unless an explicitly audited disaster-
   recovery procedure resets it.

Phase 1 uses email as the login identifier. It is trimmed, Unicode-normalized where
applicable, and compared using a documented case-insensitive canonical form. Username and
phone login are deferred. Public self-registration after bootstrap is not part of Phase 1.

## 4. Ownership and roles

Each workspace has exactly one primary Admin who is also Workspace Owner. The MVP permits
one Admin and any number of Contributors or Advisors. A workspace must never have zero or
more than one owner.

Ownership is stored as an explicit reference to the owner membership. The referenced
membership must belong to the same workspace, be Active, and have the Admin role. The
transactional invariant and database constraints are defined by ADR-013.

| Capability | Admin | Contributor | Advisor |
| --- | --- | --- | --- |
| View official balances and totals | Yes | No | Yes |
| View reports and full profitability/debt data | Yes | No | Yes |
| Create financial submissions | Yes | Yes, Pending | No |
| Edit own Pending submission | Yes | Yes | No |
| Approve or reject submissions | Yes | No | No |
| Comment or flag for review | Yes | No | Yes |
| Manage workspace settings and members | Yes | No | No |
| Transfer ownership | Yes, controlled flow | No | No |
| Delete authoritative records directly | No; correction/reversal rules apply | No | No |

The backend authorizes capabilities rather than trusting client role strings. Contributor
response schemas and queries must omit restricted aggregates rather than returning masked
or zero values.

### 4.1 Implemented authorization and repository boundary

Workspace Access defines the code-level `AuthorizationContext` as an immutable,
server-derived value containing the authenticated account ID, selected workspace ID,
Active membership ID, current role, derived capability set, and correlation ID. Capability
sets are fixed by the matrix above; clients cannot supply or widen them. Repository adapters
revalidate the account, workspace, membership, and persisted role before every protected
operation so constructing or retaining a context object does not create authority.

Every public protected repository method requires this context. Its SQL reads and mutations
include the selected `workspace_id`; global protected find-by-ID methods and post-query
workspace filtering are prohibited. Non-administrative workspace references deliberately
exclude profile administration fields. The separate administration projection and module
mutation require `MANAGE_WORKSPACE_SETTINGS`, so Contributor and Advisor call paths cannot
request those fields or operations.

Known role-capability denial uses the stable `PERMISSION_DENIED` code. Inactive account,
workspace, and membership states have bounded status codes without protected payloads.
Missing, foreign-workspace, fabricated, stale, or role-mismatched authority uses the same
`RESOURCE_NOT_FOUND` outcome and produces no protected mutation. HTTP translation, session
authentication, policy-required audit appends, and public Workspace APIs remain owned by
later Phase 1 issues.

## 5. Account and membership states

Account state and workspace membership state are separate.

Account states:

- Pending Activation
- Active
- Suspended
- Locked
- Closed

Membership states:

- Pending
- Active
- Suspended
- Revoked

Only an Active account with an Active membership can act in a workspace. Suspending an
account affects every membership. Suspending or revoking one membership affects only that
workspace. State changes revoke affected sessions and are audited.

A user may belong to multiple workspaces with a different role and membership state in
each. Identity lookup must not expose the existence of another person's global account.

## 6. Member creation and activation

The Admin can create access for a Contributor or Advisor, view and edit permitted profile
fields, change between those two roles, suspend, reactivate, restart activation, revoke
access, and view safe activity and last-login information.

Member creation produces a Pending membership and a single-use activation challenge. If
the normalized email already belongs to a user, the system attaches the membership only
after that user proves control of the account. Responses to the Admin must not reveal
unrelated global-account information.

Activation credentials are random, high entropy, stored only as digests, expire, are
single-use, and are invalidated when activation is restarted. Email link or code delivery is
preferred. A development outbox may be used outside production.

The initial implementation uses a 24-hour challenge lifetime. Provisioning and restart
persist the digest and lifecycle evidence in the same transaction as the membership/audit
change. The clear value crosses only the delivery port. The process-local development outbox
is test/developer support, not durable delivery; production fails closed until a reviewed
durable adapter is configured. A delivery failure must roll back provisioning or restart so
an unusable current challenge is not committed.

Activation locks the challenge, its same-workspace membership reference, and its account.
Only a Pending Contributor or Advisor membership can become Active. A new Pending Activation
account must set its first password; an already Active account keeps its existing verifier.
An expired challenge becomes Expired, restart makes earlier Issued challenges Revoked, and a
successful challenge becomes Used. Historical challenge rows are retained. Invalid, expired,
revoked, replayed, wrong-workspace, and ineligible-state attempts share one concealed public
failure and bounded audit evidence.

If a temporary-password fallback is later enabled, the password is system-generated,
shown once, hashed immediately, expiring, single-use, and forces password replacement
before any workspace access. An Admin cannot choose, retrieve, or redisplay it.

## 7. Authentication and sessions

Passwords follow `docs/15_Security_Design.md`: Argon2id, minimum length and compromised-
password controls, rate limiting, concealed errors, and no password logging.

F2S uses short-lived opaque access credentials and rotating server-side refresh sessions.
Refresh credentials are held in a Secure, HttpOnly, SameSite cookie and protected by CSRF
and Origin checks. Rotation detects reuse and revokes the affected session family.

Password change, account suspension, membership revocation, ownership transfer, and
security recovery revoke the sessions required by their threat model. The API never places
tokens in URLs or application logs.

## 8. Recovery and ownership transfer

Account recovery must exist before public launch. Recovery responses are indistinguishable
for existing and non-existing accounts. Recovery credentials follow the same digest,
expiry, single-use, rate-limit, and audit requirements as activation credentials.

Ownership transfer is not a role PATCH. It is a dedicated stateful operation:

1. the current owner selects an Active Contributor or Advisor;
2. the current owner completes recent reauthentication and, when configured, an additional
   one-time verification factor;
3. the target confirms using an expiring single-use challenge;
4. one transaction promotes the target to Admin, moves the ownership reference, and moves
   the former owner to the explicitly selected Contributor or Advisor role;
5. both parties are notified and security-relevant sessions are revoked; and
6. initiation, confirmation, cancellation, expiry, and completion are audited.

The transaction locks the workspace and affected memberships and asserts exactly one
active Admin/owner before commit. A failed transfer preserves the original owner.

Owner recovery requires high-assurance proof and an audited support or recovery policy. It
must never create a second owner as a shortcut.

## 9. Approval contract for later financial modules

Contributor-created financial records begin Pending. Pending records may be edited by their
creator within policy and reviewed by the Admin. The Admin may Approve or Reject them. An
Advisor may comment or flag but cannot approve.

Only Approved records affect official balances, dashboards, reports, profitability,
forecasts, exports, or AI datasets. Rejected records remain as historical evidence. An
Approved record is corrected through an auditable correction or reversal flow, not by
silently returning it to Pending.

Phase 1 documents and reserves these states but does not build a generic approval engine.
The first financial-record module implements the shared lifecycle with domain-specific
validation.

## 10. API boundary

Phase 1 route families are:

```text
GET    /api/v1/setup/bootstrap
POST   /api/v1/setup/bootstrap
POST   /api/v1/auth/activate
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/password/change
POST   /api/v1/auth/recovery/request
POST   /api/v1/auth/recovery/confirm
GET    /api/v1/me
GET    /api/v1/me/workspaces
POST   /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}
PATCH  /api/v1/workspaces/{workspace_id}
GET    /api/v1/workspaces/{workspace_id}/members
POST   /api/v1/workspaces/{workspace_id}/members
PATCH  /api/v1/workspaces/{workspace_id}/members/{membership_id}
POST   /api/v1/workspaces/{workspace_id}/members/{membership_id}/reactivate
POST   /api/v1/workspaces/{workspace_id}/members/{membership_id}/activation/restart
DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}
POST   /api/v1/workspaces/{workspace_id}/ownership-transfers
POST   /api/v1/workspaces/{workspace_id}/ownership-transfers/{transfer_id}/confirm
```

Bootstrap, member creation, activation restart, recovery confirmation, and ownership-
transfer confirmation define idempotency behavior. Protected routes derive the acting user
from the credential and validate the requested workspace membership. Client-supplied user,
role, owner, approval, or workspace claims are never authoritative.

API compatibility follows a versioned `/api/v1` contract. Mobile clients send a documented
client version so the service can reject an unsafe obsolete client without weakening API
authorization.

## 11. Web, mobile, PWA, and localization

The Basic dashboard is the only MVP dashboard level. Standard and Advanced dashboards are
future capabilities.

Navigation is capability-driven:

- Admin: Home, Transactions, Add, Reports, More.
- Contributor: submissions/activity, Add, status, and More; no totals or Reports.
- Advisor: Home, Transactions, Reports, review/flag, and More; no Add.

Routes and controls may be hidden when unavailable, but the backend remains authoritative.
Visible text is externalized for English, Shan, Myanmar, and Japanese. User language
overrides workspace language; workspace language overrides the system fallback.

The web app is online-first. Offline drafts are the next offline capability; full offline
conflict-resolving synchronization is deferred. Capacitor is the recommended first native
wrapper, and `com.saiteinthine.f2s` is reserved as the stable application identifier before
store release.

## 12. Audit events

At minimum, Phase 1 records safe events for bootstrap completion; login success/failure;
session creation, rotation, reuse detection, and revocation; password change; recovery
request/completion; workspace creation/rename; member creation, activation, role change,
suspension, reactivation, and revocation; activation restart; ownership-transfer initiation,
confirmation, cancellation, expiry, and completion; and denied cross-workspace access.

Audit records identify actor, workspace when applicable, action, target type and stable ID,
outcome, timestamp, correlation ID, and safe reason code. They never contain passwords,
tokens, one-time codes, full sensitive payloads, or unnecessary personal data.

## 13. Required validation

Phase 1 must prove:

- concurrent bootstrap has one winner and leaves one owner;
- no workspace can be committed or transitioned to zero or two owners;
- ownership transfer is atomic under failure and concurrency;
- a user can hold different roles in two workspaces without privilege carryover;
- every protected repository and API path passes the two-workspace isolation matrix;
- Contributor responses contain no restricted totals or indirect aggregate leakage;
- Advisor mutations and approvals are denied;
- suspended/revoked access invalidates sessions as designed;
- activation, recovery, and transfer credentials expire, are single-use, and resist replay;
- account-enumeration responses remain indistinguishable;
- workspace rename preserves the stable ID and is audited; and
- role-specific UI behavior matches backend capabilities.

## 14. Phase 1 exclusions

Phase 1 excludes financial transaction implementation, a generic approval engine, farming
calculations, reports and exports, the AI adviser, full offline synchronization, native-store
packaging, multiple Admins, custom roles, and advanced organization hierarchies.
