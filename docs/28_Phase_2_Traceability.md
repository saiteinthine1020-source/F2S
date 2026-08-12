# Phase 2 Household Finance Traceability

## Purpose

This matrix maps the Phase 2 Household Finance requirements to source requirements, stories,
the end-to-end use case, accepted decisions, cross-cutting controls, and required executable
evidence. It is a design contract and does not claim that future tests have passed.

## Requirement matrix

| Requirement | Source and user outcome | Governing contract | Required evidence and owning issues |
| --- | --- | --- | --- |
| FR-FIN-001 | FIN-001, FIN-005; US-ADMIN-007, US-CONTRIB-002; UC-FIN-001 | ADR-008, ADR-012, ADR-018; design §§3-6 | Exact income validation/storage/serialization, role initial state, audit, idempotency, rollback, two-workspace create/read; #78-#83, #96 |
| FR-FIN-002 | FIN-002, FIN-005; US-ADMIN-007, US-CONTRIB-002; UC-FIN-001 | ADR-018; design §§5, 8-10 | Expense/payee fields plus parent/type/size/signature/quarantine/download/removal/isolation receipt matrix; #82, #88, #91, #96 |
| FR-FIN-003 | FIN-003; US-ADMIN-007; UC-FIN-001 invalid path | ADR-008, ADR-018; design §§2-3, 6 | Zero/negative/exponent/locale/scale/range rejection; reversal uses positive magnitude and opposite direction; #78, #82, #86 |
| FR-FIN-004 | FIN-001, FIN-002; US-ADMIN-007, US-ADVISOR-002; UC-FIN-001 | ADR-012, ADR-018; design §§7-8 | Allowlisted filters, stable cursor/order, date/timezone boundaries, foreign filter isolation, Contributor aggregate omission; #83, #89, #90, #95 |
| FR-FIN-005 | FIN-004, REM-002, SALE-002; US-ADMIN-007; UC-FIN-001 | ADR-001, ADR-002, ADR-018; design §§2, 5, 11 | Unique canonical source link, duplicate/concurrent/timeout replay, no-double-count reconciliation, same-workspace constraints; #79, #81, #89, #96; later source integration in Phases 3-6 |
| FR-FIN-006 | DATA-002, AUD-001; US-ADMIN-007, US-NEG-008; UC-FIN-001 | ADR-002, ADR-018; design §§5-6, 9-12 | Pending edit conflict, Approved immutability, reversal/replacement/archive/file history, no hard delete, migration preservation; #84, #86, #88, #94, #96 |
| FR-FIN-007 | FIN-006, PR-008; US-ADMIN-006, US-CONTRIB-002/003, US-NEG-007; UC-FIN-001 | ADR-013, ADR-018; design §§4, 6-7 | Contributor always Pending/NotEffective, own eligible edit, every official consumer excludes Pending/Rejected, no total/count leakage; #82, #84, #89, #92, #96 |
| FR-FIN-008 | FIN-007; US-ADMIN-006, US-CONTRIB-003, US-NEG-007; UC-FIN-001 | ADR-013, ADR-018; design §§4, 6, 11 | Admin-only atomic Pending decision/audit, reason policy, idempotent/concurrent one winner, Rejected preservation, no Approved rollback; #85, #93, #96 |
| FR-FIN-009 | FIN-008, IAM-004; US-CONTRIB-004, US-NEG-002; UC-FIN-001 | ADR-012, ADR-013, ADR-018; design §§4, 7-10 | Contributor-specific queries/schemas omit totals, counts, metadata, files, errors, notifications and cache leaks while preserving own status view; #83, #84, #88-#92, #96 |
| FR-FIN-010 | FIN-009, IAM-004; US-ADVISOR-002/003, US-NEG-003; UC-FIN-001 | ADR-013, ADR-018; design §§4-5, 8, 10 | Permitted Approved read, attributed comment/flag, Admin flag resolution, mutation/decision denial, audit and two-workspace isolation; #87, #94, #96 |

## Cross-cutting gates

| Gate | Trace | Evidence expectation |
| --- | --- | --- |
| Workspace and authorization | FR-AUTHZ-001 to FR-AUTHZ-005; NFR-SEC-001; ADR-012/013/016 | Same-workspace positive and concealed foreign/role-negative cases at repository, service, API, file, aggregate, and browser boundaries |
| Audit and privacy | FR-AUTHZ-006; FR-AUD-001/002; NFR-COR-006; NFR-PRIV-001/002 | Event-to-audit catalogue coverage, atomic rollback, safe correlation, and zero prohibited payload/free-text fields |
| Financial correctness | NFR-COR-001 to NFR-COR-005; ADR-008/018 | Exact boundaries, one canonical event, reversal conservation, zero partial commits, migration and restore reconciliation |
| Retry and failure | NFR-REL-005/006; NFR-PERF-007 | Stable safe errors, repeated/concurrent/timeout-after-commit evidence, one intended mutation, visible UI progress |
| Files | NFR-SEC-007/008 | Abuse limiting plus full receipt lifecycle and cross-workspace download matrix |
| Time and observability | NFR-OBS-001/003/006 | Correlation propagation, UTC instants, workspace-date periods, no sensitive logs |
| Accessibility and language | NFR-A11Y-001 to NFR-A11Y-003; NFR-I18N-001 to NFR-I18N-003 | Keyboard, screen reader/axe, 320px, 200% zoom, expansion, translation keys, and Shan review |
| Delivery truth | FR-DEL-001 to FR-DEL-003; NFR-MNT-001/002/004/005/007 | Locked clean checkout, architecture/static/security/test gates, executed counts, no unexecuted pass claim |

## Phase 2 execution sequence

1. #77 accepts ADR-018, the focused design, and this traceability matrix.
2. #78-#89 implement exact backend, database, review, receipt, and summary contracts.
3. #90-#95 implement role-safe accessible frontend flows using backend values only.
4. #96 executes the complete exit matrix and publishes evidence.

The milestone cannot close while a required suite is failed, skipped without an accepted
reason, or unexecuted. Later-phase source integrations remain explicit dependencies rather
than Phase 2 pass claims.
