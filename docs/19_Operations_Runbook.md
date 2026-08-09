# F2S Operations and Incident Runbook

## 1. Purpose and status

This runbook defines future F2S production monitoring, alert handling, operator roles, incident response, safe diagnostics, maintenance, deployment rollback, provider outages, communication, evidence and tabletop exercises. It is the operational companion to the [Deployment Design](18_Deployment_Design.md) and [Backup and Recovery Design](20_Backup_Recovery.md).

It follows the [Non-Functional Requirements](04_Non_Functional_Requirements.md), [Security Design](15_Security_Design.md), and [Test Strategy](17_Test_Strategy.md).

This document does not claim that monitoring, on-call coverage, backups, alerts, commands or production infrastructure exist. Exact validated commands, provider consoles, contacts and dashboards are populated only during implementation and kept in an access-controlled operator copy where sensitive.

## 2. Operating principles

1. User safety and financial-data integrity take priority over uptime optics.
2. Operators fail closed, preserve evidence and avoid speculative destructive actions.
3. One incident has one declared lead, correlation ID, severity, timeline and decision log.
4. Monitoring is actionable only when an owner receives and tests the alert.
5. Logs and incident records use safe metadata; they are not a secondary workspace-data store.
6. Audit/business truth is not edited through operations logs or direct database repair.
7. Recovery uses approved immutable artifacts and verified backups, not an improvised production copy.
8. External/provider failure remains outside committed core financial transactions.
9. Maintenance, silence and exceptions have an owner, start, expiry and post-check.
10. Every incident and failed drill produces learning, owned remediation and a regression check.

## 3. Current official incident-response baseline

[NIST SP 800-61 Revision 3](https://csrc.nist.gov/pubs/sp/800/61/r3/final) is the initial external reference for integrating incident preparation, detection, response and recovery into cybersecurity risk management. F2S uses it as guidance; this runbook's project-specific authority, privacy and recovery rules remain controlling.

## 4. Operational registry required before production

The restricted operator registry records, without being committed publicly:

- primary and alternate incident/recovery lead contact paths;
- provider/account owner and billing contact;
- deployment, database, security, backup/key and communications responsibilities;
- Hetzner, DNS, registry, monitoring, email/Gemini and backup-storage escalation paths;
- current production domain/resource IDs and safe dashboard/runbook links;
- break-glass access location, approval and revocation path;
- maintenance window and family/user communication channel; and
- last alert, restore, key-custody and access-review drill dates.

No contact list contains passwords, private keys, tokens, full database URLs or workspace records. Public repository placeholders are never treated as a working escalation path.

## 5. Roles and authority

| Role | Authority | Prohibited shortcut |
| --- | --- | --- |
| Incident lead | Declare severity, coordinate, approve containment/cutover/closure | Make unrecorded destructive changes |
| Operations lead | Inspect/deploy/restart approved services, coordinate provider | Directly edit business records |
| Database/recovery lead | Freeze writes, inspect health, run approved backup/restore/migration procedure | Use runtime role for administration or guess schema rollback |
| Security lead | Contain credentials/access, preserve evidence, assess notification | Publish sensitive incident details or destroy evidence |
| Communications owner | Send approved safe status/user messages | Speculate, blame or expose workspace/security detail |
| Scribe/verifier | Maintain UTC timeline, decisions, checks and outcomes | Copy raw secrets/payloads into ticket/chat |

A small team may combine roles, but each action still records which authority was exercised. High-impact recovery, secret rotation, database repair and return-to-service decisions receive independent verification when a qualified person is available.

## 6. Severity and response objectives

These are initial internal objectives, not customer SLAs. Production cannot start until alert delivery and realistic coverage are confirmed.

| Severity | Examples | Acknowledge | Stabilise/decision objective | Update cadence |
| --- | --- | --- | --- | --- |
| `SEV-1 Critical` | Confirmed cross-workspace exposure, active secret compromise, destructive corruption, total outage requiring recovery | 30 minutes, 24x7 target | Begin containment within 30 minutes; recovery follows 4-hour RTO where applicable | Every 30 minutes |
| `SEV-2 High` | Major feature unavailable, repeated 5xx, database degraded, backup RPO at risk, certificate near failure | 2 hours | Action plan within 4 hours | Every 2 hours |
| `SEV-3 Medium` | Limited degradation, capacity warning, failed non-critical provider, single job backlog | 1 business day | Planned remediation within 2 business days | Daily/at material change |
| `SEV-4 Low` | Maintenance improvement, isolated warning with no impact | 3 business days | Prioritised backlog decision | At closure/change |

If on-call coverage cannot support these values, the service claim and availability target must be narrowed explicitly before production. A missed objective is recorded, reviewed and not hidden by reclassifying severity after the event.

## 7. Monitoring inventory and initial thresholds

All thresholds are provisional until production-like baselines exist. Critical health loss must become operator-visible within 5 minutes.

| Signal | Warning | Critical | First response |
| --- | --- | --- | --- |
| External HTTPS/readiness | 2 failures/2 minutes | Sustained failure or 3 failures within 5 minutes | Confirm from second vantage point; inspect edge/API health |
| HTTP 5xx rate | >2% for 10 minutes above minimum request count | >5% for 5 minutes | Compare deployment/time/correlation categories; do not log bodies |
| API p95 latency | Above NFR target for 15 minutes | >2x target for 10 minutes | Check DB/pool/host/provider dependency |
| Host CPU | >80% for 15 minutes | >95% for 5 minutes | Identify bounded service/process; preserve headroom |
| Host memory | >80% for 15 minutes | >90% or OOM/restart | Identify leak/pressure; do not blindly add restart loop |
| Filesystem/inodes | 70% | 85% | Stop avoidable generation, inspect safe category usage, expand/cleanup by policy |
| PostgreSQL readiness | Intermittent failure/slow probe | Unavailable or repeated crash recovery | Freeze risky writes/deployments; database runbook |
| DB connections | 70% usable pool/slots | 85% or reserved operator capacity at risk | Stop load source; preserve operator slots |
| Long transaction/lock | Above measured/approved threshold | Blocks critical operations or migration | Identify safe session metadata; use approved cancellation decision |
| Backup eligible-point age | 18 hours | 24 hours | Backup/recovery owner; preserve prior set and storage headroom |
| WAL archive lag | 5 minutes | 15 minutes | Inspect archive/storage/key path and WAL disk capacity |
| Certificate expiry | 30 days | 14 days or failed renewal | Test renewal/reload and DNS/account authority |
| Container restart | Repeated twice/10 minutes | Crash loop or readiness unavailable | Capture safe logs/state; stop blind restart |
| Security/config scan | Medium/fix required | Critical/High or unsafe public config | Block release/contain exposure |

Alerts include environment, severity, service, safe event code, UTC time, deployment version and correlation/runbook link. They exclude URLs with sensitive query values, request bodies, cookies, headers, database statements/values and raw provider/file content.

## 8. Alert lifecycle

1. **Receive:** acknowledge through the approved channel; record alert ID and UTC time.
2. **Validate:** confirm environment and signal from an independent view; identify false/stale alert without suppressing evidence.
3. **Classify:** assign incident/severity, affected capability, confidentiality/integrity/availability impact and lead.
4. **Contain:** stop harmful exposure/change while preserving the safest available service.
5. **Diagnose:** use the minimum safe logs/metrics/config/version metadata needed.
6. **Recover:** follow the named service, deployment or recovery runbook.
7. **Verify:** health, critical synthetic flow, financial/source integrity where relevant and alert recovery.
8. **Close:** record cause, timeline, impact, objective result, follow-ups and monitoring/test change.

An alert may be closed as false positive only with evidence and an owned threshold/monitor correction. Repeated manual dismissal is a monitoring defect.

## 9. Safe diagnostics and evidence

Operators may collect:

- timestamp, service/module, deployment image digest/commit and configuration schema version;
- process/container health, restart reason and bounded resource statistics;
- safe route template, status class, duration and correlation ID;
- database availability, connection/lock counts and safe query fingerprints without bind values;
- backup ID/state/age/size class and checksum result; and
- cloud/network/certificate event metadata.

Operators must not paste passwords, tokens, cookies, authorisation/CSRF headers, private keys, full connection strings, payment/bank details, raw SQL parameters, request/response bodies, protected files/reports, workspace free text or unmasked AI payloads into terminal history, tickets, email/chat, screenshots or support bundles.

For Phase 1 investigation, begin with the safe UUID correlation ID and a bounded UTC window.
Correlate operational records with the action/result evidence defined in the
[Audit Event Catalogue](22_Audit_Event_Catalogue.md). Do not infer that an omitted workspace or
resource ID is missing telemetry: concealed denial events intentionally exclude probed foreign
identifiers. Audit correction appends new evidence; operators do not update or delete an event.

If sensitive evidence is necessary for a security investigation, it uses a separately approved encrypted evidence location, minimum access, chain-of-custody record and expiry. Public GitHub issues/PRs never contain vulnerability or workspace details.

## 10. Incident response lifecycle

### 10.1 Declare and coordinate

1. Create incident ID, severity, UTC start, lead/scribe and restricted coordination channel.
2. State known facts, unknowns, affected environment/capabilities and immediate user risk.
3. Freeze unrelated deployments and destructive maintenance.
4. Establish next update time and required specialist/provider escalation.

### 10.2 Contain

Containment may disable one feature/provider, revoke one credential/session family, block one route/source, set the application read-only/unavailable, or isolate the host. Choose the smallest action that stops harm without preserving unsafe availability. Record every change and its reversal condition.

Do not delete/rebuild the suspected source before deciding evidence needs. Do not rotate a key in a way that makes the only backup unreadable. Do not announce technical exploit details before containment.

### 10.3 Eradicate and recover

Identify the exploited/misconfigured component and all equivalent exposure. Remove unauthorised access, rotate/revoke affected secrets, deploy approved fixed artifacts, restore through the Backup Design when integrity is uncertain, and revalidate public ports/TLS/config/permissions.

Return to service requires incident-lead approval, named verification evidence and an observation period. Optional integrations return after core health and safety.

### 10.4 Close and learn

The post-incident record contains safe timeline, root/contributing causes, impact category, detection gap, containment/recovery actions, RPO/RTO/response-objective results and owned due-dated actions. It updates tests, monitoring, design/runbooks and secret/access controls. Blameless learning does not remove accountability for unresolved risk.

## 11. Runbook: application or edge unavailable

**Trigger:** external health failure, readiness failure or sustained 5xx.

1. Confirm from external and host/internal health without sending real user data.
2. Check certificate/DNS/firewall/Nginx, then API readiness, then PostgreSQL; identify the first failed boundary.
3. Compare failure start with deployment/config/provider/host events.
4. If a new release is responsible and schema compatible, use the rollback runbook.
5. If resource pressure exists, stop non-core/report/AI workers before core API where safe.
6. If PostgreSQL integrity/availability is uncertain, stop risky writes and use the database/recovery runbook.
7. Verify HTTPS, headers, readiness, authentication and one synthetic critical flow; observe alert recovery.

Restart only a known failed service after capturing safe evidence and confirming restart cannot worsen corruption or erase evidence. Repeated restart without cause becomes `SEV-2` or higher.

## 12. Runbook: PostgreSQL unavailable or corrupt

1. Declare at least `SEV-2`; use `SEV-1` for corruption, data loss or complete outage requiring restore.
2. Stop deployments/migrations and prevent new writes if partial availability could create inconsistency.
3. Preserve PostgreSQL/container/host state, recent WAL and safe logs; do not delete data directory.
4. Check storage/inodes, memory/OOM, connection exhaustion, certificate/authentication, lock and crash-recovery state.
5. Use approved safe cancellation/restart only when diagnosis supports it.
6. If integrity is uncertain or restart fails, invoke the Backup Design on replacement isolated infrastructure.
7. Before reopening, reconcile constraints, counts, financial totals, files, audit and workspace isolation.

Direct SQL correction of business records is prohibited. Required correction uses the domain's normal reversal/correction flow after service recovery.

## 13. Runbook: disk or inode pressure

1. At 70%, identify growth by approved category: PostgreSQL/WAL, protected files, reports/temp, logs, images or unknown.
2. Confirm backup/retention health before removing any data.
3. Stop or throttle non-critical generators and investigate failed cleanup/archive jobs.
4. Delete only artifacts already eligible under documented retention; never manually delete PostgreSQL data/WAL, backup chain pieces or unknown protected files.
5. Expand/replace storage through the Deployment runbook when growth is legitimate.
6. At 85%, declare `SEV-2`, preserve write headroom and verify database plus backup after remediation.

Unknown growth or evidence of attacker activity escalates to security incident handling.

## 14. Runbook: backup failure or RPO risk

1. Acknowledge at warning; declare `SEV-2` when no eligible point can remain within 24 hours.
2. Preserve the last known-good set; suspend expiry that could remove recovery coverage.
3. Check source health, storage/copy capacity, network, scoped credential, encryption/key and manifest result.
4. Quarantine corrupt/partial output; never promote it or overwrite the prior set.
5. Retry only after cause is understood and within bounded policy; avoid repeated load during source degradation.
6. Confirm both independent copies and integrity, then update eligibility/age.
7. Schedule an immediate restore verification when integrity, tool, key or chain behavior was affected.

## 15. Runbook: certificate or DNS failure

1. Confirm canonical DNS records, certificate names/chain/expiry, time sync and Nginx last-known-good config.
2. Determine whether renewal, provider authority, rate limit, account access or DNS propagation failed.
3. Preserve the last valid certificate/key and config; do not weaken TLS or disable HTTPS as a workaround.
4. Renew/reissue through the approved account, validate before reload, and test TLS/redirect/headers externally.
5. Rotate/revoke the key if compromise is suspected and begin security assessment.

HSTS rollback is not immediate; deployment and domain decisions must account for previously cached policy.

## 16. Runbook: failed deployment or migration

1. Stop rollout and record image digests, schema version, completed step and health result.
2. If validation failed before migration, keep the current release unchanged.
3. If migration failed, preserve database state and use its reviewed forward-fix/restore plan; do not blindly rerun/downgrade.
4. If new app fails but schema is backward compatible, redeploy the previous immutable image/configuration.
5. If schema is incompatible/destructive, do not start the old app; escalate to database/recovery lead.
6. Verify readiness, external HTTPS, synthetic critical flow, logs/alerts, schema and financial reconciliation as risk requires.
7. Keep deployment failed until the observation window and follow-up evidence complete.

## 17. Runbook: suspected credential or secret exposure

1. Declare `SEV-1` for active/high-impact production secret exposure; restrict discussion/evidence.
2. Identify secret class, consumers, privileges, exposure window and evidence without repeating its value.
3. Disable/revoke the credential and contain affected service/account; preserve access/audit logs.
4. Rotate dependent credentials/keys in a safe order that keeps required backup decryption available.
5. Search repository, images, CI artifacts, logs, tickets and provider history using fingerprints/canaries—not by redistributing plaintext.
6. Rebuild/redeploy clean artifacts where embedding is possible; invalidate sessions if session/signing material is affected.
7. Confirm old credential rejection, new credential least privilege, no persistence and alert coverage.

## 18. Runbook: suspected data disclosure or cross-workspace access

1. Declare `SEV-1`, preserve evidence and stop the affected route/job/report/file/AI preparation or whole service if necessary.
2. Record affected object types, time window and safe identifiers; do not expand access merely to inspect broadly.
3. Revoke compromised sessions/credentials and isolate suspect artifacts/caches/providers.
4. Determine whether content, existence, count, timing, logs, files or external payloads crossed the boundary.
5. Fix through reviewed code/config and run the complete two-workspace isolation matrix plus canary/log scans.
6. Security/legal/communications owners decide notification without placing affected workspace data in public systems.
7. Return only after containment, regression evidence, secret/session action and monitoring are approved.

## 19. Runbook: optional provider outage

Email, Gemini, report renderer, telemetry exporter or storage integrations must have bounded timeouts and failure states outside core transactions.

1. Confirm provider scope/status and F2S timeout/rate/quota/authentication categories.
2. Disable/circuit-break only the failing integration; preserve core finance/farming access.
3. Keep queued work bounded/idempotent and communicate delay honestly.
4. Do not remove masking, TLS, validation, authentication or safety controls to restore provider success.
5. Verify safe replay/fallback and no duplicated mutation after recovery.

## 20. Maintenance and change cadence

| Cadence | Required review |
| --- | --- |
| Daily/automated | Availability, application/DB health, eligible backup age, WAL/copy status, disk/certificate critical alerts |
| Weekly | Capacity trends, failed jobs, error/latency trends, backup catalog, provider quotas and open high-severity actions |
| Monthly | OS/image/dependency/security updates, access/account inventory, cost/capacity, retention expiry, availability and incident metrics |
| Quarterly | Full restore drill, key-custody access, alert delivery/failure injection, operator access review and tabletop |
| Before/after material change | Backup/rollback readiness, migration plan, health/security smoke and observation window |
| Annually | Provider/region/topology/risk, RPO/RTO/retention, runbook ownership and disaster scenario review |

Critical dependency updates are assessed within 7 days and High updates within 30 days of reliable notification per NFR-MNT-006. Maintenance cannot be postponed indefinitely without a risk owner and expiry.

Planned maintenance records scope, expected user impact, backup/rollback, start/end, owner, communication and abort threshold. Alert silences are narrow and automatically expire; health/RPO/security critical signals retain an independent path.

## 21. User and stakeholder communication

Messages state affected capability, start/current status, safe workaround if any, next update time and resolution confirmation. They do not expose stack traces, exploit detail, internal hosts, workspace identity, financial values or uncertain blame.

For security/privacy events, only the incident lead with security/legal input approves audience and content. Public status cannot claim “no data affected” until supported by evidence. Communications use reviewed Shan-first user text when delivered in-product.

## 22. Incident record and retention

The safe incident record contains incident ID, severity, UTC timeline, roles, affected capability/data classification, safe versions/resources, decisions, containment/recovery actions, objective results, communication times, evidence locations and follow-ups. Sensitive evidence is referenced, not copied.

Safe incident/maintenance records are retained 24 months provisionally. Security audit events follow the 365-day minimum in the Security Design; operational logs remain 14 days for edge and 30 days for application/security logs. Any longer evidence hold has purpose, access, owner and expiry.

## 23. Tabletop exercises

At least quarterly, rotate scenarios and record `PASS`, `PARTIAL`, `FAIL` or `BLOCKED` honestly.

| Scenario | Inject | Required decisions | Pass evidence |
| --- | --- | --- | --- |
| Total outage/restore | Host and Volume unavailable; primary operator reachable | Severity, recovery declaration, alternate copy/key, communication, cutover | Timed restore plan exercises 24h RPO/4h RTO and every verifier |
| Database outage | PostgreSQL crash plus unknown integrity | Write freeze, evidence, restart-versus-restore decision | No direct repair; reconciliation gate named |
| Cross-workspace incident | Synthetic report exposes another workspace identifier | Feature/service containment, session/provider scope, notification decision | Isolation/canary/regression and safe evidence plan |
| Failed migration rollback | New schema partially applied; old image incompatible | Stop, forward-fix versus restore, communication | No blind downgrade; exact authority/evidence |
| Backup compromise | Primary backup credential can delete history | Revoke, preserve, use independent copy/key | Secondary recovery path and copy independence proven |
| Certificate expiry | Renewal fails with 10 days remaining | Escalation, reissue, last-known-good handling | TLS is not weakened; external verification named |

Each exercise tests contact/authority availability, safe communication and at least one unexpected inject. Findings have owner, severity, due date and retest. Tabletop success does not replace live alert tests or full restore drills.

## 24. Verification and production gates

Before production, F2S must prove:

- contact/escalation and break-glass paths work without exposing secrets;
- critical app/database health reaches an operator within 5 minutes;
- thresholds, ownership, suppression and alert delivery are configured/tested;
- logs/alerts/support evidence pass prohibited-value canary tests;
- each named runbook is exercised on production-like or isolated infrastructure;
- deployment failure uses compatible rollback or approved restore, never guessed downgrade;
- complete backup restore passes the Backup Design's 24-hour RPO/4-hour RTO and reconciliation;
- at least one outage, security incident and rollback tabletop passes; and
- open Critical/High operational findings block release or have the approved time-bound security exception.

## 25. Deferred decisions and Issue #16 acceptance

Deferred: actual operator/contact registry; on-call tooling/coverage; monitoring/log/alert vendors; exact dashboards/queries/commands; provider support contracts; maintenance window; public status channel; legal notification duties; forensics provider; incident evidence store; refined thresholds from measured baseline; and final record retention.

Issue #16 operations acceptance is satisfied when monitoring, thresholds, alert ownership, logs, incidents, maintenance, provider failure and rollback have actionable sequences; initial acknowledgement/escalation objectives are honest; logs/evidence exclude secrets and workspace payloads; restore, outage, incident and rollback tabletop scenarios have pass evidence; recovery links to the Backup Design; and no live operational change is made.
