# Audit Event Catalogue

## Purpose and boundary

This catalogue defines the implemented Phase 1 audit vocabulary and evidence-writing
contract. Audit records are investigation evidence, not operational logs or a copy of the
affected record. Query APIs, administration UI, retention automation, and external SIEM
delivery remain deferred. Phase 2 finance codes below are an accepted design contract and
become implemented only with their owning feature issues.

## Evidence contract

Every intent contains one bounded action, module and result, a UUID correlation ID, an actor,
and optional bounded reason, source, context and resource references. PostgreSQL supplies the
timezone-aware occurrence time. Identity events before a workspace exists use `GLOBAL` scope;
events for an established workspace use `WORKSPACE` scope and its stable ID.

User actors always reference an account. A user actor references a membership only for a
workspace-scoped event. System actors carry no account or membership reference. Denied events
never carry a probed resource ID. A denied foreign-workspace attempt is global evidence with
the authenticated account, `WORKSPACE` resource type, `RESOURCE_NOT_FOUND` reason and no
workspace or resource ID.

The audit writer exposes only `append`. Its SQLAlchemy adapter receives the caller's session,
flushes the new row, and never opens or commits a transaction. A required audit failure
therefore rolls back the consequential state change with the caller's transaction.

## Bounded vocabulary

| Field | Implemented values |
| --- | --- |
| Scope | `GLOBAL`, `WORKSPACE` |
| Actor type | `SYSTEM`, `USER` |
| Result | `SUCCEEDED`, `FAILED`, `DENIED` |
| Module | Implemented: `IDENTITY_SECURITY`, `WORKSPACE_ACCESS`; Phase 2 contract: `HOUSEHOLD_FINANCE` |
| Resource type | Implemented: `USER_ACCOUNT`, `SESSION`, `WORKSPACE`, `WORKSPACE_MEMBERSHIP`, `OWNERSHIP_TRANSFER`; Phase 2: `FINANCE_CATEGORY`, `FINANCIAL_EVENT`, `FINANCIAL_EVENT_REVIEW`, `PROTECTED_FILE` |
| Source | `API`, `BACKGROUND_JOB`, `SYSTEM` |
| Context | `BOOTSTRAP`, `AUTHENTICATION`, `ACTIVATION`, `RECOVERY`, `MEMBERSHIP_ADMINISTRATION`, `OWNERSHIP_TRANSFER`, `WORKSPACE_SETTINGS` |
| Safe reason | `INVALID_CREDENTIALS`, `RESOURCE_NOT_FOUND`, `ACCOUNT_INACTIVE`, `MEMBERSHIP_INACTIVE`, `WORKSPACE_INACTIVE`, `PERMISSION_DENIED`, `EXPIRED`, `REPLAY_DETECTED`, `REVOKED`, `VALIDATION_FAILED`, `STALE_VERSION`, `INVALID_STATE_TRANSITION`, `OWNERSHIP_INVARIANT` |

Phase 1 action codes are:

- `BOOTSTRAP_COMPLETED`;
- `LOGIN_SUCCEEDED`, `LOGIN_FAILED`;
- `SESSION_CREATED`, `SESSION_ROTATED`, `SESSION_REUSE_DETECTED`, `SESSION_REVOKED`;
- `PASSWORD_CHANGED`, `RECOVERY_REQUESTED`, `RECOVERY_COMPLETED`;
- `WORKSPACE_CREATED`, `WORKSPACE_RENAMED`, `WORKSPACE_SETTINGS_UPDATED`,
  `WORKSPACE_MODULES_UPDATED`;
- `MEMBER_CREATED`, `MEMBER_ACTIVATED`, `MEMBER_ROLE_CHANGED`, `MEMBER_SUSPENDED`,
  `MEMBER_REACTIVATED`, `MEMBER_REVOKED`, `ACTIVATION_RESTARTED`;
- `OWNERSHIP_TRANSFER_INITIATED`, `OWNERSHIP_TRANSFER_CONFIRMED`,
  `OWNERSHIP_TRANSFER_CANCELLED`, `OWNERSHIP_TRANSFER_EXPIRED`,
  `OWNERSHIP_TRANSFER_COMPLETED`; and
- `CROSS_WORKSPACE_ACCESS_DENIED`.

Adding a code is an intentional contract change with tests and catalogue review. Callers cannot
submit arbitrary strings or metadata dictionaries.

Phase 2 action codes are defined in §10 of the
[Household Finance Design](27_Household_Finance_Design.md). They are not a claim of current
runtime support. Finance audit evidence never stores money, source/payee, reference, notes,
review or decision free text, filenames, file bytes, or before/after copies.

## Correlation and privacy

An absent request correlation ID receives a UUIDv4. A supplied value must be a canonical UUID;
malformed input produces `INVALID_CORRELATION_ID` with a fresh safe correlation ID and never
echoes the input. The same validated/generated UUID flows to safe errors and related evidence.

Audit metadata never accepts passwords, credentials, tokens, one-time codes, headers, raw
request/response payloads, free text, contact details, financial values, or before/after record
copies. A later need for metadata must be represented by a reviewed enum rather than a generic
key/value field.

Ownership-transfer audit events reference only the stable transfer resource after a successful
transition. Denied target, password, proof, replay, and foreign-resource decisions carry no
submitted membership ID, transfer ID, digest, clear confirmation value, email, or role payload.
Session revocation and transfer completion evidence share the request correlation ID and commit
with the owner/membership changes.

## Required evidence

Automated evidence covers field and enum validation, correlation generation/rejection,
prohibited raw-value rejection, actor/scope/reference consistency, concealed denial records,
UTC persistence, global/workspace events, append-only public methods, and atomic commit and
rollback. Operational investigation should search by the safe correlation ID and UTC window;
it must not copy protected values into tickets or support bundles.
