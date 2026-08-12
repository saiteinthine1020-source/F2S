# Phase 1 Test Traceability

## Purpose

This matrix maps the implemented Phase 1 requirements, stories, use cases, and accepted ADRs
to executable evidence. It is the release-gate companion to the
[Test Strategy](17_Test_Strategy.md) and does not claim that a skipped or unexecuted suite
passed.

## Executable suites

| Evidence ID | Requirement and product trace | Primary executable evidence |
| --- | --- | --- |
| TST-IAM-001 | FR-IAM-001; US-ADMIN-001; UC-IAM-001; ADR-013; ADR-015 | `test_bootstrap_service.py`, `test_bootstrap_repository.py`, `test_identity_schema.py` |
| TST-IAM-002 | FR-IAM-002; US-CONTRIB-001; US-ADVISOR-001; US-NEG-005; UC-IAM-002; ADR-014; ADR-015 | `test_member_activation_*`, `test_session_*`, `test_account_security_*` |
| TST-IAM-003 | FR-IAM-003; US-ADMIN-003; UC-IAM-003; ADR-013; ADR-015 | `test_member_activation_*`, `test_member_lifecycle_*` |
| TST-IAM-004 | FR-IAM-004; US-ADMIN-003; US-NEG-004; UC-IAM-003; ADR-013 | `test_authorization_policy.py`, `test_member_lifecycle_*`, `test_identity_schema.py` |
| TST-IAM-005 | FR-IAM-005; US-CONTRIB-001; US-ADVISOR-001; UC-IAM-002; ADR-012 | `test_workspace_scope_repository.py`, `test_workspace_settings_*`, frontend auth routing and session tests |
| TST-IAM-006 | FR-IAM-006; US-ADMIN-004; US-NEG-004; UC-IAM-004; ADR-013; ADR-015 | `test_ownership_transfer_*`, frontend administration routing and browser ownership flow |
| TST-WS-001 | FR-WS-001; US-ADMIN-002; UC-WS-001; ADR-016 | `test_workspace_settings_*`, frontend administration API/routing/accessibility tests |
| TST-WS-002 | FR-WS-002; US-ADMIN-002; UC-WS-001; ADR-016 | workspace-settings repository concurrency/audit tests and stale-write frontend test |
| TST-AUTHZ-001 | FR-AUTHZ-001 to FR-AUTHZ-005; US-ADMIN-005; US-NEG-001 to US-NEG-004; UC-SEC-001; ADR-012 | `test_authorization_policy.py`, `test_workspace_scope_repository.py`, all protected repository/API suites, frontend direct-route tests |
| TST-AUTHZ-002 | FR-AUTHZ-003; US-CONTRIB-004; US-NEG-002; ADR-012 | role-safe workspace/member projections, Contributor administration denial, navigation tests |
| TST-AUTHZ-003 | FR-AUTHZ-004; US-NEG-003; ADR-013 | capability decision table, protected APIs, and denied unauthorized Advisor or Contributor requests |
| TST-AUD-001 | FR-AUTHZ-006; FR-AUD-001; FR-AUD-002; UC-AUD-001; ADR-012 to ADR-016 | `test_audit_contracts.py`, `test_audit_repository.py`, required-audit rollback tests in lifecycle repositories |
| TST-SEC-001 | NFR-SEC-001; NFR-SEC-004; NFR-SEC-006; NFR-SEC-007; NFR-SEC-009 | two-workspace repository tests, credential/log redaction, session expiry/reuse, endpoint abuse, production configuration tests |
| TST-A11Y-001 | NFR-A11Y-001 to NFR-A11Y-003; US-CONTRIB-006 | frontend accessibility component suites and `tests/e2e/auth.spec.ts` keyboard/320-pixel flows |
| TST-MNT-001 | NFR-MNT-001; NFR-MNT-002; NFR-MNT-004; NFR-MNT-007 | repository workflow, `test_architecture.py`, this matrix, locked dependency and clean-build commands |

Backend locations are relative to `backend/tests/`; frontend locations are relative to
`frontend/tests/`. The canonical `tests/fixtures/phase_one.py` pack contains two workspaces,
Admin, Contributor, and Advisor roles, every membership state, one actor with different roles
between workspaces, and foreign membership/module identifiers.

## Cross-workspace surface rule

Every currently implemented protected Phase 1 repository/API family has both an authorized
same-workspace path and a concealed foreign, fabricated, inactive, stale, or over-privileged
path in its named suite. Phase 2 financial aggregates, files, reports, background jobs, caches,
and AI payloads do not yet exist; their isolation evidence remains a blocking acceptance
condition for the phase that implements each surface, not a Phase 1 pass claim.

## Manual evidence still required before production

Shan linguistic review, screen-reader/200-percent-zoom review, production dependency and
container scans, dynamic security testing, proxy/TLS verification, production performance,
alerts, and restore drills are production gates. They are not required to begin Phase 2 and are
not reported as completed here.
